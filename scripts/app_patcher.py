#!/usr/bin/env python3
"""
App Replicator - APK Pull & Patcher Tool
========================================
Handles:
1. Locating package on connected ADB emulator / device
2. Pulling all split APKs (base + config splits)
3. Patching SSL pinning via apk-mitm with --debuggable enabled
4. Reinstalling patched APKs cleanly via install-multiple
"""

import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path

def run_cmd(cmd, check=True):
    print(f"[*] Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    res = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True)
    if check and res.returncode != 0:
        print(f"[!] Error:\n{res.stderr}\n{res.stdout}")
        raise RuntimeError(f"Command failed with exit code {res.returncode}")
    return res

def pull_and_patch_app(package_name: str, device_serial: str = "emulator-5554", output_dir: str = "pulled_apks"):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print(f"[*] Step 1: Locating APK paths for {package_name} on {device_serial}...")
    pm_path_res = run_cmd(["adb", "-s", device_serial, "shell", "pm", "path", package_name])
    
    apk_remote_paths = []
    for line in pm_path_res.stdout.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            apk_remote_paths.append(line.replace("package:", "").strip())

    if not apk_remote_paths:
        raise RuntimeError(f"Could not find installed package '{package_name}' on device.")

    print(f"[+] Found {len(apk_remote_paths)} APK part(s). Pulling to {out_path}...")
    local_apks = []
    for r_path in apk_remote_paths:
        fname = Path(r_path).name
        local_target = out_path / fname
        run_cmd(["adb", "-s", device_serial, "pull", r_path, str(local_target)])
        local_apks.append(local_target)

    # Package into .apks bundle
    bundle_name = f"{package_name.split('.')[-1]}.apks"
    bundle_path = out_path / bundle_name
    print(f"[*] Creating bundle {bundle_path}...")
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for lapk in local_apks:
            zipf.write(lapk, arcname=lapk.name)

    print(f"[+] Bundle created successfully: {bundle_path}")

    # Patch with apk-mitm
    patched_bundle_name = bundle_name.replace(".apks", "-patched.apks")
    patched_bundle_path = Path(patched_bundle_name)

    print(f"[*] Step 2: Patching SSL pinning & making debuggable with apk-mitm...")
    npx_cmd = "npx.cmd" if os.name == "nt" else "npx"
    
    env = os.environ.copy()
    java_path = r"C:\Program Files\Android\Android Studio\jbr\bin"
    if os.path.exists(java_path) and java_path not in env.get("PATH", ""):
        env["PATH"] = java_path + os.pathsep + env.get("PATH", "")

    patch_cmd = [npx_cmd, "-y", "apk-mitm", str(bundle_path), "--debuggable"]
    subprocess.run(patch_cmd, check=True, env=env)

    if not patched_bundle_path.exists():
        # Check current dir
        cand = Path(f"./{patched_bundle_name}")
        if cand.exists():
            patched_bundle_path = cand

    print(f"[+] App successfully patched: {patched_bundle_path}")
    return patched_bundle_path

def reinstall_patched_app(patched_bundle_path: Path, package_name: str, device_serial: str = "emulator-5554"):
    print(f"[*] Step 3: Reinstalling patched {package_name} on {device_serial}...")
    temp_dir = Path("temp_install_dir")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(exist_ok=True)

    with zipfile.ZipFile(patched_bundle_path, "r") as z:
        z.extractall(temp_dir)

    apk_files = list(temp_dir.glob("*.apk"))
    print(f"[*] Uninstalling original {package_name}...")
    run_cmd(["adb", "-s", device_serial, "uninstall", package_name], check=False)

    print(f"[*] Installing patched APKs ({len(apk_files)} files)...")
    cmd = ["adb", "-s", device_serial, "install-multiple", "-r"] + [str(p) for p in apk_files]
    run_cmd(cmd)
    
    shutil.rmtree(temp_dir)
    print(f"[+] Patched {package_name} installed successfully!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python app_patcher.py <package_name> [device_serial]")
        sys.exit(1)
    pkg = sys.argv[1]
    serial = sys.argv[2] if len(sys.argv) > 2 else "emulator-5554"
    bundle = pull_and_patch_app(pkg, serial)
    reinstall_patched_app(bundle, pkg, serial)
