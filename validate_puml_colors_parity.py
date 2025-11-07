#!/usr/bin/env python3
"""
Validate parity of activation color tokens between JSON payload (LLM output)
and the saved PlantUML (.puml) file.

Usage:
  python validate_puml_colors_parity.py --json path/to/output-data.json --puml path/to/diagram.puml

Exit codes:
  0 -> parity OK
  1 -> parity failed (missing colors in .puml)
  2 -> invalid inputs / runtime error
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Optional, Set


HEX_COLOR_RE = re.compile(r"#[0-9A-Fa-f]{6}")


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


def extract_hex_colors(text: str) -> Set[str]:
    return set(HEX_COLOR_RE.findall(text or ""))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate JSON↔.puml activation color parity")
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
        puml_text = read_text(puml_path)

        json_plantuml = find_plantuml_text(data)
        if not json_plantuml:
            print("ERROR: No PlantUML text found in JSON.")
            return 2

        json_colors = extract_hex_colors(json_plantuml)
        puml_colors = extract_hex_colors(puml_text)

        missing = sorted(list(json_colors - puml_colors))
        if missing:
            print("❌ Parity failed: missing color tokens in .puml")
            for c in missing:
                print(f"   - {c}")
            return 1

        print("✅ Parity OK: all JSON color tokens found in .puml")
        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


