#!/usr/bin/env python3
"""
Validate that reasoning.md files include all available API reasoning fields.

Rules:
- For each stage output directory containing output-response.json and output-reasoning.md,
  if a reasoning-related field is present in response.json (or derived payload),
  the reasoning.md must include the corresponding section heading.
- Missing sections are allowed only when the corresponding data is absent.

Usage:
  python code-netlogo-to-lucim-agentic-workflow/validate_reasoning_markdown.py --runs-root code-netlogo-to-lucim-agentic-workflow/output/runs

Exit codes:
  0: All validations passed
  1: Validation failures found
  2: Unexpected error (e.g., IO)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List


SECTION_MAP = {
    "reasoning": "## Reasoning",
    "reasoning_summary": "## Reasoning Summary",
    "step_trace": "## Step Trace",
    "tool_justifications": "## Tool Justifications",
    "token_usage": "## Token Usage (Reasoning)",
    "errors": "## Errors",
    "raw_payload": "## Raw Reasoning Payload",
}


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"Failed to load JSON {path}: {e}")


def discover_stage_dirs(runs_root: Path) -> List[Path]:
    stage_dirs: List[Path] = []
    if not runs_root.exists():
        return stage_dirs
    # We expect structure: runs/YYYY-MM-DD/HHMM/<combo>/**/<NN-stage>/
    for date_dir in runs_root.iterdir():
        if not date_dir.is_dir():
            continue
        for time_dir in date_dir.iterdir():
            if not time_dir.is_dir():
                continue
            for combo_dir in time_dir.iterdir():
                if not combo_dir.is_dir():
                    continue
                for stage_dir in combo_dir.iterdir():
                    if stage_dir.is_dir() and stage_dir.name[:2].isdigit():
                        stage_dirs.append(stage_dir)
    return stage_dirs


def has_section(md_text: str, heading: str) -> bool:
    return heading in md_text


def build_payload_from_response(response_json: Dict[str, Any]) -> Dict[str, Any]:
    # Normalize fields similarly to write_reasoning_md_from_payload
    payload: Dict[str, Any] = {}
    # Common top-level fields that may be present in our complete_response/results
    for key in ("reasoning", "reasoning_summary", "tokens_used", "input_tokens", "output_tokens", "reasoning_tokens", "errors"):
        if key in response_json:
            payload[key] = response_json.get(key)
    # Sometimes the actual payload lives under a different key; we include as raw when present
    if "raw_usage" in response_json:
        payload["usage"] = response_json.get("raw_usage")
    return payload


def validate_stage(stage_dir: Path) -> List[str]:
    errors: List[str] = []
    response_path = stage_dir / "output-response.json"
    reasoning_md_path = stage_dir / "output-reasoning.md"

    if not response_path.exists() or not reasoning_md_path.exists():
        # If either is missing, skip quietly; other validators check layout
        return errors

    response_data = load_json(response_path)
    md_text = reasoning_md_path.read_text(encoding="utf-8")
    payload = build_payload_from_response(response_data)

    # Validate presence of sections only when data is available
    if payload.get("reasoning") is not None and not has_section(md_text, SECTION_MAP["reasoning"]):
        errors.append(f"Missing section '{SECTION_MAP['reasoning']}' in {reasoning_md_path}")
    if payload.get("reasoning_summary") is not None and not has_section(md_text, SECTION_MAP["reasoning_summary"]):
        errors.append(f"Missing section '{SECTION_MAP['reasoning_summary']}' in {reasoning_md_path}")
    # Token usage presence: consider either flat or nested usage
    has_any_usage = any(k in payload for k in ("tokens_used", "input_tokens", "output_tokens", "reasoning_tokens", "usage"))
    if has_any_usage and not has_section(md_text, SECTION_MAP["token_usage"]):
        errors.append(f"Missing section '{SECTION_MAP['token_usage']}' in {reasoning_md_path}")
    if payload.get("errors") and not has_section(md_text, SECTION_MAP["errors"]):
        errors.append(f"Missing section '{SECTION_MAP['errors']}' in {reasoning_md_path}")
    # Raw payload section is always expected because writer includes it when any payload exists
    if response_data and not has_section(md_text, SECTION_MAP["raw_payload"]):
        errors.append(f"Missing section '{SECTION_MAP['raw_payload']}' in {reasoning_md_path}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate reasoning.md contains all available API reasoning fields")
    parser.add_argument("--runs-root", required=True, help="Path to runs root directory (e.g., code-netlogo-to-lucim-agentic-workflow/output/runs)")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    failures: List[str] = []

    try:
        for stage_dir in discover_stage_dirs(runs_root):
            failures.extend(validate_stage(stage_dir))
    except Exception as e:
        print(f"[ERROR] Validation failed due to unexpected error: {e}")
        return 2

    if failures:
        print("Validation failures:")
        for f in failures:
            print(f"- {f}")
        return 1

    print("OK: All reasoning.md files are compliant with available reasoning fields.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


