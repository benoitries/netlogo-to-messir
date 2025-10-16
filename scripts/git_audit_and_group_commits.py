#!/usr/bin/env python3
"""
CLI to audit working tree changes, propose grouped commits, request human approval,
and perform the corresponding git commits. Artifacts are persisted under
output/runs/<YYYY-MM-DD>/<HHMM>/overall/ (relative to the repository root).

Usage examples:
  - Dry-run audit & plan only (no staging/committing):
      python code-netlogo-to-messir/scripts/git_audit_and_group_commits.py --dry-run

  - Propose groups by directory and ask for approval interactively:
      python code-netlogo-to-messir/scripts/git_audit_and_group_commits.py --grouping directory

  - Auto-approve the proposed plan (non-interactive environments):
      python code-netlogo-to-messir/scripts/git_audit_and_group_commits.py --yes

Notes:
  - Requires running inside a git repository with a clean index or with changes to audit.
  - Does not rewrite history. Commits are additive and grouped by the chosen strategy.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


# ----------------------------- Filesystem Helpers -----------------------------


def get_repo_root() -> Path:
    try:
        out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True)
        return Path(out.strip())
    except subprocess.CalledProcessError as exc:
        print("Error: Not a git repository (or git not available).", file=sys.stderr)
        raise exc


def get_run_output_dir(repo_root: Path) -> Path:
    now = datetime.now()
    date_part = now.strftime("%Y-%m-%d")
    time_part = now.strftime("%H%M")
    dir_path = repo_root / "output" / "runs" / date_part / time_part / "overall"
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


# --------------------------------- Git Utils ---------------------------------


def run_git_command(args: List[str]) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(["git", *args], check=False, capture_output=True, text=True)
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return 127, "", "git not found"


def list_changed_files(base_ref: str) -> List[str]:
    # Include staged and unstaged changes relative to index/working tree.
    # We combine:
    #  - `git diff --name-only` for unstaged
    #  - `git diff --name-only --cached` for staged
    #  - `git ls-files --others --exclude-standard` for untracked
    files: List[str] = []

    for args in (
        ["diff", "--name-only"],
        ["diff", "--name-only", "--cached"],
        ["ls-files", "--others", "--exclude-standard"],
    ):
        code, out, _ = run_git_command(args)
        if code == 0 and out:
            files.extend(line for line in out.splitlines() if line.strip())

    # Deduplicate while preserving order
    seen = set()
    unique_files: List[str] = []
    for f in files:
        if f not in seen:
            unique_files.append(f)
            seen.add(f)
    return unique_files


# ------------------------------- Grouping Logic -------------------------------


class GroupingStrategy:
    DIRECTORY = "directory"
    EXTENSION = "ext"
    MODULE = "module"  # Heuristic: top-level folder or stem prefix
    TASK = "task"       # Group by ai_docs/tasks/NNN-*.md (maps to dashboard short name)


def load_task_labels(repo_root: Path) -> Dict[str, str]:
    """Parse ai_docs/tasks/TASK-DASHBOARD.md to map NNN -> short name.
    Expected line format: "NNN — <emoji> — <short name> — <status> — ..."
    """
    dashboard = repo_root / "ai_docs" / "tasks" / "TASK-DASHBOARD.md"
    labels: Dict[str, str] = {}
    if not dashboard.exists():
        return labels
    try:
        for line in dashboard.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^(\d{3})\s+—\s+.+?—\s+(.+?)\s+—\s+", line)
            if m:
                labels[m.group(1)] = m.group(2)
    except Exception:
        pass
    return labels


def group_files(files: List[str], strategy: str, repo_root: Path | None = None) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = defaultdict(list)
    task_labels: Dict[str, str] = {}
    if strategy == GroupingStrategy.TASK and repo_root is not None:
        task_labels = load_task_labels(repo_root)
    for path in files:
        key = "misc"
        if strategy == GroupingStrategy.DIRECTORY:
            parts = Path(path).parts
            key = parts[0] if len(parts) > 1 else "root"
        elif strategy == GroupingStrategy.EXTENSION:
            key = Path(path).suffix or "no-ext"
        elif strategy == GroupingStrategy.MODULE:
            parts = Path(path).parts
            key = parts[0] if parts else "misc"
        elif strategy == GroupingStrategy.TASK:
            # Detect ai_docs/tasks/NNN-*.md
            m = re.match(r"^ai_docs/tasks/(\d{3})-", path)
            if m:
                num = m.group(1)
                label = task_labels.get(num, "")
                key = f"task-{num}{(' ' + label) if label else ''}"
            else:
                key = "no-task"
        else:
            key = "all"
        grouped[key].append(path)
    return dict(grouped)


# --------------------------------- Data Model --------------------------------


@dataclasses.dataclass
class ProposedGroup:
    name: str
    files: List[str]
    rationale: str


@dataclasses.dataclass
class AuditPlan:
    grouping_strategy: str
    groups: List[ProposedGroup]
    total_files: int


def build_audit_plan(files: List[str], strategy: str, repo_root: Path | None = None) -> AuditPlan:
    grouped = group_files(files, strategy, repo_root=repo_root)
    groups: List[ProposedGroup] = []
    for name, members in sorted(grouped.items(), key=lambda kv: kv[0]):
        rationale = f"Grouped by {strategy}: bucket '{name}' contains {len(members)} file(s)."
        groups.append(ProposedGroup(name=name, files=sorted(members), rationale=rationale))
    return AuditPlan(grouping_strategy=strategy, groups=groups, total_files=len(files))


# ------------------------------ Persistence Layer -----------------------------


def persist_artifacts(out_dir: Path, plan: AuditPlan) -> Path:
    json_path = out_dir / "git_audit_plan.json"
    md_path = out_dir / "git_audit_plan.md"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "grouping_strategy": plan.grouping_strategy,
                "total_files": plan.total_files,
                "groups": [dataclasses.asdict(g) for g in plan.groups],
                "generated_at": datetime.now().isoformat(),
            },
            f,
            indent=2,
        )

    with md_path.open("w", encoding="utf-8") as f:
        f.write(f"# Git Audit Plan\n\n")
        f.write(f"- Grouping strategy: {plan.grouping_strategy}\n")
        f.write(f"- Total files: {plan.total_files}\n")
        f.write(f"- Generated at: {datetime.now().isoformat()}\n\n")
        for group in plan.groups:
            f.write(f"## Group: {group.name}\n")
            f.write(f"- Rationale: {group.rationale}\n")
            f.write("- Files:\n")
            for path in group.files:
                f.write(f"  - {path}\n")
            f.write("\n")

    return json_path


# ---------------------------- Approval & Commit Flow --------------------------


def prompt_user_selection(plan: AuditPlan) -> List[ProposedGroup]:
    print("Proposed commit groups:", file=sys.stdout)
    for idx, group in enumerate(plan.groups, 1):
        print(f"  [{idx}] {group.name} — {len(group.files)} file(s)")
    print()
    print("Enter the group numbers to commit, separated by commas (e.g., 1,3,4). Press Enter to select all, or type 'none' to cancel:")
    selection = input("> ").strip()
    if selection.lower() in {"none", "n", "no"}:
        return []
    if not selection:
        return plan.groups
    try:
        indices = {int(x.strip()) for x in selection.split(",") if x.strip()}
    except ValueError:
        print("Invalid selection. Aborting.", file=sys.stderr)
        return []
    chosen: List[ProposedGroup] = []
    for i, group in enumerate(plan.groups, 1):
        if i in indices:
            chosen.append(group)
    return chosen


def stage_and_commit(group: ProposedGroup, dry_run: bool) -> Tuple[bool, str]:
    if dry_run:
        return True, f"[DRY-RUN] Would commit group '{group.name}' with {len(group.files)} file(s)."

    # Stage files
    code, _, err = run_git_command(["add", *group.files])
    if code != 0:
        return False, f"Failed to stage files for group '{group.name}': {err.strip()}"

    # Commit
    message = f"chore(commit-group): {group.name} — {len(group.files)} file(s)"
    code, out, err = run_git_command(["commit", "-m", message])
    if code != 0:
        return False, f"Failed to commit group '{group.name}': {err.strip()}"
    return True, out.strip() or message


# ------------------------------------ Main -----------------------------------


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit, propose, approve, and commit grouped git changes.")
    parser.add_argument("--grouping", choices=[
        GroupingStrategy.DIRECTORY,
        GroupingStrategy.EXTENSION,
        GroupingStrategy.MODULE,
        GroupingStrategy.TASK,
    ], default=GroupingStrategy.DIRECTORY, help="Grouping strategy for proposed commits.")
    parser.add_argument("--dry-run", action="store_true", help="Do not stage or commit; only produce audit artifacts and console plan.")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-approve all proposed groups (non-interactive mode).")
    parser.add_argument("--base-ref", default="HEAD", help="Base ref (reserved for future diff strategies; currently informational).")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    repo_root = get_repo_root()
    out_dir = get_run_output_dir(repo_root)

    changed_files = list_changed_files(args.base_ref)
    if not changed_files:
        print("No changes detected. Nothing to plan.")
        return 0

    plan = build_audit_plan(changed_files, args.grouping, repo_root=repo_root)
    plan_path = persist_artifacts(out_dir, plan)
    print(f"Audit plan persisted to: {plan_path}")

    chosen_groups: List[ProposedGroup]
    if args.yes:
        chosen_groups = plan.groups
        print("Auto-approved all groups due to --yes flag.")
    else:
        chosen_groups = prompt_user_selection(plan)
    if not chosen_groups:
        print("No groups selected. Exiting without changes.")
        return 0

    any_failures = False
    for group in chosen_groups:
        ok, msg = stage_and_commit(group, args.dry_run)
        print(msg)
        if not ok:
            any_failures = True

    if args.dry_run:
        print("Dry-run completed. No changes were made to the repository.")
    elif any_failures:
        print("Completed with some failures. Review messages above.")
    else:
        print("All selected groups committed successfully.")
    return 0 if not any_failures else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


