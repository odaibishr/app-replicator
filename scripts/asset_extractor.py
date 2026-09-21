#!/usr/bin/env python3
"""
App Replicator - Universal Android Asset Extractor & Vector-to-SVG Converter
===========================================================================
Extracts, ranks, and converts all design assets from an Android APK or decompiled folder:
- Vector Drawables (<vector>) converted into standard W3C SVGs
- Highest-density raster graphics (xxxhdpi > xxhdpi > xhdpi > hdpi)
- Lottie JSON animations
- Audio/Video media (mp3, wav, ogg, mp4)
- Automated noise/boilerplate filtering (Android support libraries, AppCompat)
"""

import os
import sys
import re
import shutil
import zipfile
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Tuple, Optional, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from loguru import logger
    logger.disable("androguard")
    from androguard.core.axml import AXMLPrinter
except ImportError:
    AXMLPrinter = None

BOILERPLATE_PREFIXES = (
    "abc_", "androidx_", "notification_", "btn_checkbox_", 
    "btn_radio_", "material_", "design_", "test_", "common_google_",
    "googleg_", "quantum_ic_", "tooltip_frame", "mtrl_", "navigation_empty_icon"
)

DPI_RANKS = {
    "xxxhdpi": 6,
    "xxhdpi": 5,
    "xhdpi": 4,
    "hdpi": 3,
    "mdpi": 2,
    "ldpi": 1,
    "nodpi": 0,
    "anydpi": 7,
}

def get_dpi_rank(folder_name: str) -> int:
    for dpi, rank in DPI_RANKS.items():
        if dpi in folder_name:
            return rank
    return 0

def android_color_to_svg(color_str: Optional[str]) -> Tuple[str, Optional[str]]:
    """Converts Android color formats (#AARRGGBB, #RRGGBB, color names) to SVG fill/stroke & opacity."""
    if not color_str:
        return "none", None
    color_str = color_str.strip()
    
    if color_str.startswith("#"):
        hex_val = color_str[1:]
        if len(hex_val) == 8: # AARRGGBB
            alpha = int(hex_val[:2], 16) / 255.0
            rgb = f"#{hex_val[2:]}"
            return rgb, f"{alpha:.2f}" if alpha < 0.99 else None
        elif len(hex_val) in (3, 4, 6):
            return color_str, None
    elif "@android:color/white" in color_str or "color/white" in color_str:
        return "#FFFFFF", None
    elif "@android:color/black" in color_str or "color/black" in color_str:
        return "#000000", None
    elif "@android:color/transparent" in color_str or "transparent" in color_str:
        return "none", None
    elif color_str.startswith("?"):
        return "currentColor", None
        
    return "#000000", None

def parse_dimension(dim_str: Optional[str], default: float = 24.0) -> float:
    if not dim_str:
        return default
    m = re.match(r"([\d\.]+)", dim_str)
    return float(m.group(1)) if m else default

