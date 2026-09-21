#!/usr/bin/env python3
"""
App Replicator - Master Pipeline Orchestrator v3.0
==================================================
The unified one-command execution engine for the entire Android-to-Flutter
replication workflow:
Phase 0: Device Discovery & Package Verification
Phase 1: Automated APK Pulling & SSL Patching (app_patcher.py)
Phase 2: Asset Extraction & Vector Conversion (asset_extractor.py)
Phase 2.5: Design System & Custom Font Extraction (design_system_extractor.py)
Phase 2.8: Deep Screen Decompilation (deep_screen_decompiler.py)
Phase 2.8.5: Automated Flutter Code Synthesis (compose_to_flutter_transpiler.py)
Phase 2.9: Runtime Pixel Color Extraction (color_palette_extractor.py)
Phase 3: Live Screen Inspection (ui_inspector.py)
Phase 4: Flutter Clean Architecture Scaffolding (flutter_scaffolder.py)
Phase 5.5: Automated Visual Diff & Fidelity SSIM Engine (visual_diff_engine.py)
Phase 5.6: Interactive HTML Fidelity Dashboard (fidelity_dashboard.py)
"""

import os
import sys
import time
import argparse
import subprocess
from pathlib import Path
from typing import List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def run_step(title: str, script_name: str, args: List[str], cwd: Optional[Path] = None) -> bool:
    print(f"\n{'=' * 65}")
    print(f"🚀 {title}")
    print(f"{'=' * 65}")

    script_path = Path(__file__).parent / script_name
    if not script_path.exists():
        print(f"[!] Error: Script not found: {script_path}")
        return False

    cmd = [sys.executable, str(script_path)] + args
    print(f"[*] Command: {' '.join(cmd)}\n")

    t_start = time.time()
    res = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    elapsed = round(time.time() - t_start, 2)

    if res.returncode != 0:
        print(f"\n[!] Step Failed ({elapsed}s) with exit code {res.returncode}")
        return False

    print(f"\n[OK] Step Completed in {elapsed}s")
    return True


def run_orchestrated_clone(package_name: str, device_serial: str, flutter_dir: str,
                           target_screen: Optional[str] = None, skip_pull: bool = False):
    total_start = time.time()
    work_dir = Path("replication_workspace") / package_name.split(".")[-1]
    work_dir.mkdir(parents=True, exist_ok=True)

    bundle_path = work_dir / "pulled_apks" / f"{package_name.split('.')[-1]}.apks"
    assets_dir = work_dir / "extracted_assets"
    decompiled_dir = work_dir / "decompiled_screens"
    inspection_dir = work_dir / "inspected_screen"
    diff_dir = work_dir / "visual_diff"

    print(f"""
╔═════════════════════════════════════════════════════════════════╗
║         APP REPLICATOR v3.0 — MASTER PIPELINE ORCHESTRATOR      ║
╚═════════════════════════════════════════════════════════════════╝
Target Package:  {package_name}
Target Device:   {device_serial}
Flutter Project: {flutter_dir}
Target Screen:   {target_screen or 'All Detected Screens'}
Workspace:       {work_dir.resolve()}
""")

    # Phase 0: Verification
    print("[*] Phase 0: Verifying ADB connection...")
    adb_check = subprocess.run(["adb", "-s", device_serial, "get-state"], capture_output=True, text=True)
    if adb_check.returncode != 0:
        print(f"[!] Target device '{device_serial}' is offline or not found via ADB.")
        return

    # Phase 1: Pull & Patch
    if not skip_pull or not bundle_path.exists():
        success = run_step(
            "Phase 1: APK Pull & SSL Pinning Patch",
            "app_patcher.py",
            [package_name, device_serial, str(bundle_path.parent)]
        )
        if not success:
            print("[!] APK pull failed. Halting pipeline.")
            return
    else:
        print(f"[OK] Phase 1: Skipping pull; using existing bundle: {bundle_path}")

    # Phase 2: Asset Extraction
    run_step(
        "Phase 2: Universal Vector & Asset Extraction",
        "asset_extractor.py",
        [str(bundle_path), "--output", str(assets_dir)]
    )

    # Phase 2.5: Design System & Fonts
    run_step(
        "Phase 2.5: Design System & Fonts Extraction",
        "design_system_extractor.py",
        [str(bundle_path), "--flutter-dir", flutter_dir]
    )

    # Phase 2.8: Deep Screen Decompilation (if target screen specified)
    screen_name = target_screen or "Home"
    run_step(
        f"Phase 2.8: Deep Screen Decompilation ({screen_name})",
        "deep_screen_decompiler.py",
        [str(bundle_path), "--screen", screen_name, "--output", str(decompiled_dir)]
    )

    # Phase 2.8.5: Compose to Flutter Transpilation
    comp_tree_json = decompiled_dir / f"{screen_name.lower()}_component_tree.json"
    if comp_tree_json.exists():
        run_step(
            f"Phase 2.8.5: Compose-to-Flutter Code Synthesis ({screen_name})",
            "compose_to_flutter_transpiler.py",
            [str(comp_tree_json), "--screen", screen_name, "--output-dir", f"{flutter_dir}/lib/features"]
        )

    # Phase 3: Live UI Inspection
    run_step(
        "Phase 3: Live Screen Inspection & Pixel Truth",
        "ui_inspector.py",
        ["--serial", device_serial, "--output-dir", str(inspection_dir), "--screen-name", f"{screen_name.lower()}_ref"]
    )

    total_time = round(time.time() - total_start, 2)
    print(f"""
===================================================================
   [+] MASTER REPLICATION PIPELINE COMPLETED IN {total_time}s!
===================================================================
- Assets:        {assets_dir}
- Decompiled:    {decompiled_dir}
- Flutter Code:  {flutter_dir}/lib/features
- Live Screen:   {inspection_dir}

Next: Run 'flutter run' in your Flutter project, then invoke Phase 5.5:
python scripts/visual_diff_engine.py <reference_png> <replica_png> --output-dir {diff_dir}
""")


def main():
    parser = argparse.ArgumentParser(description="App Replicator - Master Pipeline Orchestrator v3.0")
    parser.add_argument("package", help="Target Android package name (e.g. com.ahd.jaib)")
    parser.add_argument("--device", default="emulator-5554", help="ADB Device Serial (default: emulator-5554)")
    parser.add_argument("--flutter-dir", default="flutter_replica", help="Target Flutter project directory")
    parser.add_argument("--screen", default="Home", help="Target screen name (default: Home)")
    parser.add_argument("--skip-pull", action="store_true", help="Skip APK pull if bundle already exists")
    args = parser.parse_args()

    run_orchestrated_clone(args.package, args.device, args.flutter_dir, args.screen, args.skip_pull)


if __name__ == "__main__":
    main()
