#!/usr/bin/env python3
"""
App Replicator - Classic Android XML Layout Decompiler v3.0
===========================================================
Parses legacy and non-Compose Android XML layouts (res/layout/*.xml):
1. Analyzes Android view hierarchy (ConstraintLayout, LinearLayout, RecyclerView, etc.)
2. Translates layout attributes (match_parent, wrap_content, dp margins, padding)
3. Maps Android views to idiomatic Flutter widgets
4. Generates clean Flutter widgets for hybrid or traditional Android apps
"""

import os
import sys
import re
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def clean_tag(tag: str) -> str:
    """Strips package prefix from custom or support library XML tags."""
    if "}" in tag:
        tag = tag.split("}", 1)[1]
    return tag.split(".")[-1]


def parse_dp_or_value(val: Optional[str]) -> str:
    """Parses dp/sp dimensions or matches."""
    if not val:
        return "0.0"
    val = val.strip()
    if val in ["match_parent", "fill_parent"]:
        return "double.infinity"
    elif val == "wrap_content":
        return "null"

    match = re.match(r"([0-9.]+)(dp|sp|px)", val)
    if match:
        num = float(match.group(1))
        unit = match.group(2)
        if unit == "px":
            return str(round(num / 3.5, 1))  # default 560dpi scaling
        return str(num)
    return "0.0"


