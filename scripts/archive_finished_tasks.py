#!/usr/bin/env python3
"""
Archive finished task files by moving them from ai_docs/tasks/ to ai_docs/tasks/tasks-done/.

Features:
- Dry-run by default; use --apply to perform changes.
- Detects "finished" by verifying all Success Criteria are checked (✅) and timestamped.
- Updates TASK-DASHBOARD.md status to FINISHED and synchronizes the last-change timestamp.
- Idempotent: re-running after move does nothing for already-archived files.
- Optionally filter by task number.

This script performs a real move (rename) without delete/recreate.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


RE_CHECKED = re.compile(r"^\s*[-*]\s*✅\s+.*?\s—\s\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}\s\(local time\)\s*$")
RE_CRITERIA_ITEM = re.compile(r"^\s*[-*]\s+.*")
RE_TIMESTAMP_CAPTURE = re.compile(r"(\d{4}-\d{2}-\d{2})\s(\d{2}):(\d{2})\s\(local time\)")


@dataclass
class TaskInfo:
    number: str
    file_path: Path
    short_name: str
    is_finished: bool
    last_change_local: Optional[datetime]


def find_repo_root() -> Path:
    # scripts/ is under code-netlogo-to-lucim-agentic-workflow/scripts, repo root is two levels up
    return Path(__file__).resolve().parents[2]


def normalize_short_title_from_filename(filename: str) -> str:
    # Strip numeric prefix and extension, keep a concise title from slug
    stem = Path(filename).stem
    parts = stem.split("-", 1)
    if len(parts) == 2:
        title_slug = parts[1]
    else:
        title_slug = stem
    # Replace dashes with spaces and capitalize lightly
    return title_slug.replace("-", " ").strip()


def extract_success_criteria_section(lines: List[str]) -> List[str]:
    in_section = False
    collected: List[str] = []
    for line in lines:
        if not in_section and line.strip().lower().startswith("## success criteria"):
            in_section = True
            continue
        if in_section:
            if line.strip().startswith("## "):
                break
            collected.append(line.rstrip("\n"))
    return collected


def is_task_finished_and_last_timestamp(criteria_lines: List[str]) -> Tuple[bool, Optional[datetime]]:
    # Consider only bullet items as criteria; ignore empty lines
    items = [ln for ln in criteria_lines if ln.strip() and RE_CRITERIA_ITEM.match(ln)]
    if not items:
        return False, None
    # All items must be checked and timestamped
    for ln in items:
        if not RE_CHECKED.match(ln):
            return False, None
    # Extract latest timestamp across items
    latest: Optional[datetime] = None
    for ln in items:
        m = RE_TIMESTAMP_CAPTURE.search(ln)
        if m:
            dt = datetime.strptime(f"{m.group(1)} {m.group(2)}:{m.group(3)}", "%Y-%m-%d %H:%M")
            if latest is None or dt > latest:
                latest = dt
    return True, latest


def discover_tasks(tasks_dir: Path) -> List[TaskInfo]:
    results: List[TaskInfo] = []
    for md_path in sorted(tasks_dir.glob("*.md")):
        if md_path.name == "TASK-DASHBOARD.md":
            continue
        # Require numeric prefix
        if "-" not in md_path.stem:
            continue
        num = md_path.stem.split("-", 1)[0]
        if not num.isdigit() or len(num) < 1:
            continue
        short_title = normalize_short_title_from_filename(md_path.name)
        lines = md_path.read_text(encoding="utf-8").splitlines()
        criteria = extract_success_criteria_section(lines)
        is_finished, last_ts = is_task_finished_and_last_timestamp(criteria)
        results.append(TaskInfo(number=num.zfill(3), file_path=md_path, short_name=short_title, is_finished=is_finished, last_change_local=last_ts))
    return results


def format_dashboard_timestamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d at %H-%M")


def update_dashboard_line(line: str, number: str, short_name: str, last_change: datetime) -> str:
    # Ensure single-line format with FINISHED status and updated timestamp.
    # Expected pattern: "NNN — <emoji> — <short> — <STATUS> — last change YYYY-MM-DD at HH-MM"
    # We'll replace status and trailing timestamp while preserving the beginning prefix.
    # If the line lacks segments, reconstruct minimally.
    parts = [seg.strip() for seg in line.strip().split("—")]
    if not parts or not parts[0].strip().startswith(number):
        # Rebuild entirely
        return f"{number} — ✅ — {short_name} — FINISHED — last change {format_dashboard_timestamp(last_change)}"

    # Try to preserve the short name if present; otherwise use provided
    new_short = short_name
    if len(parts) >= 3 and parts[2]:
        new_short = parts[2]

    return f"{number} — ✅ — {new_short} — FINISHED — last change {format_dashboard_timestamp(last_change)}"


def apply_dashboard_update(dashboard_path: Path, task: TaskInfo, dry_run: bool) -> None:
    if task.last_change_local is None:
        return
    if not dashboard_path.exists():
        # Create minimal dashboard with a single line if missing
        new_line = update_dashboard_line("", task.number, task.short_name, task.last_change_local)
        msg = f"[dashboard] add: {new_line}"
        print(msg)
        if not dry_run:
            dashboard_path.write_text(new_line + "\n", encoding="utf-8")
        return

    lines = dashboard_path.read_text(encoding="utf-8").splitlines()
    updated = False
    for idx, line in enumerate(lines):
        if line.strip().startswith(task.number):
            new_line = update_dashboard_line(line, task.number, task.short_name, task.last_change_local)
            if new_line != line:
                print(f"[dashboard] update: {line} -> {new_line}")
                if not dry_run:
                    lines[idx] = new_line
            updated = True
            break
    if not updated:
        new_line = update_dashboard_line("", task.number, task.short_name, task.last_change_local)
        print(f"[dashboard] append: {new_line}")
        if not dry_run:
            lines.append(new_line)
    if not dry_run:
        dashboard_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def move_task_file(task: TaskInfo, tasks_done_dir: Path, dry_run: bool) -> Optional[Path]:
    target = tasks_done_dir / task.file_path.name
    if target.exists():
        print(f"[move] already archived: {target}")
        return target
    print(f"[move] {task.file_path} -> {target}")
    if not dry_run:
        tasks_done_dir.mkdir(parents=True, exist_ok=True)
        os.replace(task.file_path, target)
    return target


def warn_links_update(old_path: Path, new_path: Path) -> None:
    # Basic reminder to update links; comprehensive repo-wide relink is out of scope here.
    print(f"[links] Reminder: update references from '{old_path}' to '{new_path}' if any.")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive finished tasks (move to tasks-done and update dashboard)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    mode.add_argument("--dry-run", action="store_true", help="Dry-run only (default)")
    parser.add_argument("--number", "-n", type=str, help="Filter by task number (e.g., 052)")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    dry_run = not args.apply

    repo_root = find_repo_root()
    tasks_dir = repo_root / "ai_docs" / "tasks"
    tasks_done_dir = tasks_dir / "tasks-done"
    dashboard_path = tasks_dir / "TASK-DASHBOARD.md"

    if not tasks_dir.exists():
        print(f"[error] tasks directory not found: {tasks_dir}", file=sys.stderr)
        return 2

    all_tasks = discover_tasks(tasks_dir)
    if args.number:
        sel = args.number.zfill(3)
        all_tasks = [t for t in all_tasks if t.number == sel]

    finished = [t for t in all_tasks if t.is_finished]
    if not finished:
        print("[info] No finished tasks detected.")
        return 0

    for task in finished:
        # Move file
        new_path = move_task_file(task, tasks_done_dir, dry_run=dry_run)
        if new_path is not None:
            warn_links_update(task.file_path, new_path)
        # Update dashboard
        apply_dashboard_update(dashboard_path, task, dry_run=dry_run)

    if dry_run:
        print("[summary] Dry-run complete. Re-run with --apply to perform changes.")
    else:
        print("[summary] Apply complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


