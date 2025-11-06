#!/usr/bin/env python3
"""
Validate presence of renamed artifacts per stage directory.

Checks for:
- output-response-full.json
- output-data.json (when data exists)
- output-reasoning.md
- output-response-raw.json
- input-instructions.md

Usage:
  python code-netlogo-to-lucim-agentic-workflow/scripts/validate_artifact_presence.py --runs-root code-netlogo-to-lucim-agentic-workflow/output/runs
"""

import argparse
from pathlib import Path
from typing import List

REQUIRED_ALWAYS = [
    "output-response-full.json",
    "output-reasoning.md",
    "output-response-raw.json",
    "input-instructions.md",
]

# output-data.json is conditionally required only if it exists; presence is optional
# This validator will not fail if output-data.json is missing.


def discover_stage_dirs(runs_root: Path) -> List[Path]:
    stage_dirs: List[Path] = []
    if not runs_root.exists():
        return stage_dirs
    for date_dir in runs_root.iterdir():
        if not date_dir.is_dir():
            continue
        for time_dir in date_dir.iterdir():
            if not time_dir.is_dir():
                continue
            for combo_dir in time_dir.iterdir():
                if not combo_dir.is_dir():
                    continue
                # Skip nothing at combination level; overall summaries live at run root as files, not folders
                for stage_dir in combo_dir.iterdir():
                    if stage_dir.is_dir() and stage_dir.name[:2].isdigit():
                        stage_dirs.append(stage_dir)
    return stage_dirs


def validate_stage(stage_dir: Path) -> List[str]:
    errors: List[str] = []
    for fname in REQUIRED_ALWAYS:
        if not (stage_dir / fname).exists():
            errors.append(f"Missing {fname} in {stage_dir}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate presence of renamed artifacts per stage")
    parser.add_argument("--runs-root", required=True, help="Path to runs root directory (e.g., code-netlogo-to-lucim-agentic-workflow/output/runs)")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    failures: List[str] = []
    for stage in discover_stage_dirs(runs_root):
        failures.extend(validate_stage(stage))
    if failures:
        print("Artifact presence validation failures:")
        for f in failures:
            print(f"- {f}")
        return 1
    print("OK: All required artifacts are present in each stage directory.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
