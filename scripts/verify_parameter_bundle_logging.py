#!/usr/bin/env python3
"""
Lightweight verifier for parameter-bundle logging consistency.

Rules validated:
- Lines that are intended to show the parameter bundle must include text_verbosity (token: "text_verbosity=").
- Non-parameter lines must not include the text_verbosity token.

Scan scope:
- By default, scans logs under the most recent run directory: output/runs/<YYYY-MM-DD>/<HHMM>/
- You can override target path via --run-dir.
"""

import argparse
import sys
import pathlib
from typing import List, Tuple


PARAM_PREFIX = "Parameters: "
VERBOSITY_TOKEN = "text_verbosity="


def find_latest_run_dir(output_root: pathlib.Path) -> pathlib.Path:
    runs_root = output_root / "runs"
    if not runs_root.exists():
        raise SystemExit(f"No runs directory found at: {runs_root}")
    date_dirs = sorted([d for d in runs_root.iterdir() if d.is_dir()], reverse=True)
    for date_dir in date_dirs:
        time_dirs = sorted([d for d in date_dir.iterdir() if d.is_dir()], reverse=True)
        if time_dirs:
            return time_dirs[0]
    raise SystemExit("No run subdirectories found under output/runs")


def collect_log_files(run_dir: pathlib.Path) -> List[pathlib.Path]:
    return sorted(list(run_dir.rglob("*.log")))


def verify_log_file(log_path: pathlib.Path) -> Tuple[int, int, List[str]]:
    """
    Returns: (num_param_lines, num_violations, violations)
    """
    violations: List[str] = []
    num_param_lines = 0
    try:
        for idx, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), start=1):
            # Treat as parameter-bundle line if it contains the marker anywhere (timestamps/prefix may precede)
            if PARAM_PREFIX in line:
                num_param_lines += 1
                if VERBOSITY_TOKEN not in line:
                    violations.append(f"{log_path}:L{idx}: parameter bundle missing '{VERBOSITY_TOKEN}'")
            else:
                if VERBOSITY_TOKEN in line:
                    violations.append(f"{log_path}:L{idx}: non-parameter line contains '{VERBOSITY_TOKEN}'")
    except Exception as e:
        violations.append(f"{log_path}: failed to read: {e}")
    return num_param_lines, len(violations), violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify parameter-bundle logging consistency")
    parser.add_argument("--output-root", default=str(pathlib.Path(__file__).resolve().parents[1] / "output"), help="Path to output root (default: ../output)")
    parser.add_argument("--run-dir", default=None, help="Optional explicit run directory (overrides latest detection)")
    args = parser.parse_args()

    output_root = pathlib.Path(args.output_root).resolve()
    if args.run_dir:
        run_dir = pathlib.Path(args.run_dir).resolve()
    else:
        run_dir = find_latest_run_dir(output_root)

    log_files = collect_log_files(run_dir)
    if not log_files:
        print(f"No .log files found under: {run_dir}")
        return 1

    total_param_lines = 0
    total_violations = 0
    all_violations: List[str] = []

    for log_path in log_files:
        num_param_lines, num_file_violations, violations = verify_log_file(log_path)
        total_param_lines += num_param_lines
        total_violations += num_file_violations
        all_violations.extend(violations)

    print(f"Scanned {len(log_files)} log files under: {run_dir}")
    print(f"Parameter bundle lines: {total_param_lines}")
    if total_violations == 0:
        print("OK: All parameter bundle lines include text_verbosity; non-parameter lines are clean.")
        return 0
    else:
        print(f"ERROR: Found {total_violations} violation(s):")
        for v in all_violations:
            print(f" - {v}")
        return 2


if __name__ == "__main__":
    sys.exit(main())


