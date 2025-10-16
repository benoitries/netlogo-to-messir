# Grouped Git Commits — Audit, Plan, Approve, Execute

This guide explains how to audit pending changes, propose grouped commits, review/approve them, and finally perform the corresponding commits.

## Script

Path: `code-netlogo-to-messir/scripts/git_audit_and_group_commits.py`

## Output Location

Artifacts are persisted under:

```
code-netlogo-to-messir/output/runs/<YYYY-MM-DD>/<HHMM>/overall/
```

Generated files include:
- `git_audit_plan.json` — machine-readable plan
- `git_audit_plan.md` — human-readable plan

## Usage

1) Dry-run (no changes):

```
python code-netlogo-to-messir/scripts/git_audit_and_group_commits.py --dry-run
```

2) Propose groups by directory and approve interactively:

```
python code-netlogo-to-messir/scripts/git_audit_and_group_commits.py --grouping directory
```

3) Auto-approve all groups (non-interactive):

```
python code-netlogo-to-messir/scripts/git_audit_and_group_commits.py --yes
```

## Grouping Strategies

- `directory` (default): bucket by top-level folder
- `ext`: bucket by file extension
- `module`: heuristic bucket using top-level folder

## Commit Messages

Each group is committed with a message like:

```
chore(commit-group): <group-name> — <N> file(s)
```

## Notes & Caveats

- The script respects `.gitignore` via git commands.
- It does not rewrite history; commits are additive.
- Use `--dry-run` to validate the plan before committing.
- Large diffs and binary files are listed but not parsed; review carefully before approval.


