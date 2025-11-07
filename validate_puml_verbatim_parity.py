#!/usr/bin/env python3
"""
Validate verbatim parity between the PlantUML string present in a JSON artifact
and the saved .puml file, allowing only normal escaping differences (\\n, \\t, \\",
CRLF vs LF) and leading/trailing whitespace.

Usage:
  python validate_puml_verbatim_parity.py --json path/to/output-data.json --puml path/to/diagram.puml

Exit codes:
  0 -> parity OK (after allowed unescaping/normalization)
  1 -> parity failed (content differs beyond allowed escaping)
  2 -> invalid inputs / runtime error
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Optional


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(read_text(path))


def find_plantuml_text(obj: Any) -> Optional[str]:
    """Recursively search for a PlantUML string within a JSON-like structure.
    
    New format (prioritized):
    {
      "data": {
        "diagram": {
          "name": "scenario name",
          "plantuml": "@startuml\n...\n@enduml"
        }
      },
      "errors": []
    }
    """
    if isinstance(obj, str):
        if "@startuml" in obj and "@enduml" in obj:
            return obj
        return None
    if isinstance(obj, dict):
        # NEW FORMAT: Check for data.diagram.plantuml structure first (prioritized)
        if "data" in obj and isinstance(obj["data"], dict):
            data_node = obj["data"]
            if "diagram" in data_node and isinstance(data_node["diagram"], dict):
                diagram_node = data_node["diagram"]
                if "plantuml" in diagram_node and isinstance(diagram_node["plantuml"], str):
                    plantuml_text = diagram_node["plantuml"]
                    if "@startuml" in plantuml_text and "@enduml" in plantuml_text:
                        return plantuml_text
        
        # Legacy format: direct "diagram" key
        if "diagram" in obj and isinstance(obj["diagram"], dict):
            diagram_node = obj["diagram"]
            if "plantuml" in diagram_node and isinstance(diagram_node["plantuml"], str):
                plantuml_text = diagram_node["plantuml"]
                if "@startuml" in plantuml_text and "@enduml" in plantuml_text:
                    return plantuml_text
        
        # Fallback: search in common keys
        for key in ("plantuml", "uml", "content", "text"):
            val = obj.get(key)
            if isinstance(val, str) and "@startuml" in val and "@enduml" in val:
                return val
        # Recurse into all values
        for val in obj.values():
            found = find_plantuml_text(val)
            if found:
                return found
        return None
    if isinstance(obj, list):
        for item in obj:
            found = find_plantuml_text(item)
            if found:
                return found
        return None
    return None


def normalize_uml_text(text: str) -> str:
    """Normalize common escaping differences and whitespace for comparison."""
    if text is None:
        return ""
    # Normalize line endings
    norm = text.replace("\r\n", "\n").replace("\r", "\n")
    # Allow typical JSON-escaped sequences to become their literal forms
    # Do these replacements conservatively to avoid over-unescaping
    norm = norm.replace("\\n", "\n").replace("\\t", "\t").replace("\\\"", '"')
    # Remove potential BOM and trim leading/trailing whitespace
    norm = norm.lstrip('\ufeff').strip()
    # Collapse trailing spaces on each line
    norm = "\n".join(line.rstrip() for line in norm.splitlines())
    return norm


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate verbatim JSON↔.puml parity (with normal escaping allowed)")
    parser.add_argument("--json", required=True, help="Path to JSON file containing LLM output (e.g., output-data.json)")
    parser.add_argument("--puml", required=True, help="Path to saved .puml file")
    args = parser.parse_args()

    json_path = Path(args.json)
    puml_path = Path(args.puml)

    try:
        if not json_path.exists() or not puml_path.exists():
            print(f"ERROR: Input file not found. json={json_path} puml={puml_path}")
            return 2

        data = load_json(json_path)
        puml_text_file = read_text(puml_path)

        json_plantuml = find_plantuml_text(data)
        if not json_plantuml:
            print("ERROR: No PlantUML text found in JSON.")
            return 2

        lhs = normalize_uml_text(json_plantuml)
        rhs = normalize_uml_text(puml_text_file)

        if lhs == rhs:
            print("✅ Verbatim parity OK (after allowed escaping normalization)")
            return 0

        # Show a small unified-like diff context to help diagnosis (first mismatch window)
        def first_diff(a: str, b: str) -> str:
            max_ctx = 80
            for i, (ca, cb) in enumerate(zip(a, b)):
                if ca != cb:
                    start = max(0, i - max_ctx)
                    end = min(len(a), i + max_ctx)
                    seg_a = a[start:end]
                    seg_b = b[start:end]
                    return f"Diff at index {i}:\nJSON: {seg_a}\nP UML: {seg_b}"
            if len(a) != len(b):
                return f"Lengths differ: json={len(a)} puml={len(b)}"
            return "No visible diff computed"

        print("❌ Verbatim parity failed.")
        print(first_diff(lhs, rhs))
        return 1

    except Exception as e:
        print(f"ERROR: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


