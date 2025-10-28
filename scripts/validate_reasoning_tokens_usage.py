#!/usr/bin/env python3
"""
Validate that recent agent outputs include a canonical reasoning_tokens value.

This script scans output-response.json files under code-netlogo-to-lucim-agentic-workflow/output/runs/
and checks that each JSON has an integer field reasoning_tokens (>= 0), and that
usage was extracted consistently. It prints a summary report and a non-zero exit
code if any violations are found.

Usage:
  python code-netlogo-to-lucim-agentic-workflow/scripts/validate_reasoning_tokens_usage.py [--root <path>] [--limit N]

Defaults:
  --root defaults to code-netlogo-to-lucim-agentic-workflow/output/runs
  --limit limits the number of files inspected (most recently modified)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple


def find_output_response_files(root: Path) -> List[Path]:
    if not root.exists():
        return []
    return list(root.rglob("output-response.json"))


def validate_file(path: Path) -> Tuple[bool, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"Invalid JSON: {e}"

    # Basic shape checks
    if not isinstance(data, dict):
        return False, "Top-level JSON is not an object"

    # Check reasoning_tokens presence and type
    rt = data.get("reasoning_tokens")
    if not isinstance(rt, int) or rt < 0:
        return False, f"reasoning_tokens invalid (expected non-negative int), got: {rt!r}"

    # Optional: cross-check total/input/output if present
    it = data.get("input_tokens")
    ot = data.get("output_tokens")
    tt = data.get("tokens_used")
    # Only check basic types; exact sums can vary if API omitted some fields
    for key, val in ("input_tokens", it), ("output_tokens", ot), ("tokens_used", tt):
        if val is not None and not isinstance(val, int):
            return False, f"{key} must be int when present, got: {val!r}"

    return True, "OK"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate reasoning_tokens presence and value in outputs")
    default_root = Path(__file__).resolve().parents[1] / "output" / "runs"
    parser.add_argument("--root", default=str(default_root), help="Root directory to scan")
    parser.add_argument("--limit", type=int, default=200, help="Max files to inspect (most recent first)")
    args = parser.parse_args()

    root = Path(args.root)
    files = find_output_response_files(root)
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if args.limit and args.limit > 0:
        files = files[: args.limit]

    total = len(files)
    if total == 0:
        print(f"No output-response.json files found under {root}")
        return 0

    failures = 0
    for f in files:
        ok, msg = validate_file(f)
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {f}: {msg}")
        if not ok:
            failures += 1

    print("\nSummary:")
    print(f"  Files inspected: {total}")
    print(f"  Failures:       {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())




