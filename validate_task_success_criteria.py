#!/usr/bin/env python3
"""
Validate task success criteria formatting in ai_docs/tasks/*.md.

Rules validated:
1) Checked criteria lines MUST start with "- ✅ " (green check at start)
2) Checked criteria lines MUST end with " — YYYY-MM-DD HH:mm (local time)"

Exit codes:
 - 0: All good
 - 1: Violations found
 - 2: Unexpected error
"""

import re
import sys
from pathlib import Path


TASKS_DIR = Path(__file__).resolve().parents[1] / "ai_docs" / "tasks"

# Pattern for a checked criterion line with required timestamp suffix
CHECKED_PREFIX = "- ✅ "
TIMESTAMP_REGEX = re.compile(r"\s—\s\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}\s\(local time\)\s*$")


def validate_task_file(path: Path) -> list:
    """Return list of violation strings for a single task file."""
    violations = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        return [f"ERROR reading {path.name}: {exc}"]

    for idx, line in enumerate(lines, start=1):
        if line.strip().startswith(CHECKED_PREFIX):
            # Must end with timestamp
            if not TIMESTAMP_REGEX.search(line):
                violations.append(
                    f"{path.name}:{idx}: checked criterion missing end-of-line timestamp '— YYYY-MM-DD HH:mm (local time)'"
                )

    return violations


def main() -> int:
    if not TASKS_DIR.exists():
        print(f"ERROR: Tasks directory not found: {TASKS_DIR}")
        return 2

    all_md = sorted(TASKS_DIR.glob("*.md"))
    total = 0
    all_violations = []
    for md in all_md:
        total += 1
        all_violations.extend(validate_task_file(md))

    if all_violations:
        print("Task Success Criteria Validation — FAIL")
        for v in all_violations:
            print(f" - {v}")
        print(f"Total files scanned: {total}")
        print(f"Violations: {len(all_violations)}")
        return 1

    print("Task Success Criteria Validation — OK")
    print(f"Total files scanned: {total}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: Unexpected exception: {exc}")
        sys.exit(2)


