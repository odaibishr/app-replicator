#!/usr/bin/env python3
"""
App Replicator - Color Palette Pixel Extractor v2.0
====================================================
Extracts the REAL color palette from a live app screenshot by pixel sampling
specific UI regions. ARSC colors alone are NEVER enough — this script captures
what actually renders at runtime (dark mode, gradients, card tints).

Usage:
  python color_palette_extractor.py --serial emulator-5554 --output lib/core/theme/
  python color_palette_extractor.py --screenshot screenshot.png --output lib/core/theme/
  python color_palette_extractor.py --serial emulator-5554 --ui-dump hierarchy.xml --output lib/core/theme/

Outputs:
  - extracted_palette.json: All sampled colors with coordinates and region names
  - app_colors.dart: Flutter color constants ready to use
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import xml.etree.ElementTree as ET
    import re
except ImportError:
    pass

# ─── ADB Helpers ─────────────────────────────────────────────────────────────
def adb_screencap(serial: str, output_path: Path):
    """Capture screenshot from device."""
    subprocess.run(
        ["adb", "-s", serial, "shell", "screencap", "-p", f"/sdcard/_palette_cap.png"],
        check=True, capture_output=True
    )
    subprocess.run(
        ["adb", "-s", serial, "pull", "/sdcard/_palette_cap.png", str(output_path)],
        check=True, capture_output=True
    )
    subprocess.run(
        ["adb", "-s", serial, "shell", "rm", "/sdcard/_palette_cap.png"],
        capture_output=True
    )
    print(f"[+] Screenshot captured: {output_path}")

def adb_get_density(serial: str) -> int:
    """Get device display density."""
    try:
        result = subprocess.run(
            ["adb", "-s", serial, "shell", "wm", "density"],
            capture_output=True, text=True
        )
        for line in result.stdout.strip().split('\n'):
            if 'Physical' in line or 'density' in line.lower():
                parts = line.split(':')
                if len(parts) >= 2:
                    return int(parts[-1].strip())
        return 560
    except Exception:
        return 560

# ─── Pixel Sampling ──────────────────────────────────────────────────────────
def sample_pixel(img: 'Image.Image', x: int, y: int) -> str:
    """Sample a pixel at (x, y) and return hex color."""
    x = max(0, min(x, img.width - 1))
    y = max(0, min(y, img.height - 1))
    pixel = img.getpixel((x, y))
    if len(pixel) == 4:
        r, g, b, a = pixel
    else:
        r, g, b = pixel[:3]
    return f"#{r:02X}{g:02X}{b:02X}"

def sample_region_average(img: 'Image.Image', cx: int, cy: int, radius: int = 5) -> str:
    """Sample average color in a small region around (cx, cy)."""
    r_total, g_total, b_total, count = 0, 0, 0, 0
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            px = max(0, min(cx + dx, img.width - 1))
            py = max(0, min(cy + dy, img.height - 1))
            pixel = img.getpixel((px, py))
            r_total += pixel[0]
            g_total += pixel[1]
            b_total += pixel[2]
            count += 1
    r = r_total // count
    g = g_total // count
    b = b_total // count
    return f"#{r:02X}{g:02X}{b:02X}"

def auto_define_regions(img_width: int, img_height: int) -> Dict[str, Tuple[int, int]]:
    """Auto-define sampling regions based on common mobile app layout."""
    return {
        # Header area
        'header_bg': (img_width // 2, 150),
        'header_left': (100, 150),
        'header_right': (img_width - 100, 150),
        
        # Screen background
        'screen_bg_top': (img_width // 2, img_height // 4),
        'screen_bg_center': (50, img_height // 2),
        'screen_bg_bottom': (50, img_height - 300),
        
        # Card area (assuming cards are in upper-middle portion)
        'primary_card_center': (img_width // 2, img_height // 4 + 100),
        'primary_card_top': (img_width // 2, img_height // 4),
        'secondary_card_left': (img_width // 6, img_height // 4 + 100),
        'secondary_card_right': (img_width * 5 // 6, img_height // 4 + 100),
        
        # Service grid area (middle of screen)
        'grid_card_bg': (img_width // 4, img_height * 3 // 5),
        'grid_card_bg2': (img_width // 2, img_height * 3 // 5),
        'grid_card_bg3': (img_width * 3 // 4, img_height * 3 // 5),
        
        # Bottom nav
        'bottom_nav_bg': (img_width // 2, img_height - 100),
        'bottom_nav_active': (img_width * 4 // 5, img_height - 100),
        
        # FAB / Primary button (center bottom)
        'fab_center': (img_width // 2, img_height - 130),
        
        # Text sampling (approximate text-heavy areas)
        'text_region_header': (img_width - 200, 120),
        'text_region_grid': (img_width // 4, img_height * 3 // 5 + 80),
    }

def extract_regions_from_ui_dump(xml_path: Path, img_width: int, img_height: int) -> Dict[str, Tuple[int, int]]:
    """Extract sampling coordinates from UI Automator XML dump."""
    regions = auto_define_regions(img_width, img_height)
    
    try:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        
        for node in root.iter('node'):
            bounds = node.get('bounds', '')
            res_id = node.get('resource-id', '')
            text = node.get('text', '')
            
            m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
            if not m:
                continue
            
            left, top, right, bottom = map(int, m.groups())
            cx = (left + right) // 2
            cy = (top + bottom) // 2
            
            # Map known resource IDs to region names
            rid_lower = res_id.lower()
            if 'toolbar' in rid_lower or 'appbar' in rid_lower:
                regions['appbar_bg'] = (cx, cy)
            elif 'card' in rid_lower:
                regions[f'card_{res_id.split("/")[-1]}'] = (cx, cy)
            elif 'button' in rid_lower or 'fab' in rid_lower:
                regions[f'button_{res_id.split("/")[-1]}'] = (cx, cy)
            elif 'nav' in rid_lower and 'bottom' in rid_lower:
                regions['bottom_nav_element'] = (cx, cy)
    except Exception as e:
        print(f"[!] Warning parsing UI dump: {e}")
    
    return regions

# ─── Color Clustering ────────────────────────────────────────────────────────
def cluster_colors(colors: List[str], threshold: int = 30) -> List[Dict]:
    """Simple color clustering to identify distinct brand colors."""
    def hex_to_rgb(h):
        h = h.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    
    def color_distance(c1, c2):
        return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5
    
    clusters = []
    for hex_color in colors:
        rgb = hex_to_rgb(hex_color)
        found = False
        for cluster in clusters:
            if color_distance(rgb, cluster['rgb']) < threshold:
                cluster['count'] += 1
                cluster['samples'].append(hex_color)
                found = True
                break
        if not found:
            clusters.append({
                'hex': hex_color,
                'rgb': rgb,
                'count': 1,
                'samples': [hex_color],
            })
    
    # Sort by frequency
    clusters.sort(key=lambda c: c['count'], reverse=True)
    return clusters

# ─── Dart Generator ──────────────────────────────────────────────────────────
def generate_colors_dart(palette: Dict, output_path: Path):
    """Generate app_colors.dart from extracted palette."""
    lines = [
        "import 'package:flutter/material.dart';",
        "",
        "/// Auto-generated from live screenshot pixel sampling",
        "/// DO NOT edit manually — regenerate with color_palette_extractor.py",
        "class AppColors {",
        "  AppColors._();",
        "",
    ]
    
    for name, data in palette.items():
        hex_val = data['hex'].lstrip('#')
        dart_hex = f"0xFF{hex_val}"
        lines.append(f"  /// Sampled from: {data.get('region', 'unknown')} at ({data.get('x', 0)}, {data.get('y', 0)})")
        lines.append(f"  static const Color {name} = Color({dart_hex});")
        lines.append("")
    
    lines.append("}")
    lines.append("")
    
    output_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f"[+] Generated {output_path}")

# ─── Name Guesser ────────────────────────────────────────────────────────────
def guess_color_name(region_name: str, hex_color: str) -> str:
    """Guess a semantic color name from region and color value."""
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    
    # Detect common color categories
    is_dark = (r + g + b) < 150
    is_white = (r + g + b) > 700
    is_red = r > 180 and g < 80 and b < 80
    
    if 'bg' in region_name or 'background' in region_name:
        if is_dark:
            return 'background'
        return 'backgroundLight'
    elif 'card' in region_name:
        if is_red:
            return 'primaryCard'
        elif is_dark:
            return 'surfaceCard'
        return f'card_{region_name.split("_")[-1]}'
    elif 'header' in region_name or 'appbar' in region_name:
        return 'headerBg'
    elif 'nav' in region_name:
        return 'navBarBg'
    elif 'fab' in region_name or 'button' in region_name:
        if is_red:
            return 'primary'
        return 'buttonBg'
    elif 'text' in region_name:
        if is_white:
            return 'textPrimary'
        return 'textSecondary'
    elif 'grid' in region_name:
        return f'gridCard'
    
    # Fallback
    return region_name.replace(' ', '_')

# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Extract real color palette from live app screenshot via pixel sampling"
    )
    parser.add_argument("--serial", "-s", default="emulator-5554", help="ADB device serial")
    parser.add_argument("--screenshot", default=None, help="Path to existing screenshot (skip capture)")
    parser.add_argument("--ui-dump", default=None, help="Path to UI Automator XML dump for precise region detection")
    parser.add_argument("--output", "-o", default="lib/core/theme/", help="Output directory for generated files")
    args = parser.parse_args()
    
    if not HAS_PIL:
        print("[!] Error: Pillow is required. Install with: pip install Pillow")
        sys.exit(1)
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Get screenshot
    if args.screenshot:
        screenshot_path = Path(args.screenshot)
    else:
        screenshot_path = output_dir / "_palette_screenshot.png"
        adb_screencap(args.serial, screenshot_path)
    
    if not screenshot_path.exists():
        print(f"[!] Screenshot not found: {screenshot_path}")
        sys.exit(1)
    
    img = Image.open(screenshot_path)
    print(f"[*] Screenshot loaded: {img.width}x{img.height}")
    
    # Step 2: Define sampling regions
    if args.ui_dump:
        regions = extract_regions_from_ui_dump(Path(args.ui_dump), img.width, img.height)
    else:
        regions = auto_define_regions(img.width, img.height)
    
    print(f"[*] Sampling {len(regions)} regions...")
    
    # Step 3: Sample colors
    sampled = {}
    all_colors = []
    for region_name, (x, y) in regions.items():
        hex_color = sample_region_average(img, x, y, radius=8)
        color_name = guess_color_name(region_name, hex_color)
        sampled[region_name] = {
            'hex': hex_color,
            'x': x,
            'y': y,
            'region': region_name,
            'dart_name': color_name,
        }
        all_colors.append(hex_color)
        print(f"  [{region_name}] ({x}, {y}) -> {hex_color} -> {color_name}")
    
    # Step 4: Cluster to find distinct brand colors
    clusters = cluster_colors(all_colors)
    print(f"\n[*] Distinct color clusters: {len(clusters)}")
    for i, c in enumerate(clusters[:12]):
        print(f"  Cluster {i+1}: {c['hex']} (appeared {c['count']}x)")
    
    # Step 5: Save palette JSON
    palette_path = output_dir / "extracted_palette.json"
    palette_data = {
        'screenshot': str(screenshot_path),
        'dimensions': {'width': img.width, 'height': img.height},
        'sampled_regions': sampled,
        'color_clusters': [{'hex': c['hex'], 'count': c['count']} for c in clusters[:12]],
    }
    palette_path.write_text(json.dumps(palette_data, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\n[+] Palette saved -> {palette_path}")
    
    # Step 6: Generate app_colors.dart
    dart_palette = {}
    seen_names = set()
    for region_name, data in sampled.items():
        name = data['dart_name']
        if name in seen_names:
            name = f"{name}_{region_name.split('_')[-1]}"
        seen_names.add(name)
        dart_palette[name] = data
    
    dart_path = output_dir / "app_colors.dart"
    generate_colors_dart(dart_palette, dart_path)
    
    print(f"\n{'='*50}")
    print(f"  Color Palette Extraction Complete!")
    print(f"  Regions Sampled: {len(sampled)}")
    print(f"  Distinct Colors: {len(clusters)}")
    print(f"  Palette JSON: {palette_path}")
    print(f"  Dart Colors: {dart_path}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
