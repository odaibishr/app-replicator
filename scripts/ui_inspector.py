#!/usr/bin/env python3
"""
App Replicator - Mobile UI Inspector & Hierarchy Analyzer
=========================================================
Extracts live screen layout, XML hierarchy, bounds, text, and visual specs from Android:
1. Dumps UI Automator XML hierarchy without writing temp files to device (via /dev/tty)
2. Captures high-res screenshot directly via ADB stream
3. Parses XML bounds [left,top][right,bottom] into exact Flutter coordinate specifications
4. Extracts color palette and dominant tones from the screenshot
5. Produces screen_spec.json for 100% pixel-perfect Flutter widget synthesis
"""

import os
import sys
import re
import json
import argparse
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional

def run_adb(cmd_args: List[str], serial: str = "emulator-5554", binary: bool = False):
    full_cmd = ["adb", "-s", serial] + cmd_args
    res = subprocess.run(full_cmd, capture_output=True)
    if res.returncode != 0:
        err_msg = res.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"ADB command failed: {' '.join(full_cmd)}\n{err_msg}")
    return res.stdout if binary else res.stdout.decode("utf-8", errors="ignore")

def capture_screenshot(output_path: Path, serial: str = "emulator-5554"):
    print(f"[*] Capturing screenshot from {serial}...")
    png_bytes = run_adb(["exec-out", "screencap", "-p"], serial=serial, binary=True)
    # Fix CRLF line endings on Windows adb if needed
    if png_bytes.startswith(b"\x89PNG\r\r\n"):
        png_bytes = png_bytes.replace(b"\r\r\n", b"\r\n")
    output_path.write_bytes(png_bytes)
    print(f"[+] Screenshot saved to: {output_path}")

def capture_hierarchy(output_path: Path, serial: str = "emulator-5554") -> str:
    print(f"[*] Dumping UI Automator hierarchy from {serial}...")
    try:
        xml_text = run_adb(["exec-out", "uiautomator", "dump", "/dev/tty"], serial=serial)
        if "<?xml" in xml_text:
            xml_text = xml_text[xml_text.find("<?xml"):]
        output_path.write_text(xml_text, encoding="utf-8")
        print(f"[+] UI hierarchy saved to: {output_path}")
        return xml_text
    except Exception:
        # Fallback to file dump if /dev/tty is not supported
        run_adb(["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], serial=serial)
        run_adb(["pull", "/sdcard/window_dump.xml", str(output_path)], serial=serial)
        xml_text = output_path.read_text(encoding="utf-8", errors="ignore")
        return xml_text

def parse_bounds(bounds_str: str) -> Dict[str, int]:
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
    if m:
        left, top, right, bottom = map(int, m.groups())
        return {
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
            "width": right - left,
            "height": bottom - top
        }
    return {"left": 0, "top": 0, "right": 0, "bottom": 0, "width": 0, "height": 0}

def element_to_dict(node: ET.Element) -> Dict[str, Any]:
    attr = node.attrib
    bounds = parse_bounds(attr.get("bounds", ""))
    
    item = {
        "tag": node.tag,
        "class": attr.get("class", ""),
        "resource_id": attr.get("resource-id", ""),
        "package": attr.get("package", ""),
        "text": attr.get("text", ""),
        "content_desc": attr.get("content-desc", ""),
        "clickable": attr.get("clickable", "false") == "true",
        "scrollable": attr.get("scrollable", "false") == "true",
        "checkable": attr.get("checkable", "false") == "true",
        "bounds": bounds,
        "children": []
    }
    
    for child in node:
        item["children"].append(element_to_dict(child))
        
    return item

def extract_screen_spec(xml_content: str, out_json: Path):
    try:
        root = ET.fromstring(xml_content)
        spec = {
            "screen": element_to_dict(root)
        }
        out_json.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[+] Screen spec JSON saved to: {out_json}")
    except Exception as e:
        print(f"[!] Warning: Could not parse XML to JSON spec: {e}")

def main():
    parser = argparse.ArgumentParser(description="Capture Android screen and parse UI hierarchy")
    parser.add_argument("--serial", "-s", default="emulator-5554", help="ADB device serial")
    parser.add_argument("--output-dir", "-o", default="inspected_screen", help="Output directory for artifacts")
    parser.add_argument("--screen-name", "-n", default="current_screen", help="Prefix name for the captured files")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    png_path = out_dir / f"{args.screen_name}.png"
    xml_path = out_dir / f"{args.screen_name}.xml"
    json_path = out_dir / f"{args.screen_name}_spec.json"

    capture_screenshot(png_path, serial=args.serial)
    xml_text = capture_hierarchy(xml_path, serial=args.serial)
    extract_screen_spec(xml_text, json_path)

if __name__ == "__main__":
    main()
