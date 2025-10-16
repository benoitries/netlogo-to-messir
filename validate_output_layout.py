#!/usr/bin/env python3
"""
Validate output layout under output/runs/<YYYY-MM-DD>/<HHMM>/<combination>/.
Where <combination> is <case>-<model-name>-reason-<reasoning-value>-verb-<verbosity-value>.

- Picks the latest run by date/time unless --run <path> is provided
- Checks presence of at least one combination folder
- Checks agent step subfolders match pattern NN-<agent_id>
- Checks at least one orchestrator log file exists in the combination folder root
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
    # Only consider YYYY-MM-DD folders (ignore archives or other folders)
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    date_dirs = sorted(
        [d for d in base_runs_dir.iterdir() if d.is_dir() and date_pattern.match(d.name)],
        reverse=True,
    )
    for date_dir in date_dirs:
        # Only consider HHMM folders
        time_pattern = re.compile(r"^\d{4}$")
        time_dirs = sorted(
            [d for d in date_dir.iterdir() if d.is_dir() and time_pattern.match(d.name)],
            reverse=True,
        )
        if time_dirs:
            return time_dirs[0]
    return None


def _reasoning_md_has_non_empty_summary(md_path: Path) -> bool:
    """Return True if the markdown file has a non-empty section under '## Reasoning Summary'.

    Heuristic: find the line that equals the header, then the first non-empty
    subsequent line (ignoring whitespace). If none found before next '##' or EOF,
    consider empty. If the header is missing, consider empty.
    """
    try:
        text = md_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False

    lines = [l.rstrip("\n") for l in text.splitlines()]
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "## Reasoning Summary":
            header_idx = i
            break
    if header_idx is None:
        return False

    # scan until next section header or EOF
    for j in range(header_idx + 1, len(lines)):
        line = lines[j].strip()
        if line.startswith("## "):
            # reached next section without content
            return False
        if line != "":
            return True
    return False


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

    # Must have at least one orchestrator log file at combination root
    logs = list(case_dir.glob("*_orchestrator.log"))
    if not logs:
        errors.append(f"No orchestrator log found in {case_dir}")

    # Ensure Step 5 produced a standalone .puml file
    step5_dir = case_dir / "05-plantuml_writer"
    if step5_dir.exists() and step5_dir.is_dir():
        # Accept legacy filename pattern and new simplified name
        puml_candidates = list(step5_dir.glob("*_plantuml_writer_diagram.puml"))
        if not puml_candidates:
            puml_candidates = list(step5_dir.glob("diagram.puml"))
        if not puml_candidates:
            errors.append(f"Missing PlantUML .puml file in {step5_dir} (expected diagram.puml or legacy *_plantuml_writer_diagram.puml)")

    # Ensure Step 7 produced a corrected standalone .puml file with canonical name
    step7_dir = case_dir / "07-plantuml_messir_corrector"
    if step7_dir.exists() and step7_dir.is_dir():
        puml7 = step7_dir / "diagram.puml"
        if not puml7.exists():
            errors.append(f"Missing corrected PlantUML .puml file in {step7_dir} (expected diagram.puml)")

    # New check: all *_reasoning.md files should have non-empty Reasoning Summary section
    for step_dir in case_dir.iterdir():
        if not step_dir.is_dir():
            continue
        for md_file in step_dir.glob("*_reasoning.md"):
            if not _reasoning_md_has_non_empty_summary(md_file):
                errors.append(f"Empty Reasoning Summary in {md_file}")

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
