#!/usr/bin/env python3
"""
Scan a run directory and verify that each agent's response.json contains exactly the
expected top-level keys. Fails with non-zero exit if any mismatch is found.
"""

import sys
import json
import pathlib
from typing import Dict, Any

# Ensure repository root module path is available when invoked as a script
_SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from utils_config_constants import expected_keys_for_agent


def validate_response_file(response_path: pathlib.Path) -> str:
    try:
        data = json.loads(response_path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"{response_path}: failed to read/parse JSON: {e}"

    agent_type = data.get("agent_type")
    if not agent_type:
        return f"{response_path}: missing agent_type"

    expected = expected_keys_for_agent(agent_type)
    emitted = set(data.keys())
    missing = expected - emitted
    extra = emitted - expected
    if missing or extra:
        return f"{response_path}: keys mismatch. Missing={sorted(missing)} Extra={sorted(extra)}"

    # Soft consistency check for token fields when present
    try:
        output_tokens = int(data.get("visible_output_tokens", data.get("output_tokens", 0)) or 0)
        reasoning_tokens = int(data.get("reasoning_tokens", 0) or 0)
        total_output_tokens = data.get("total_output_tokens")
        visible_output_tokens = data.get("visible_output_tokens")

        # Derive visible when not explicitly provided
        if visible_output_tokens is None:
            derived_visible = max(output_tokens - reasoning_tokens, 0)
        else:
            derived_visible = int(visible_output_tokens)

        # If total_output_tokens is present, enforce equality
        if total_output_tokens is not None:
            total_output_tokens = int(total_output_tokens)
            if total_output_tokens != (derived_visible + reasoning_tokens):
                return (
                    f"{response_path}: total_output_tokens inconsistency: "
                    f"expected {derived_visible + reasoning_tokens}, got {total_output_tokens} "
                    f"(visible={derived_visible}, reasoning={reasoning_tokens})"
                )
    except Exception as e:
        return f"{response_path}: token consistency check failed: {e}"
    return ""


def main(argv):
    if len(argv) < 2:
        print("Usage: validate_response_jsons.py <run_dir>")
        return 2

    run_dir = pathlib.Path(argv[1])
    if not run_dir.exists():
        print(f"Run directory not found: {run_dir}")
        return 2

    errors = []
    for response_file in run_dir.rglob("output-response.json"):
        err = validate_response_file(response_file)
        if err:
            errors.append(err)

    if errors:
        print("Validation errors found:")
        for e in errors:
            print(f"- {e}")
        return 1

    print("OK: All output-response.json files have exact expected keys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))