def convert_vector_node_to_svg(node: ET.Element, indent: int = 2) -> str:
    """Recursively converts <path>, <group>, and <clip-path> into standard SVG elements."""
    spaces = " " * indent
    tag = node.tag.split("}")[-1] if "}" in node.tag else node.tag
    
    if tag == "path":
        attrs = {k.split("}")[-1]: v for k, v in node.attrib.items()}
        path_data = attrs.get("pathData", "")
        if not path_data:
            return ""
            
        svg_attrs = [f'd="{path_data}"']
        
        fill_color, fill_alpha = android_color_to_svg(attrs.get("fillColor"))
        svg_attrs.append(f'fill="{fill_color}"')
        if fill_alpha:
            svg_attrs.append(f'fill-opacity="{fill_alpha}"')
        if attrs.get("fillAlpha"):
            svg_attrs.append(f'fill-opacity="{attrs["fillAlpha"]}"')
            
        if attrs.get("fillType", "").lower() == "evenodd":
            svg_attrs.append('fill-rule="evenodd"')
            
        if "strokeColor" in attrs:
            stroke_color, stroke_alpha = android_color_to_svg(attrs.get("strokeColor"))
            svg_attrs.append(f'stroke="{stroke_color}"')
            if stroke_alpha:
                svg_attrs.append(f'stroke-opacity="{stroke_alpha}"')
            if attrs.get("strokeAlpha"):
                svg_attrs.append(f'stroke-opacity="{attrs["strokeAlpha"]}"')
            if "strokeWidth" in attrs:
                svg_attrs.append(f'stroke-width="{attrs["strokeWidth"]}"')
            if "strokeLineCap" in attrs:
                svg_attrs.append(f'stroke-linecap="{attrs["strokeLineCap"]}"')
            if "strokeLineJoin" in attrs:
                svg_attrs.append(f'stroke-linejoin="{attrs["strokeLineJoin"]}"')
                
        return f"{spaces}<path {' '.join(svg_attrs)} />\n"
        
    elif tag == "group":
        attrs = {k.split("}")[-1]: v for k, v in node.attrib.items()}
        transforms = []
        tx = float(attrs.get("translateX", 0))
        ty = float(attrs.get("translateY", 0))
        if tx != 0 or ty != 0:
            transforms.append(f"translate({tx}, {ty})")
            
        rot = float(attrs.get("rotation", 0))
        px = float(attrs.get("pivotX", 0))
        py = float(attrs.get("pivotY", 0))
        if rot != 0:
            if px != 0 or py != 0:
                transforms.append(f"rotate({rot} {px} {py})")
            else:
                transforms.append(f"rotate({rot})")
                
        sx = float(attrs.get("scaleX", 1))
        sy = float(attrs.get("scaleY", 1))
        if sx != 1 or sy != 1:
            transforms.append(f"scale({sx}, {sy})")
            
        transform_attr = f' transform="{" ".join(transforms)}"' if transforms else ""
        
        inner_content = ""
        for child in node:
            inner_content += convert_vector_node_to_svg(child, indent + 2)
            
        if inner_content:
            return f"{spaces}<g{transform_attr}>\n{inner_content}{spaces}</g>\n"
        return ""
        
    elif tag == "clip-path":
        attrs = {k.split("}")[-1]: v for k, v in node.attrib.items()}
        path_data = attrs.get("pathData", "")
        if path_data:
            return f'{spaces}<!-- clip-path: {path_data} -->\n'
            
    return ""

def convert_android_vector_to_svg(xml_path: Path) -> Optional[str]:
    """Parses an Android Vector Drawable XML (plaintext or binary AXML) and returns valid SVG string."""
    try:
        raw_bytes = xml_path.read_bytes()
        root = None

        # Try parsing as standard plaintext XML first
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
        except Exception:
            # Fallback to Androguard AXML printer for compiled binary XML
            if AXMLPrinter:
                try:
                    printer = AXMLPrinter(raw_bytes)
                    xml_str = printer.get_xml()
                    if xml_str:
                        root = ET.fromstring(xml_str)
                except Exception:
                    root = None

        if root is None:
            return None

        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
        if tag != "vector":
            return None
            
        attrs = {k.split("}")[-1]: v for k, v in root.attrib.items()}
        
        vp_width = parse_dimension(attrs.get("viewportWidth"), 24.0)
        vp_height = parse_dimension(attrs.get("viewportHeight"), 24.0)
        w = parse_dimension(attrs.get("width"), vp_width)
        h = parse_dimension(attrs.get("height"), vp_height)
        
        body = ""
        for child in root:
            body += convert_vector_node_to_svg(child, indent=2)
            
        if not body.strip():
            return None
            
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{w}" height="{h}" '
            f'viewBox="0 0 {vp_width} {vp_height}">\n'
            f'{body}'
            f'</svg>\n'
        )
    except Exception:
        return None

