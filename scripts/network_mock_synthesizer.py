#!/usr/bin/env python3
"""
App Replicator - Network & Mock API Synthesizer v3.0
====================================================
Transforms intercepted network payloads (HAR, mitmproxy flows, or decrypted JSON files)
into production-ready Flutter data layer components:
1. Infers JSON schemas and generates strongly-typed Dart Data Models
2. Generates fromJson() and toJson() serialization methods
3. Produces a Mock Data Repository with embedded real response fixtures
4. Enables 100% offline-ready, fully interactive Flutter replicas
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple, Set, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def to_pascal_case(text: str) -> str:
    words = re.split(r'[-_ ]+', text)
    return "".join(w.capitalize() for w in words if w)


def to_camel_case(text: str) -> str:
    pascal = to_pascal_case(text)
    return pascal[0].lower() + pascal[1:] if pascal else ""


def to_snake_case(text: str) -> str:
    s = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', text)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s).lower()


class DartModelGenerator:
    def __init__(self, root_name: str):
        self.root_name = to_pascal_case(root_name)
        self.generated_classes: Dict[str, str] = {}

    def generate_from_sample(self, data: Any, class_name: Optional[str] = None) -> str:
        if class_name is None:
            class_name = self.root_name

        if isinstance(data, list):
            if data:
                return self.generate_from_sample(data[0], class_name)
            else:
                data = {}

        fields: List[Tuple[str, str, str]] = []  # (json_key, dart_field, dart_type)

        for key, value in data.items():
            dart_field = to_camel_case(key)
            if dart_field in ["default", "switch", "case", "return", "class", "final", "new", "in", "is"]:
                dart_field = f"{dart_field}Value"

            dart_type = "dynamic"

            if value is None:
                dart_type = "String?"
            elif isinstance(value, bool):
                dart_type = "bool"
            elif isinstance(value, int):
                dart_type = "int"
            elif isinstance(value, float):
                dart_type = "double"
            elif isinstance(value, str):
                dart_type = "String"
            elif isinstance(value, dict):
                nested_class = f"{class_name}_{to_pascal_case(key)}"
                self.generate_from_sample(value, nested_class)
                dart_type = nested_class
            elif isinstance(value, list):
                if value and isinstance(value[0], dict):
                    item_class = f"{class_name}_{to_pascal_case(key)}Item"
                    self.generate_from_sample(value[0], item_class)
                    dart_type = f"List<{item_class}>"
                elif value and isinstance(value[0], str):
                    dart_type = "List<String>"
                elif value and isinstance(value[0], int):
                    dart_type = "List<int>"
                elif value and isinstance(value[0], float):
                    dart_type = "List<double>"
                elif value and isinstance(value[0], bool):
                    dart_type = "List<bool>"
                else:
                    dart_type = "List<dynamic>"

            fields.append((key, dart_field, dart_type))

        # Generate Class Dart Code
        code_lines = [
            f"class {class_name} {{",
        ]

        for _, d_field, d_type in fields:
            code_lines.append(f"  final {d_type}? {d_field};")

        # Constructor
        code_lines.append(f"\n  const {class_name}({{")
        for _, d_field, _ in fields:
            code_lines.append(f"    this.{d_field},")
        code_lines.append("  });")

        # fromJson
        code_lines.append(f"\n  factory {class_name}.fromJson(Map<String, dynamic> json) {{")
        code_lines.append(f"    return {class_name}(")

        for j_key, d_field, d_type in fields:
            if d_type.startswith("List<") and not d_type.endswith("dynamic>"):
                inner = d_type[5:-1]
                if inner in ["String", "int", "double", "bool"]:
                    code_lines.append(f"      {d_field}: json['{j_key}'] != null ? List<{inner}>.from(json['{j_key}']) : null,")
                else:
                    code_lines.append(f"      {d_field}: json['{j_key}'] != null ? (json['{j_key}'] as List).map((i) => {inner}.fromJson(i as Map<String, dynamic>)).toList() : null,")
            elif not d_type.endswith("?") and d_type not in ["String", "int", "double", "bool", "dynamic"]:
                code_lines.append(f"      {d_field}: json['{j_key}'] != null ? {d_type}.fromJson(json['{j_key}'] as Map<String, dynamic>) : null,")
            else:
                code_lines.append(f"      {d_field}: json['{j_key}'] as {d_type},")

        code_lines.append("    );")
        code_lines.append("  }")

        # toJson
        code_lines.append("\n  Map<String, dynamic> toJson() => {")
        for j_key, d_field, d_type in fields:
            if d_type.startswith("List<") and not d_type.endswith("dynamic>") and not d_type[5:-1] in ["String", "int", "double", "bool"]:
                code_lines.append(f"    '{j_key}': {d_field}?.map((e) => e.toJson()).toList(),")
            elif not d_type.endswith("?") and d_type not in ["String", "int", "double", "bool", "dynamic"]:
                code_lines.append(f"    '{j_key}': {d_field}?.toJson(),")
            else:
                code_lines.append(f"    '{j_key}': {d_field},")
        code_lines.append("  };")

        code_lines.append("}\n")

        self.generated_classes[class_name] = "\n".join(code_lines)
        return class_name


def synthesize_mock_repository(model_class: str, sample_payload: Any, file_snake_name: str) -> str:
    """Creates a Mock repository with embedded real JSON fixture."""
    json_literal = json.dumps(sample_payload, indent=4, ensure_ascii=False)
    repo_name = f"Mock{model_class}Repository"

    return f"""import 'dart:async';
