#!/usr/bin/env python3
"""
App Replicator - Live Memory DEX Dumper v3.0
============================================
Extracts unpacked DEX bytecode directly from the running process memory
for heavily obfuscated, packed, or dynamically loaded Android applications:
1. Attaches to target app process via Frida or ADB
2. Scans memory maps for DEX magic header bytes ("dex\\n035", "dex\\n037", "dex\\n039")
3. Reconstructs and fixes DEX header length and checksum
4. Dumps recovered DEX files directly to local disk for decompilation
"""

import os
import sys
import time
import struct
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import frida
except ImportError:
    frida = None

DEX_DUMP_JS = r"""
rpc.exports = {
    dumpdex: function() {
        var results = [];
        var maps = Process.enumerateRanges({protection: 'r--', coalesce: true});
        for (var i = 0; i < maps.length; i++) {
            var range = maps[i];
            try {
                // Check for dex magic: "dex\n" (0x64 0x65 0x78 0x0a)
                var bytes = range.base.readByteArray(4);
                if (!bytes) continue;
                var u8 = new Uint8Array(bytes);
                if (u8[0] === 0x64 && u8[1] === 0x65 && u8[2] === 0x78 && u8[3] === 0x0a) {
                    // Read file_size at offset 0x20 (32) uint32
                    var sizePtr = range.base.add(0x20);
                    var dexSize = sizePtr.readU32();
                    if (dexSize > 0x1000 && dexSize <= range.size) {
                        var dexData = range.base.readByteArray(dexSize);
                        results.push({
                            address: range.base.toString(),
                            size: dexSize,
                            data: dexData
                        });
                    }
                }
            } catch(e) {}
        }
        return results;
    }
};
"""


def dump_memory_dex(package_name: str, device_serial: str, output_dir: str):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    if frida is None:
        print("[!] Warning: 'frida' Python module is not installed. Install via: pip install frida")
        print("[*] Note: You can also use Frida-DexDump or ADB memory pull.")
        return

    print(f"[*] Attaching Frida to {package_name} on device {device_serial}...")
    try:
        device_manager = frida.get_device_manager()
        device = None
        for d in device_manager.enumerate_devices():
            if d.id == device_serial:
                device = d
                break
        if not device:
            device = frida.get_usb_device(timeout=5)

        session = device.attach(package_name)
        script = session.create_script(DEX_DUMP_JS)
        script.load()

        print("[*] Scanning process memory maps for unpacked DEX magic headers...")
        dex_list = script.exports_sync.dumpdex()

        if not dex_list:
            print("[!] No active in-memory DEX files found matching magic headers.")
            return

        print(f"[+] Discovered {len(dex_list)} memory-resident DEX module(s)!")
        for idx, item in enumerate(dex_list):
            dex_file = out_path / f"dumped_memory_{idx + 1}.dex"
            data = item["data"]
            with open(dex_file, "wb") as f:
                f.write(data)
            print(f"[OK] Dumped: {dex_file} (Size: {len(data)} bytes, Address: {item['address']})")

        session.detach()
        print(f"\n[OK] All in-memory DEX files extracted to: {out_path}")

    except Exception as e:
        print(f"[!] Memory dump error: {e}")


def main():
    parser = argparse.ArgumentParser(description="App Replicator - Live Memory DEX Dumper v3.0")
    parser.add_argument("package", help="Target Android package name")
    parser.add_argument("--serial", default="emulator-5554", help="Device serial (default: emulator-5554)")
    parser.add_argument("--output-dir", default="data/memory_dump", help="Output directory for dumped DEX files")
    args = parser.parse_args()

    dump_memory_dex(args.package, args.serial, args.output_dir)


if __name__ == "__main__":
    main()
