#!/usr/bin/env python3
"""
Validate output layout under output/runs/<YYYY-MM-DD>/<HHMM>/<case>/.
- Picks the latest run by date/time unless --run <path> is provided
- Checks presence of at least one case folder
- Checks agent step subfolders match pattern NN-<agent_id>
- Checks at least one orchestrator log file exists in the case folder
Exits with non-zero code on validation failure.
"""

import sys
import re
from pathlib import Path
from typing import Optional, List

from config import OUTPUT_DIR

STEP_DIR_REGEX = re.compile(r"^\d{2}-[a-z_]+$")


def find_latest_run(base_runs_dir: Path) -> Optional[Path]:
    if not base_runs_dir.exists():
        return None
    date_dirs = sorted(
        [d for d in base_runs_dir.iterdir() if d.is_dir()],
        reverse=True,
    )
    for date_dir in date_dirs:
        time_dirs = sorted(
            [d for d in date_dir.iterdir() if d.is_dir()],
            reverse=True,
        )
        if time_dirs:
            return time_dirs[0]
    return None


def validate_case_folder(case_dir: Path) -> List[str]:
    errors: List[str] = []
    # Must contain NN-agent_id subfolders
    step_dirs = [d for d in case_dir.iterdir() if d.is_dir()]
    if not step_dirs:
        errors.append(f"No step subfolders found in case folder: {case_dir}")
    else:
        bad = [d.name for d in step_dirs if not STEP_DIR_REGEX.match(d.name)]
        if bad:
            errors.append(
                f"Found non-conforming step folders in {case_dir.name}: {', '.join(bad)}"
            )

    # Must have at least one orchestrator log file at case root
    logs = list(case_dir.glob("*_orchestrator.log"))
    if not logs:
        errors.append(f"No orchestrator log found in {case_dir}")

    return errors


def main() -> int:
    # Canonical base: OUTPUT_DIR / "runs" / YYYY-MM-DD / HHMM / <case>
    runs_root = OUTPUT_DIR / "runs"

    # Optional argument: explicit run path
    run_arg: Optional[str] = None
    if len(sys.argv) > 1 and sys.argv[1] != "--help":
        run_arg = sys.argv[1]

    run_path = Path(run_arg).resolve() if run_arg else find_latest_run(runs_root)

    if run_path is None or not run_path.exists():
        print(f"ERROR: No run folder found under {runs_root}."
              f" You can provide a run path explicitly.")
        return 2

    print(f"Validating run: {run_path}")

    # Expect at least one case folder under run_path
    case_dirs = [d for d in run_path.iterdir() if d.is_dir()]
    if not case_dirs:
        print(f"ERROR: No case folders found in run path: {run_path}")
        return 3

    errors: List[str] = []
    for case_dir in case_dirs:
        errors.extend(validate_case_folder(case_dir))

    if errors:
        print("Validation FAILED:")
        for err in errors:
            print(f" - {err}")
        return 4

    print("Validation OK: output layout matches expected structure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
