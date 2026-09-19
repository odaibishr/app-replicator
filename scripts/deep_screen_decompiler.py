#!/usr/bin/env python3
"""
App Replicator - Deep Screen Decompiler v2.0
=============================================
Given a target screen name, fully decompiles that screen into:
1. A readable Kotlin/Compose source reconstruction
2. Complete component tree with all child Composables
3. Animation/effect parameters (scale, rotation, blur, alpha)
4. ViewModel state map with StateFlow bindings
5. Data model definitions used by the screen

This is the KILLER FEATURE of app-replicator v2.0.

Usage:
  python deep_screen_decompiler.py jaib.apks --screen "Home" --output data/deep_decompiled/
  python deep_screen_decompiler.py jaib.apks --screen "Cards" --output data/deep_decompiled/
  python deep_screen_decompiler.py jaib.apks --class "Lib/y;" --output data/deep_decompiled/
"""

import os
import sys
import io
import json
import math
import struct
import zipfile
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple

try:
    from loguru import logger
    logger.disable("androguard")
    from androguard.core.dex import DEX
except ImportError:
    DEX = None

# ─── Float Constant Decoder ─────────────────────────────────────────────────
def decode_float_from_int(raw_int: int) -> Optional[float]:
    """Decode IEEE 754 float from raw integer constant in DEX bytecode."""
    try:
        packed = struct.pack('>I', raw_int & 0xFFFFFFFF)
        return struct.unpack('>f', packed)[0]
    except Exception:
        return None

# ─── Instruction Classifier ─────────────────────────────────────────────────
INSTRUCTION_CATEGORIES = {
    'ui_labels': ['const-string'],
    'method_calls': ['invoke-virtual', 'invoke-static', 'invoke-direct', 'invoke-interface', 'invoke-super'],
    'object_creation': ['new-instance'],
    'field_read': ['sget', 'sget-object', 'sget-boolean', 'sget-wide', 'iget', 'iget-object', 'iget-boolean', 'iget-wide'],
    'field_write': ['sput', 'sput-object', 'sput-boolean', 'iput', 'iput-object', 'iput-boolean'],
    'numeric_const': ['const/4', 'const/16', 'const', 'const/high16', 'const-wide', 'const-wide/16', 'const-wide/32', 'const-wide/high16'],
}

def categorize_instruction(ins_name: str) -> str:
    for category, prefixes in INSTRUCTION_CATEGORIES.items():
        for prefix in prefixes:
            if ins_name.startswith(prefix):
                return category
    return 'other'

# ─── Bytecode Walker ────────────────────────────────────────────────────────
def walk_method_bytecode(method) -> Dict[str, Any]:
    """Walk ALL bytecode instructions in a method, categorizing each one."""
    result = {
        'method_name': method.get_name(),
        'descriptor': method.get_descriptor(),
        'strings': [],
        'invocations': [],
        'new_instances': [],
        'field_reads': [],
        'field_writes': [],
        'float_constants': [],
        'int_constants': [],
    }
    
    code = method.get_code()
    if not code:
        return result
    
    for ins in code.get_bc().get_instructions():
        name = ins.get_name()
        output = ins.get_output()
        category = categorize_instruction(name)
        
        if category == 'ui_labels':
            # Extract string value
            val = output.strip()
            if ', ' in val:
                val = val.split(', ', 1)[-1]
            val = val.strip('"').strip("'")
            if val and len(val) > 0:
                result['strings'].append(val)
                
        elif category == 'method_calls':
            # Extract target class and method
            result['invocations'].append({
                'instruction': name,
                'target': output.strip(),
            })
            
        elif category == 'object_creation':
            result['new_instances'].append(output.strip())
            
        elif category == 'field_read':
            result['field_reads'].append({
                'instruction': name,
                'field': output.strip(),
            })
            
        elif category == 'field_write':
            result['field_writes'].append({
                'instruction': name,
                'field': output.strip(),
            })
            
        elif category == 'numeric_const':
            # Try to decode as float (for animation params)
            try:
                raw_parts = output.strip().split(', ')
                if len(raw_parts) >= 2:
                    raw_val = raw_parts[-1].strip()
                    if raw_val.startswith('0x') or raw_val.startswith('-0x'):
                        int_val = int(raw_val, 16)
                        float_val = decode_float_from_int(int_val)
                        if float_val is not None and 0.01 < abs(float_val) < 1000:
                            result['float_constants'].append({
                                'raw_hex': raw_val,
                                'float_value': round(float_val, 6),
                                'possible_meaning': classify_float(float_val),
                            })
                        result['int_constants'].append(int_val)
            except (ValueError, IndexError):
                pass
    
    return result

