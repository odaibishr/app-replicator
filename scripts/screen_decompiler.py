#!/usr/bin/env python3
"""
App Replicator - Universal Screen Decompiler & Source Code Extractor
====================================================================
Decompiles Android APK DEX bytecode into clean, readable Java/Kotlin source files:
1. Identifies all Composable screens, ViewModels, Navigation graphs, and API endpoints
2. Decompiles matching classes into .java source code using Androguard's internal decompiler (DvClass)
3. Maps state flows, models, and layout architectures
4. Saves decompiled source files into structured folders ready for developer review
"""

import os
import sys
import io
import json
import zipfile
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from loguru import logger
    logger.disable("androguard")
    from androguard.core.apk import APK
    from androguard.core.dex import DEX
    from androguard.decompiler.decompile import DvClass
except ImportError:
    APK = None
    DEX = None
    DvClass = None

def sanitize_class_name(cname: str) -> str:
    # Lcom/ahd/jaib/MainActivity; -> com/ahd/jaib/MainActivity.java
    clean = cname.lstrip("L").rstrip(";")
    return clean.replace("/", os.sep) + ".java"

def decompile_and_save_class(c_obj: Any, out_root: Path) -> Optional[Path]:
    if not DvClass:
        return None
    try:
        dv = DvClass(c_obj, None)
        dv.process()
        source = dv.get_source()
        if not source or len(source.strip()) < 10:
            return None

        rel_path = sanitize_class_name(c_obj.get_name())
        target_file = out_root / rel_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(source, encoding="utf-8", errors="ignore")
        return target_file
    except Exception:
        return None

def analyze_navigation_routes(dex_list: List[Any]) -> List[Dict[str, Any]]:
    routes = []
    keywords = ["home", "login", "register", "profile", "transfer", "services",
                "wallet", "cards", "settings", "reports", "notifications", "support"]

    for d in dex_list:
        for c in d.get_classes():
            for m in c.get_methods():
                code = m.get_code()
                if not code:
                    continue
                for ins in code.get_bc().get_instructions():
                    if "const-string" in ins.get_name():
                        val = ins.get_output().replace('"', '').strip()
                        if ", " in val:
                            val = val.split(", ", 1)[-1]
                        val_lower = val.lower()
                        if any(k == val_lower or f"/{k}" in val_lower for k in keywords):
                            if len(val) < 40 and not any(ext in val for ext in [".", "http", " "]):
                                routes.append({
                                    "route": val,
                                    "found_in_class": c.get_name(),
                                    "method": m.get_name()
                                })
    seen = set()
    unique = []
    for r in routes:
        if r["route"] not in seen:
            seen.add(r["route"])
            unique.append(r)
    return unique

def decompile_all_screens(apk_source: Path, out_dir: Path):
    if not APK or not DEX:
        print("[!] Error: androguard is required.")
        sys.exit(1)

    print(f"[*] Reading and analyzing APK: {apk_source}...")
    apk_bytes = None
    if apk_source.suffix.lower() == ".apks":
        with zipfile.ZipFile(apk_source) as z:
            for name in ["base.apk", z.namelist()[0]]:
                if name in z.namelist():
                    apk_bytes = z.read(name)
                    break
    else:
        apk_bytes = apk_source.read_bytes()

    if not apk_bytes:
        raise RuntimeError("Could not read APK bytes.")

    dex_list = []
    with zipfile.ZipFile(io.BytesIO(apk_bytes)) as z_apk:
        dex_names = [n for n in z_apk.namelist() if n.endswith(".dex")]
        print(f"[+] Found {len(dex_names)} DEX container(s). Parsing...")
        for dn in dex_names:
            dex_list.append(DEX(z_apk.read(dn)))

    print("[*] Discovering navigation routes...")
    routes = analyze_navigation_routes(dex_list)

    print("[*] Decompiling UI screens, ViewModels, and data controllers...")
    src_out = out_dir / "src"
    src_out.mkdir(parents=True, exist_ok=True)

    decompiled_count = 0
    screen_map = {}

    for d in dex_list:
        for c in d.get_classes():
            cname = c.get_name()
            # Decompile app classes, ViewModels, and Composable UI containers
            is_app_class = "com/ahd/jaib" in cname or cname.startswith("Lib/") or cname.startswith("Lra/") or cname.startswith("Lya/")
            is_viewmodel = "ViewModel" in cname or "Lh9/e;" in c.get_superclassname()
            has_composer = any("Lt2/r;" in m.get_descriptor() for m in c.get_methods())

            if is_app_class or is_viewmodel or has_composer:
                saved_path = decompile_and_save_class(c, src_out)
                if saved_path:
                    decompiled_count += 1
                    screen_map[cname] = str(saved_path.relative_to(out_dir))

    print(f"[+] Successfully decompiled {decompiled_count} classes into {src_out}")

    # Generate summary & spec
    spec = {
        "total_decompiled_classes": decompiled_count,
        "routes": routes,
        "screen_map": screen_map
    }
    (out_dir / "decompiled_spec.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    
    md_summary = [
        "# Decompiled Screen & UI Code Summary",
        "",
        f"- **Total Decompiled Classes**: `{decompiled_count}`",
        f"- **Discovered Routes**: `{len(routes)}`",
        f"- **Source Directory**: `src/`",
        "",
        "## Discovered Navigation Routes",
        "| Route | Class | Method |",
        "|---|---|---|"
    ]
    for r in routes:
        md_summary.append(f"| `{r['route']}` | `{r['found_in_class']}` | `{r['method']}` |")
        
    (out_dir / "decompiled_summary.md").write_text("\n".join(md_summary), encoding="utf-8")
    print(f"[+] Full decompilation completed! Summary saved to {out_dir / 'decompiled_summary.md'}")

def main():
    parser = argparse.ArgumentParser(description="Decompile and extract all screens and code from Android APK")
    parser.add_argument("source", help="Path to APK or APKS bundle")
    parser.add_argument("--output", "-o", default="data/decompiled_code", help="Output directory")
    args = parser.parse_args()

    decompile_all_screens(Path(args.source), Path(args.output))

if __name__ == "__main__":
    main()