import 'dart:convert';
import '{file_snake_name}_model.dart';

class {repo_name} {{
  // Intercepted & decrypted real API fixture
  static const String _fixtureJson = r'''{json_literal}''';

  Future<{model_class}> fetch{model_class}() async {{
    // Simulate real network latency (350ms)
    await Future.delayed(const Duration(milliseconds: 350));
    final Map<String, dynamic> data = json.decode(_fixtureJson) as Map<String, dynamic>;
    return {model_class}.fromJson(data);
  }}
}}
"""


def process_network_payload(input_file: str, model_name: str, output_dir: str):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print(f"[*] Reading payload: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        content = json.load(f)

    # Handle HAR file or direct JSON
    sample_data = content
    if isinstance(content, dict) and "log" in content and "entries" in content["log"]:
        print("[*] HAR format detected. Extracting first valid response payload...")
        entries = content["log"]["entries"]
        found = False
        for entry in entries:
            resp_content = entry.get("response", {}).get("content", {})
            text = resp_content.get("text")
            if text:
                try:
                    sample_data = json.loads(text)
                    found = True
                    break
                except Exception:
                    pass
        if not found:
            raise ValueError("Could not extract JSON payload from HAR file.")

    gen = DartModelGenerator(model_name)
    root_class = gen.generate_from_sample(sample_data)

    snake_name = to_snake_case(model_name)
    models_file_path = out_path / f"{snake_name}_model.dart"
    repo_file_path = out_path / f"mock_{snake_name}_repository.dart"

    # Write Models
    all_models_code = "\n".join(gen.generated_classes.values())
    with open(models_file_path, "w", encoding="utf-8") as f:
        f.write(all_models_code)
    print(f"[+] Generated Data Model: {models_file_path} ({len(gen.generated_classes)} classes)")

    # Write Mock Repository
    mock_repo_code = synthesize_mock_repository(root_class, sample_data, snake_name)
    with open(repo_file_path, "w", encoding="utf-8") as f:
        f.write(mock_repo_code)
    print(f"[+] Generated Mock Repository: {repo_file_path}")


def main():
    parser = argparse.ArgumentParser(description="App Replicator - Network & Mock API Synthesizer v3.0")
    parser.add_argument("input_json", help="Path to decrypted response JSON or HAR file")
    parser.add_argument("--name", default="WalletData", help="Base name for Dart Model (e.g., WalletAccount, LoginResponse)")
    parser.add_argument("--output-dir", default="lib/data/mock", help="Output directory in Flutter project")
    args = parser.parse_args()

    process_network_payload(args.input_json, args.name, args.output_dir)


if __name__ == "__main__":
    main()