def classify_float(val: float) -> str:
    """Guess what a float constant means in UI context."""
    abs_val = abs(val)
    if 0.5 <= abs_val <= 1.0:
        if abs_val > 0.95:
            return 'opacity/alpha (near 1.0)'
        elif abs_val > 0.75:
            return 'scale_factor or alpha'
        else:
            return 'viewport_fraction or scale'
    elif 1.0 < abs_val <= 10.0:
        return f'rotation_degrees ({val}° = {round(val * math.pi / 180, 4)} rad)'
    elif 10.0 < abs_val <= 50.0:
        return 'padding/margin_dp or font_size'
    elif 50.0 < abs_val <= 500.0:
        return 'dimension_dp or duration_ms'
    elif abs_val < 0.5 and abs_val > 0.01:
        return 'enlarge_factor or blur_sigma'
    return 'unknown'

# ─── Component Tree Builder ─────────────────────────────────────────────────
def is_composable_class(class_obj) -> bool:
    """Check if a class is a Jetpack Compose Composable (has Composer parameter)."""
    for m in class_obj.get_methods():
        desc = m.get_descriptor()
        if 'Lt2/r;' in desc or 'Landroidx/compose/runtime/Composer;' in desc:
            return True
    return False

def extract_composable_params(method) -> List[str]:
    """Extract parameter names from Composable method strings."""
    params = []
    code = method.get_code()
    if not code:
        return params
    
    for ins in code.get_bc().get_instructions():
        if 'const-string' in ins.get_name():
            val = ins.get_output().strip()
            if ', ' in val:
                val = val.split(', ', 1)[-1]
            val = val.strip('"')
            # Heuristic: Composable parameter names are typically camelCase identifiers
            if val and val[0].islower() and ' ' not in val and len(val) < 40 and not val.startswith('/'):
                params.append(val)
    
    return params

def build_component_tree(target_class_name: str, dex_list: List, spec_data: Dict,
                          visited: Optional[Set[str]] = None, depth: int = 0) -> Dict[str, Any]:
    """Recursively build the component tree from a target Composable class."""
    if visited is None:
        visited = set()
    
    if target_class_name in visited or depth > 5:
        return {'class': target_class_name, 'note': 'circular_ref_or_max_depth'}
    
    visited.add(target_class_name)
    
    node = {
        'class': target_class_name,
        'methods': [],
        'children': [],
        'strings': [],
        'animation_params': [],
        'state_reads': [],
    }
    
    # Find the class in DEX
    target_class = None
    for d in dex_list:
        for c in d.get_classes():
            if c.get_name() == target_class_name:
                target_class = c
                break
        if target_class:
            break
    
    if not target_class:
        return node
    
    for m in target_class.get_methods():
        method_data = walk_method_bytecode(m)
        
        # Collect UI strings
        for s in method_data['strings']:
            if s not in node['strings']:
                node['strings'].append(s)
        
        # Collect animation floats
        for fc in method_data['float_constants']:
            node['animation_params'].append(fc)
        
        # Find child Composable invocations
        for inv in method_data['invocations']:
            target = inv['target']
            # Extract class name from invocation
            if '->' in target:
                inv_class = target.split('->')[0].strip()
                # Check if this is a Composable we know about
                if inv_class.startswith('L') and inv_class.endswith(';'):
                    # Check if it's in our spec (known screen/component)
                    for d in dex_list:
                        for c in d.get_classes():
                            if c.get_name() == inv_class and is_composable_class(c):
                                child_params = extract_composable_params(
                                    next((cm for cm in c.get_methods() if 'Lt2/r;' in cm.get_descriptor()), None) or m
                                )
                                child_tree = build_component_tree(inv_class, dex_list, spec_data, visited, depth + 1)
                                child_tree['params'] = child_params
                                if child_tree not in node['children']:
                                    node['children'].append(child_tree)
                                break
        
        # Collect ViewModel state reads
        for fr in method_data['field_reads']:
            field_str = fr['field']
            if 'StateFlow' in field_str or 'MutableState' in field_str or 'pq/b1' in field_str:
                node['state_reads'].append(field_str)
        
        node['methods'].append({
            'name': method_data['method_name'],
            'descriptor': method_data['descriptor'],
            'string_count': len(method_data['strings']),
            'invocation_count': len(method_data['invocations']),
            'float_constants': method_data['float_constants'],
        })
    
    return node