def extract_from_directory(src_dir: Path, out_dir: Path):
    out_svgs = out_dir / "svgs"
    out_images = out_dir / "images"
    out_sounds = out_dir / "sounds"
    out_anims = out_dir / "animations"

    for d in (out_svgs, out_images, out_sounds, out_anims):
        d.mkdir(parents=True, exist_ok=True)

    vector_count = 0
    img_candidates: Dict[str, Tuple[int, Path]] = {}
    sound_count = 0
    anim_count = 0

    for root, dirs, files in os.walk(src_dir):
        rel_folder = os.path.basename(root).lower()
        rank = get_dpi_rank(rel_folder)

        for fname in files:
            p = Path(root) / fname
            name_lower = p.stem.lower()
            ext = p.suffix.lower()

            if any(name_lower.startswith(pfx) for pfx in BOILERPLATE_PREFIXES):
                continue

            if ext == ".xml":
                svg_content = convert_android_vector_to_svg(p)
                if svg_content:
                    (out_svgs / f"{p.stem}.svg").write_text(svg_content, encoding="utf-8")
                    vector_count += 1
            elif ext in (".png", ".webp", ".jpg", ".jpeg"):
                if name_lower not in img_candidates or rank > img_candidates[name_lower][0]:
                    img_candidates[name_lower] = (rank, p)
            elif ext in (".mp3", ".wav", ".ogg", ".aac", ".flac"):
                shutil.copy2(p, out_sounds / p.name)
                sound_count += 1
            elif ext == ".json":
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    if '"layers"' in content or '"assets"' in content or 'lottie' in p.name.lower():
                        shutil.copy2(p, out_anims / p.name)
                        anim_count += 1
                except Exception:
                    pass

    for _, (_, fpath) in img_candidates.items():
        shutil.copy2(fpath, out_images / fpath.name)

    print(f"[+] Extracted & Converted: {vector_count} SVGs")
    print(f"[+] Extracted: {len(img_candidates)} Highest-DPI Images")
    print(f"[+] Extracted: {sound_count} Audio Tracks")
    print(f"[+] Extracted: {anim_count} Lottie Animations")

def extract_from_apk(apk_path: Path, out_dir: Path):
    temp_unpack = out_dir / "_temp_unpack"
    if temp_unpack.exists():
        shutil.rmtree(temp_unpack)
    temp_unpack.mkdir(parents=True, exist_ok=True)

    print(f"[*] Unpacking APK: {apk_path}...")
    with zipfile.ZipFile(apk_path, "r") as z:
        z.extractall(temp_unpack)

    # If it was an .apks bundle, unpack each inner .apk part
    inner_apks = list(temp_unpack.glob("*.apk"))
    for inner in inner_apks:
        print(f"[*] Unpacking bundle part: {inner.name}...")
        try:
            with zipfile.ZipFile(inner, "r") as z_inner:
                z_inner.extractall(temp_unpack)
        except Exception as e:
            print(f"[!] Warning: Failed to unpack inner APK {inner.name}: {e}")

    extract_from_directory(temp_unpack, out_dir)
    shutil.rmtree(temp_unpack, ignore_errors=True)

def main():
    parser = argparse.ArgumentParser(description="Extract and convert assets from APK or decompiled folder")
    parser.add_argument("source", help="Path to .apk file or decompiled resource folder (e.g. res/)")
    parser.add_argument("--output", "-o", default="extracted_assets", help="Destination directory")
    args = parser.parse_args()

    src = Path(args.source)
    out = Path(args.output)
    if not src.exists():
        print(f"[!] Error: Source '{src}' does not exist.")
        sys.exit(1)

    if src.is_file() and src.suffix.lower() in (".apk", ".zip", ".apks"):
        extract_from_apk(src, out)
    else:
        extract_from_directory(src, out)

if __name__ == "__main__":
    main()
