#!/usr/bin/env python3
"""
Validate Agent 2a (Interface Image Analyzer) widget output against schema and basic rules.

Usage:
  python validate_2a_widget_output.py --output-dir <02a-interface_image_analyzer dir> [--schema <schema.json>]

Defaults:
  - If --schema is omitted, attempts to use experimentation/templates/agent_2a_widget_schema.json
  - Exits with code 0 on success, 1 on validation failure or IO error
"""

import argparse
import json
import sys
from pathlib import Path


def load_schema(schema_path: Path) -> dict:
    try:
        return json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"Failed to load schema from {schema_path}: {e}")


def validate_against_schema(data, schema) -> list:
    try:
        import jsonschema
    except ImportError:
        return [
            "jsonschema is required for validation. Install with: pip install jsonschema"
        ]

    errors = []
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        errors.append(f"Schema validation error: {e.message}")
        if e.path:
            errors.append("Path: " + " -> ".join(str(p) for p in e.path))
    except Exception as e:
        errors.append(f"Validation error: {e}")
    return errors


ALLOWED_TYPES = {
    "Button", "Slider", "Switch", "Chooser", "Input", "Monitor", "Plot", "Output", "Note"
}


def validate_business_rules(widgets) -> list:
    errs = []
    if not isinstance(widgets, list):
        return ["Top-level widgets must be a list"]

    for idx, w in enumerate(widgets):
        if not isinstance(w, dict):
            errs.append(f"Item {idx}: not an object")
            continue
        t = (w.get("type") or "").strip()
        n = (w.get("name") or "").strip()
        d = (w.get("description") or "").strip()
        if not t or not n or not d:
            errs.append(f"Item {idx}: missing required non-empty fields (type/name/description)")
        if t and t not in ALLOWED_TYPES:
            errs.append(f"Item {idx}: invalid type '{t}'")
    return errs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, help="Path to 02a-interface_image_analyzer output directory")
    parser.add_argument("--schema", help="Path to schema JSON (optional)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.exists():
        print(f"ERROR: Output directory not found: {output_dir}")
        sys.exit(1)

    # Locate output-data.json (preferred) or <base>_output_data.json fallback
    data_path = output_dir / "output-data.json"
    if not data_path.exists():
        # Fallback: find any *_output_data.json
        candidates = list(output_dir.glob("*_output_data.json"))
        if candidates:
            data_path = candidates[0]
    if not data_path.exists():
        print(f"ERROR: Could not find output-data.json in {output_dir}")
        sys.exit(1)

    # Load data
    try:
        payload = json.loads(data_path.read_text(encoding="utf-8"))
        # Support both top-level array and {"widgets": [...]}
        if isinstance(payload, list):
            widgets = payload
        elif isinstance(payload, dict):
            widgets = payload.get("widgets", [])
        else:
            widgets = []
    except Exception as e:
        print(f"ERROR: Failed to read widget data: {e}")
        sys.exit(1)

    # Resolve schema
    if args.schema:
        schema_path = Path(args.schema)
    else:
        # Default to experimentation/templates location
        repo_root = Path(__file__).resolve().parents[1]
        schema_path = repo_root / "experimentation" / "templates" / "agent_2a_widget_schema.json"

    if not schema_path.exists():
        print(f"ERROR: Schema file not found: {schema_path}")
        sys.exit(1)

    try:
        schema = load_schema(schema_path)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Run validations
    schema_errors = validate_against_schema(widgets, schema)
    rule_errors = validate_business_rules(widgets)
    all_errors = schema_errors + rule_errors

    if all_errors:
        print("✗ Agent 2a widget output validation FAILED:")
        for e in all_errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✓ Agent 2a widget output is valid")
        sys.exit(0)


if __name__ == "__main__":
    main()