# ─── ViewModel Mapper ────────────────────────────────────────────────────────
def map_viewmodel(vm_class_name: str, dex_list: List) -> Dict[str, Any]:
    """Map all StateFlow fields and methods of a ViewModel class."""
    vm_data = {
        'class': vm_class_name,
        'state_fields': [],
        'methods': [],
    }
    
    for d in dex_list:
        for c in d.get_classes():
            if c.get_name() == vm_class_name:
                # Map fields
                for f in c.get_fields():
                    field_type = f.get_descriptor()
                    vm_data['state_fields'].append({
                        'name': f.get_name(),
                        'type': field_type,
                        'is_state_flow': 'pq/b1' in field_type or 'StateFlow' in field_type,
                        'is_mutable_state': 'pq/o0' in field_type or 'MutableState' in field_type,
                    })
                
                # Map methods
                for m in c.get_methods():
                    method_info = walk_method_bytecode(m)
                    vm_data['methods'].append({
                        'name': m.get_name(),
                        'descriptor': m.get_descriptor(),
                        'strings': method_info['strings'][:10],  # First 10 strings
                        'invocation_count': len(method_info['invocations']),
                    })
                
                return vm_data
    
    return vm_data

# ─── Kotlin Source Synthesizer ───────────────────────────────────────────────
def synthesize_kotlin(screen_name: str, component_tree: Dict, vm_data: Dict,
                       spec_data: Dict) -> str:
    """Generate human-readable Kotlin/Compose source from the component tree."""
    
    lines = [
        f'package com.app.presentation.{screen_name.lower()}',
        '',
        'import androidx.compose.foundation.layout.*',
        'import androidx.compose.foundation.lazy.LazyColumn',
        'import androidx.compose.foundation.lazy.items',
        'import androidx.compose.material3.*',
        'import androidx.compose.runtime.*',
        'import androidx.compose.ui.Modifier',
        'import androidx.compose.ui.graphics.graphicsLayer',
        'import androidx.compose.ui.unit.dp',
        '',
        '/**',
        f' * {screen_name} Screen — Deep Decompiled from APK',
        f' * Original Class: {component_tree.get("class", "unknown")}',
        f' * ViewModel: {vm_data.get("class", "unknown")}',
        f' * Total Components: {count_components(component_tree)}',
        f' * Animation Params Found: {len(component_tree.get("animation_params", []))}',
        ' */',
        '',
    ]
    
    # ViewModel class
    if vm_data.get('state_fields'):
        lines.append(f'// ViewModel: {vm_data["class"]}')
        lines.append(f'class {screen_name}ViewModel : ViewModel() {{')
        for field in vm_data['state_fields']:
            flow_type = 'StateFlow' if field.get('is_state_flow') else 'MutableState' if field.get('is_mutable_state') else 'Field'
            lines.append(f'    val {field["name"]}: {flow_type}<*>  // {field["type"]}')
        lines.append('}')
        lines.append('')
    
    # Main Composable
    lines.append('@Composable')
    params_str = ', '.join(component_tree.get('params', ['navController: Any', f'viewModel: {screen_name}ViewModel']))
    lines.append(f'fun {screen_name}Screen({params_str}) {{')
    
    # State observations
    for sr in component_tree.get('state_reads', [])[:10]:
        lines.append(f'    // State read: {sr}')
    
    lines.append('    LazyColumn(modifier = Modifier.fillMaxSize()) {')
    
    # Children
    for i, child in enumerate(component_tree.get('children', [])):
        child_name = clean_class_name(child.get('class', f'Component{i}'))
        child_params = child.get('params', [])
        params_display = ', '.join(child_params[:5]) if child_params else ''
        
        lines.append(f'        item {{')
        lines.append(f'            {child_name}({params_display})')
        
        # Show animation params if any
        for ap in child.get('animation_params', []):
            lines.append(f'            // Animation: {ap["float_value"]} → {ap["possible_meaning"]}')
        
        lines.append(f'        }}')
    
    # Show UI strings found
    interesting_strings = [s for s in component_tree.get('strings', []) 
                          if len(s) > 2 and not s.startswith('L') and not '/' in s[:3]]
    if interesting_strings:
        lines.append('')
        lines.append('        // Discovered UI labels:')
        for s in interesting_strings[:20]:
            lines.append(f'        // "{s}"')
    
    lines.append('    }')
    lines.append('}')
    
    # Animation section
    anim_params = component_tree.get('animation_params', [])
    if anim_params:
        lines.append('')
        lines.append('// ═══ Animation Parameters Extracted from Bytecode ═══')
        for ap in anim_params:
            lines.append(f'// {ap["raw_hex"]} → {ap["float_value"]} ({ap["possible_meaning"]})')
    
    return '\n'.join(lines)