class XmlLayoutToFlutterConverter:
    def __init__(self, xml_path: str, layout_name: str):
        self.xml_path = Path(xml_path)
        self.layout_name = layout_name

    def convert(self) -> str:
        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        widget_tree = self._convert_element(root, indent=3)

        class_name = "".join(w.capitalize() for w in self.layout_name.replace("-", "_").split("_") if w)
        if not class_name.endswith("Layout"):
            class_name += "Layout"

        return f"""import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

class {class_name} extends StatelessWidget {{
  const {class_name}({{super.key}});

  @override
  Widget build(BuildContext context) {{
    return Directionality(
      textDirection: TextDirection.rtl, // Preserves Arabic RTL alignment
      child: {widget_tree.strip()},
    );
  }}
}}
"""

    def _convert_element(self, elem: ET.Element, indent: int = 3) -> str:
        tag = clean_tag(elem.tag)
        attribs = elem.attrib

        # Extract common Android attributes
        android_ns = "{http://schemas.android.com/apk/res/android}"
        padding = attribs.get(f"{android_ns}padding") or attribs.get("android:padding")
        margin = attribs.get(f"{android_ns}layout_margin") or attribs.get("android:layout_margin")
        text = attribs.get(f"{android_ns}text") or attribs.get("android:text")
        src = attribs.get(f"{android_ns}src") or attribs.get("android:src")
        orientation = attribs.get(f"{android_ns}orientation") or attribs.get("android:orientation", "vertical")
        width = attribs.get(f"{android_ns}layout_width") or attribs.get("android:layout_width")
        height = attribs.get(f"{android_ns}layout_height") or attribs.get("android:layout_height")

        spaces = "  " * indent
        child_spaces = "  " * (indent + 1)

        # Children recursion
        children_widgets = [self._convert_element(c, indent + 1) for c in list(elem)]

        widget_str = ""

        if tag in ["LinearLayout", "TableLayout"]:
            is_col = orientation.lower() != "horizontal"
            dir_widget = "Column" if is_col else "Row"
            children_str = ",\n".join(children_widgets)
            widget_str = f"""{spaces}{dir_widget}(
{child_spaces}mainAxisSize: MainAxisSize.min,
{child_spaces}crossAxisAlignment: CrossAxisAlignment.start,
{child_spaces}children: [
{children_str}
{child_spaces}],
{spaces})"""

        elif tag in ["ConstraintLayout", "RelativeLayout", "FrameLayout"]:
            if len(children_widgets) == 1:
                widget_str = children_widgets[0]
            else:
                children_str = ",\n".join(children_widgets)
                widget_str = f"""{spaces}Stack(
{child_spaces}children: [
{children_str}
{child_spaces}],
{spaces})"""

        elif tag in ["ScrollView", "NestedScrollView"]:
            child_content = children_widgets[0] if children_widgets else f"{child_spaces}Container()"
            widget_str = f"""{spaces}SingleChildScrollView(
{child_spaces}physics: const BouncingScrollPhysics(),
{child_spaces}child: {child_content.strip()},
{spaces})"""

        elif tag in ["RecyclerView", "ListView"]:
            widget_str = f"""{spaces}ListView.builder(
{child_spaces}shrinkWrap: true,
{child_spaces}physics: const NeverScrollableScrollPhysics(),
{child_spaces}itemCount: 5,
{child_spaces}itemBuilder: (context, index) {{
{child_spaces}  return const ListTile(
{child_spaces}    title: Text('List item'),
{child_spaces}  );
{child_spaces}}},
{spaces})"""

        elif tag in ["TextView", "MaterialTextView"]:
            txt_display = text if text else "Text Label"
            widget_str = f"""{spaces}Text(
{child_spaces}'{txt_display}',
{child_spaces}style: Theme.of(context).textTheme.bodyMedium,
{spaces})"""

        elif tag in ["ImageView", "AppCompatImageView", "ShapeableImageView"]:
            if src and src.endswith(".svg"):
                widget_str = f"""{spaces}SvgPicture.asset(
{child_spaces}'assets/icons/{Path(src).stem}.svg',
{child_spaces}width: 24,
{child_spaces}height: 24,
{spaces})"""
            else:
                widget_str = f"""{spaces}Container(
{child_spaces}width: 32,
{child_spaces}height: 32,
{child_spaces}decoration: BoxDecoration(
{child_spaces}  color: Colors.grey.withOpacity(0.2),
{child_spaces}  borderRadius: BorderRadius.circular(8),
{child_spaces}),
{child_spaces}child: const Icon(Icons.image_outlined, size: 20),
{spaces})"""

        elif tag in ["Button", "MaterialButton"]:
            btn_txt = text if text else "Action"
            widget_str = f"""{spaces}ElevatedButton(
{child_spaces}onPressed: () {{}},
{child_spaces}child: Text('{btn_txt}'),
{spaces})"""

        elif tag in ["CardView", "MaterialCardView"]:
            child_content = children_widgets[0] if children_widgets else f"{child_spaces}Container()"
            widget_str = f"""{spaces}Card(
{child_spaces}elevation: 2,
{child_spaces}shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
{child_spaces}child: {child_content.strip()},
{spaces})"""

        elif tag in ["EditText", "TextInputEditText"]:
            hint = attribs.get(f"{android_ns}hint") or attribs.get("android:hint", "Enter text...")
            widget_str = f"""{spaces}TextField(
{child_spaces}decoration: InputDecoration(
{child_spaces}  hintText: '{hint}',
{child_spaces}  border: const OutlineInputBorder(),
{child_spaces}),
{spaces})"""

        else:
            if children_widgets:
                children_str = ",\n".join(children_widgets)
                widget_str = f"""{spaces}Column(
{child_spaces}children: [
{children_str}
{child_spaces}],
{spaces})"""
            else:
                widget_str = f"{spaces}const SizedBox.shrink()"

        # Apply padding / margin wrapper if specified
        if padding:
            p_val = parse_dp_or_value(padding)
            widget_str = f"""{spaces}Padding(
{child_spaces}padding: const EdgeInsets.all({p_val}),
{child_spaces}child: {widget_str.strip()},
{spaces})"""

        return widget_str


def main():
    parser = argparse.ArgumentParser(description="App Replicator - Classic Android XML Layout Decompiler v3.0")
    parser.add_argument("xml_file", help="Path to Android layout XML file")
    parser.add_argument("--output", default="lib/presentation/widgets", help="Output directory")
    args = parser.parse_args()

    xml_p = Path(args.xml_file)
    layout_name = xml_p.stem
    converter = XmlLayoutToFlutterConverter(str(xml_p), layout_name)
    flutter_code = converter.convert()

    out_p = Path(args.output) / f"{layout_name}_layout.dart"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        f.write(flutter_code)

    print(f"[OK] Transpiled Android XML Layout to Flutter: {out_p}")


if __name__ == "__main__":
    main()