def clean_class_name(cname: str) -> str:
    """Convert obfuscated class name to readable component name."""
    clean = cname.lstrip('L').rstrip(';').split('/')[-1]
    return clean if len(clean) > 2 else f'Component_{clean}'

def count_components(tree: Dict, count: int = 0) -> int:
    count += 1
    for child in tree.get('children', []):
        count = count_components(child, count)
    return count

# ─── Main Entry Point ────────────────────────────────────────────────────────
def deep_decompile_screen(apk_path: Path, screen_name: str, target_class: Optional[str],
                           output_dir: Path, spec_path: Optional[Path] = None):
    if not DEX:
        print("[!] Error: androguard is required. Install with: pip install androguard loguru")
        sys.exit(1)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load spec if available
    spec_data = {}
    if spec_path and spec_path.exists():
        spec_data = json.loads(spec_path.read_text(encoding='utf-8'))
    
    # Read DEX from APK
    print(f"[*] Loading APK: {apk_path}...")
    apk_bytes = None
    if apk_path.suffix.lower() == '.apks':
        with zipfile.ZipFile(apk_path) as z:
            for name in ['base.apk'] + z.namelist():
                if name in z.namelist() and name.endswith('.apk'):
                    apk_bytes = z.read(name)
                    break
    else:
        apk_bytes = apk_path.read_bytes()
    
    if not apk_bytes:
        print("[!] Could not read APK bytes.")
        sys.exit(1)
    
    dex_list = []
    with zipfile.ZipFile(io.BytesIO(apk_bytes)) as z_apk:
        dex_names = [n for n in z_apk.namelist() if n.endswith('.dex')]
        print(f"[+] Found {len(dex_names)} DEX file(s).")
        for dn in dex_names:
            dex_list.append(DEX(z_apk.read(dn)))
    
    # Resolve target class
    if not target_class:
        # Try to find from spec
        target_class = resolve_screen_class(screen_name, spec_data, dex_list)
    
    if not target_class:
        print(f"[!] Could not resolve class for screen '{screen_name}'.")
        print("[*] Available screen hints from bytecode:")
        for d in dex_list:
            for c in d.get_classes():
                if is_composable_class(c):
                    params = extract_composable_params(
                        next((m for m in c.get_methods() if 'Lt2/r;' in m.get_descriptor()), None)
                    ) if any('Lt2/r;' in m.get_descriptor() for m in c.get_methods()) else []
                    if params:
                        print(f"  {c.get_name()} -> params: {params[:5]}")
        sys.exit(1)
    
    # Format target class name for DEX lookup
    if not target_class.startswith('L'):
        target_class = f'L{target_class}'
    if not target_class.endswith(';'):
        target_class = f'{target_class};'
    
    print(f"[*] Deep decompiling screen: {screen_name} (class: {target_class})")
    
    # Build component tree
    print("[*] Building component tree...")
    tree = build_component_tree(target_class, dex_list, spec_data)
    
    # Find associated ViewModel
    print("[*] Mapping ViewModel state...")
    vm_class = find_viewmodel_for_screen(target_class, dex_list)
    vm_data = map_viewmodel(vm_class, dex_list) if vm_class else {}
    
    # Save component tree
    tree_path = output_dir / f"{screen_name}_component_tree.json"
    tree_path.write_text(json.dumps(tree, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    print(f"[+] Component tree -> {tree_path}")
    
    # Save animations
    anim_path = output_dir / f"{screen_name}_animations.json"
    all_anims = collect_all_animations(tree)
    anim_path.write_text(json.dumps(all_anims, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"[+] Animation params -> {anim_path}")
    
    # Save ViewModel map
    if vm_data:
        vm_path = output_dir / f"{screen_name}_viewmodel.json"
        vm_path.write_text(json.dumps(vm_data, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
        print(f"[+] ViewModel map -> {vm_path}")
    
    # Synthesize Kotlin source
    kotlin_source = synthesize_kotlin(screen_name, tree, vm_data, spec_data)
    kt_path = output_dir / f"{screen_name}_decompiled.kt"
    kt_path.write_text(kotlin_source, encoding='utf-8')
    print(f"[+] Kotlin source -> {kt_path}")
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"  Deep Decompilation Complete: {screen_name}")
    print(f"  Target Class: {target_class}")
    print(f"  Components Found: {count_components(tree)}")
    print(f"  UI Strings: {len(tree.get('strings', []))}")
    print(f"  Animation Params: {len(all_anims)}")
    print(f"  ViewModel Fields: {len(vm_data.get('state_fields', []))}")
    print(f"  Output Directory: {output_dir}")
    print(f"{'='*60}")

def resolve_screen_class(screen_name: str, spec_data: Dict, dex_list: List) -> Optional[str]:
    """Resolve screen name to DEX class using spec data and heuristics."""
    screen_lower = screen_name.lower()
    
    # Check spec routes
    if 'routes' in spec_data:
        for route in spec_data['routes']:
            if route.get('route', '').lower() == screen_lower:
                return route['found_in_class']
    
    # Check screens from screens_architecture_spec
    if 'screens' in spec_data:
        screens_val = spec_data['screens']
        if isinstance(screens_val, dict):
            for k, v in screens_val.items():
                if screen_lower in k.lower() or (isinstance(v, dict) and screen_lower in v.get('name', '').lower()):
                    return k
        elif isinstance(screens_val, list):
            for screen in screens_val:
                if isinstance(screen, dict) and screen_lower in screen.get('class', '').lower():
                    return screen['class']
                elif isinstance(screen, str) and screen_lower in screen.lower():
                    return screen
    
    # Heuristic: search for Composable classes with matching string constants
    for d in dex_list:
        for c in d.get_classes():
            if is_composable_class(c):
                for m in c.get_methods():
                    code = m.get_code()
                    if not code:
                        continue
                    for ins in code.get_bc().get_instructions():
                        if 'const-string' in ins.get_name():
                            val = ins.get_output().strip().strip('"').lower()
                            if val == screen_lower:
                                return c.get_name()
    
    return None

def find_viewmodel_for_screen(screen_class: str, dex_list: List) -> Optional[str]:
    """Find the ViewModel class associated with a screen by analyzing its method parameters."""
    for d in dex_list:
        for c in d.get_classes():
            if c.get_name() == screen_class:
                for m in c.get_methods():
                    desc = m.get_descriptor()
                    # Look for ViewModel-type parameters
                    if 'Lh9/e;' in desc:  # AndroidX ViewModel base
                        # The parameter type is the ViewModel
                        parts = desc.split(';')
                        for p in parts:
                            for d2 in dex_list:
                                for c2 in d2.get_classes():
                                    if c2.get_name().rstrip(';') in p:
                                        if 'Lh9/e;' in c2.get_superclassname():
                                            return c2.get_name()
                    # Direct parameter matching
                    for d2 in dex_list:
                        for c2 in d2.get_classes():
                            sc = c2.get_superclassname()
                            if sc and ('Lh9/e;' in sc or 'ViewModel' in sc):
                                vm_name = c2.get_name().rstrip(';').lstrip('L')
                                if vm_name in desc:
                                    return c2.get_name()
    return None

def collect_all_animations(tree: Dict) -> List[Dict]:
    """Recursively collect all animation parameters from the component tree."""
    anims = list(tree.get('animation_params', []))
    for child in tree.get('children', []):
        anims.extend(collect_all_animations(child))
    return anims

def main():
    parser = argparse.ArgumentParser(
        description="Deep Screen Decompiler — Fully decompile any screen with all components",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deep_screen_decompiler.py jaib.apks --screen Home
  python deep_screen_decompiler.py jaib.apks --screen Cards --output data/deep/
  python deep_screen_decompiler.py jaib.apks --class "Lib/y;" --screen Home
  python deep_screen_decompiler.py jaib.apks --screen Transfer --spec data/decompiled_screens/screens_architecture_spec.json
        """
    )
    parser.add_argument("apk_source", nargs="?", default=None, help="Path to APK or APKS bundle (auto-detected if omitted)")
    parser.add_argument("--screen", "-s", default=None, help="Screen name to decompile (e.g., Home, Cards, Splash, Transfer)")
    parser.add_argument("--class", "-c", dest="target_class", default=None, help="Direct class name (e.g., Lib/y;)")
    parser.add_argument("--output", "-o", default="data/deep_decompiled", help="Output directory")
    parser.add_argument("--spec", default=None, help="Path to screens_architecture_spec.json for route resolution")
    parser.add_argument("--list", "-l", action="store_true", help="List all detected screens and exit")
    args = parser.parse_args()
    
    # Auto-detect APK if not provided
    apk_source = args.apk_source
    if not apk_source:
        for candidate in ["jaib.apks", "app.apk", "base.apk"]:
            if Path(candidate).exists():
                apk_source = candidate
                print(f"[*] Auto-detected APK source: {apk_source}")
                break
        if not apk_source:
            # Search current dir for any .apks or .apk
            apks = list(Path(".").glob("*.apks")) + list(Path(".").glob("*.apk"))
            if apks:
                apk_source = str(apks[0])
                print(f"[*] Auto-detected APK source: {apk_source}")
            else:
                print("[!] Error: No APK file found in current directory. Please specify an APK path.")
                sys.exit(1)
    
    spec_path = Path(args.spec) if args.spec else None
    if not spec_path:
        auto_spec = Path("data/decompiled_screens/screens_architecture_spec.json")
        if auto_spec.exists():
            spec_path = auto_spec
    
    screen_name = args.screen
    if not screen_name and not args.target_class:
        # If no screen provided or --list requested, list available screens
        print(f"[*] No specific screen specified. Discovering screens in {apk_source}...")
        spec_data = {}
        if spec_path and spec_path.exists():
            try:
                with open(spec_path, "r", encoding="utf-8") as f:
                    spec_data = json.load(f)
            except Exception:
                pass
        
        routes = [r.get("route") for r in spec_data.get("routes", []) if r.get("route")]
        if routes:
            print("\n[+] Discovered Screens / Routes:")
            for r in sorted(set(routes)):
                print(f"    - {r}")
            print("\n[*] Defaulting to 'Home' screen...")
            screen_name = "Home"
        else:
            screen_name = "Home"
    elif not screen_name:
        screen_name = "CustomScreen"
    
    deep_decompile_screen(
        Path(apk_source),
        screen_name,
        args.target_class,
        Path(args.output),
        spec_path
    )

if __name__ == "__main__":
    main()
