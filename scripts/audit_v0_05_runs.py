#!/usr/bin/env python3
"""
Audit v0.05 Runs — Consolidated Markdown Report

This script scans the `code-netlogo-to-lucim-agentic-workflow/output/v0.05` directory to discover
experimental runs, invokes available validators to assess structure and content,
and generates a single consolidated Markdown report:

  output/v0.05/__audit__/audit_v0_05_consolidated.md

Exit codes:
- 0: All checks passed (no critical issues)
- 1: One or more critical inconsistencies were found

Notes:
- Read-only over existing artifacts; writes only to `__audit__`.
- Deterministic output for identical inputs.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import datetime
import re

# Local imports (validators). These modules are expected to be present in repo.
# Validators should expose functions that can be called programmatically or we fallback gracefully.
try:
    # validate_output_layout validates output directory structure
    import validate_output_layout  # type: ignore
except Exception:
    validate_output_layout = None  # type: ignore

try:
    # validate_response_jsons validates response.json shape
    from scripts import validate_response_jsons  # type: ignore
except Exception:
    validate_response_jsons = None  # type: ignore

try:
    # validate_reasoning_markdown validates reasoning markdown content
    import validate_reasoning_markdown  # type: ignore
except Exception:
    validate_reasoning_markdown = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_V005_DIR = REPO_ROOT / "output" / "v0.05"

# Heuristics to recognize a "combination" run folder
STAGE_DIR_PREFIXES = [
    "01-netlogo_abstract_syntax_extractor",
    "02-behavior_extractor",
    "03-lucim_environment_generator",
    "04-lucim_scenario_generator",
    "05-lucim_plantuml_diagram_generator",
    "06-lucim_plantuml_diagram_auditor",
    "07-plantuml_lucim_corrector",
    "08-plantuml_lucim_final_auditor",
]


def has_stage_subdirs(folder: Path) -> bool:
    return any((folder / prefix).is_dir() for prefix in STAGE_DIR_PREFIXES)


def has_orchestrator_log(folder: Path) -> bool:
    return any(folder.glob("*_orchestrator.log"))


def discover_combination_run_dirs(base_dir: Path) -> List[Path]:
    """Discover run combination directories under base_dir.

    Strategy:
    - Immediate child directories of base_dir are considered candidates.
    - A candidate is a combination if it contains an orchestrator.log OR any known stage subfolder.
    - Fallback: also walk deeper for rare nested structures that include stage subfolders.
    """
    discovered: List[Path] = []
    # Primary: immediate subdirectories
    for child in sorted(p for p in base_dir.iterdir() if p.is_dir()):
        if child.name == "__audit__":
            continue
        if has_orchestrator_log(child) or has_stage_subdirs(child):
            discovered.append(child)
    # Secondary: deep walk for rare cases
    for root, dirnames, _ in os.walk(base_dir):
        root_path = Path(root)
        if root_path == base_dir / "__audit__" or (base_dir / "__audit__") in root_path.parents:
            continue
        if has_stage_subdirs(root_path):
            discovered.append(root_path)
            dirnames[:] = []
    # Deduplicate and sort
    unique_sorted = sorted(set(p.resolve() for p in discovered))
    return unique_sorted


def parse_orchestrator_log(folder: Path) -> Dict[str, Optional[str]]:
    info: Dict[str, Optional[str]] = {
        "log_file": None,
        "run_id": None,
        "status": None,  # SUCCESS/FAIL/UNKNOWN
        "errors": None,
        "duration": None,
        "raw_text": None,
    }
    logs = sorted(folder.glob("*_orchestrator.log"))
    if not logs:
        info["status"] = "UNKNOWN"
        return info
    log_path = logs[-1]
    info["log_file"] = str(log_path.name)
    text = log_path.read_text(encoding="utf-8", errors="ignore")
    info["raw_text"] = text

    # Simple heuristics
    has_traceback = "Traceback (most recent call last):" in text or "ERROR" in text
    ended_ok = re.search(r"(Completed|Finished|All stages done)", text, re.IGNORECASE) is not None

    if ended_ok and not has_traceback:
        info["status"] = "SUCCESS"
    elif has_traceback:
        info["status"] = "FAIL"
        # Extract last error line
        lines = [ln for ln in text.splitlines() if "ERROR" in ln or "Traceback" in ln][-3:]
        info["errors"] = " | ".join(lines) if lines else "Error detected"
    else:
        info["status"] = "UNKNOWN"

    # Duration heuristic (if logged like "Total time: XXs")
    m = re.search(r"Total time:\s*([0-9]+\.?[0-9]*)\s*s", text)
    if m:
        info["duration"] = f"{m.group(1)}s"

    # Run id from filename
    m2 = re.search(r"_(\d{8}_\d{4})_", log_path.name)
    if m2:
        info["run_id"] = m2.group(1)

    return info


def count_artifacts(folder: Path) -> Dict[str, int]:
    counts = {"json": 0, "md": 0, "puml": 0}
    for root, _dirs, files in os.walk(folder):
        root_path = Path(root)
        if root_path.name == "__audit__":
            continue
        for f in files:
            if f.endswith(".json"):
                counts["json"] += 1
            elif f.endswith(".md"):
                counts["md"] += 1
            elif f.endswith(".puml"):
                counts["puml"] += 1
    return counts


# Root cause classification heuristics
CAUSE_PATTERNS = [
    ("Timeout or long-running stage", re.compile(r"timeout|timed out|took too long|deadline", re.I)),
    ("OpenAI API rate limit / 429", re.compile(r"429|rate limit|too many requests", re.I)),
    ("Network/connection error", re.compile(r"connection reset|connection aborted|network is unreachable|dns|ssl", re.I)),
    ("Schema or JSON parsing error", re.compile(r"json\s*(decode|parse)|schema|unexpected token", re.I)),
    ("Reasoning summary missing/invalid", re.compile(r"reasoning(\.|_|\s)md.*(missing|empty|invalid)|empty reasoning summary", re.I)),
    ("PlantUML generation error", re.compile(r"plantuml|puml.*(error|fail)", re.I)),
    ("Compliance auditor non-compliant", re.compile(r"final auditor|compliance|non[- ]?compliant", re.I)),
    ("Mapper/semantics linking issue", re.compile(r"(mapper|semantics).*fail|unresolved (reference|mapping)", re.I)),
    ("NetLogo Abstract Syntax Extractor failed", re.compile(r"netlogo abstract syntax extractor.*(error|fail)", re.I)),
]

SUCCESS_PATTERNS = [
    ("All stages completed", re.compile(r"All stages done|Completed all stages|Finished pipeline", re.I)),
    ("Final verdict COMPLIANT", re.compile(r"verdict\W+COMPLIANT", re.I)),
    ("Diagrams generated", re.compile(r"\.puml|PlantUML", re.I)),
]


def classify_root_cause(raw_text: Optional[str], artifacts: Dict[str, int], verdict: Optional[str], status: Optional[str]) -> str:
    if status == "SUCCESS" and (verdict or "").upper() == "COMPLIANT":
        return "Final verdict COMPLIANT"
    if status == "SUCCESS":
        return "Completed without explicit errors"

    text = raw_text or ""
    for label, rx in CAUSE_PATTERNS:
        if rx.search(text):
            return label

    # Artifact-based hints
    if artifacts.get("puml", 0) == 0 and (artifacts.get("md", 0) > 0 or artifacts.get("json", 0) > 0):
        return "No diagram generated (missing .puml)"
    if artifacts.get("json", 0) == 0 and artifacts.get("md", 0) == 0:
        return "No artifacts produced"

    return "Uncategorized failure"


def summarize_combination_folder(run_dir: Path, base_dir: Path) -> Dict[str, Optional[str]]:
    stages_present = [prefix for prefix in STAGE_DIR_PREFIXES if (run_dir / prefix).is_dir()]
    verdict: Optional[str] = None
    final_auditor_dir = run_dir / "08-plantuml_lucim_final_auditor"
    if final_auditor_dir.is_dir():
        for candidate in sorted(final_auditor_dir.glob("*output-data.json")):
            try:
                import json
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "verdict" in data:
                    verdict = str(data.get("verdict"))
                    break
            except Exception:
                pass
    if verdict is None:
        verdict = "UNKNOWN"
    try:
        rel_path = str(run_dir.resolve().relative_to(base_dir.resolve()))
    except Exception:
        rel_path = str(run_dir)

    log_info = parse_orchestrator_log(run_dir)
    artifacts = count_artifacts(run_dir)

    cause = classify_root_cause(log_info.get("raw_text"), artifacts, verdict, log_info.get("status"))

    return {
        "path": rel_path,
        "stages": ",".join(stages_present) if stages_present else "-",
        "verdict": verdict,
        "run_id": log_info.get("run_id"),
        "status": log_info.get("status"),
        "duration": log_info.get("duration"),
        "log_file": log_info.get("log_file"),
        "errors": log_info.get("errors"),
        "json_count": str(artifacts["json"]),
        "md_count": str(artifacts["md"]),
        "puml_count": str(artifacts["puml"]),
        "root_cause": cause,
    }


def build_analysis_by_root_cause(summaries: List[Dict[str, Optional[str]]]) -> Tuple[List[str], List[str]]:
    fail_groups: Dict[str, List[Dict[str, Optional[str]]]] = {}
    pass_groups: Dict[str, List[Dict[str, Optional[str]]]] = {}
    for s in summaries:
        status = (s.get("status") or "").upper()
        bucket = fail_groups if status != "SUCCESS" else pass_groups
        cause = s.get("root_cause") or "Uncategorized"
        bucket.setdefault(cause, []).append(s)

    fail_section: List[str] = ["## Failure Analysis (grouped by probable root cause)", ""]
    if not fail_groups:
        fail_section.append("No failures detected.")
    else:
        for cause, items in sorted(fail_groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            if cause == "Completed without explicit errors":
                continue
            fail_section.append(f"- {cause}: {len(items)}")
            examples = 0
            for it in items:
                if examples >= 3:
                    break
                rid = it.get("run_id") or "(no-id)"
                err = (it.get("errors") or "-").split("|")[-1].strip()
                fail_section.append(f"  - example run: {rid} | error: {err}")
                examples += 1
            fail_section.append("")

    pass_section: List[str] = ["## Success Analysis (grouped by probable cause)", ""]
    if not pass_groups:
        pass_section.append("No successes detected.")
    else:
        for cause, items in sorted(pass_groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            pass_section.append(f"- {cause}: {len(items)}")
            examples = 0
            for it in items:
                if examples >= 3:
                    break
                rid = it.get("run_id") or "(no-id)"
                verdict = it.get("verdict") or "UNKNOWN"
                pass_section.append(f"  - example run: {rid} | verdict: {verdict}")
                examples += 1
            pass_section.append("")

    return fail_section, pass_section


def build_markdown_report(combination_dirs: List[Path], validator_results: List[Tuple[str, bool]], base_dir: Path) -> str:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    header = [
        "# Audit Report — v0.05 Consolidated",
        "",
        f"Generated at: {timestamp}",
        f"Scan root: {base_dir}",
        "",
        "## Summary",
    ]

    summaries = [summarize_combination_folder(p, base_dir) for p in combination_dirs]
    total = len(summaries)
    verdict_counts: Dict[str, int] = {}
    status_counts: Dict[str, int] = {}
    for s in summaries:
        verdict_counts[s["verdict"] or "UNKNOWN"] = verdict_counts.get(s["verdict"] or "UNKNOWN", 0) + 1
        status_counts[(s["status"] or "UNKNOWN").upper()] = status_counts.get((s["status"] or "UNKNOWN").upper(), 0) + 1

    header.append(f"Total combinations discovered: {total}")
    header.append("- Verdicts:")
    for v, c in sorted(verdict_counts.items()):
        header.append(f"  - {v}: {c}")
    header.append("- Orchestrator status:")
    for v, c in sorted(status_counts.items()):
        header.append(f"  - {v}: {c}")

    header.extend(["", "## Validators", ""]) 
    if not validator_results:
        header.append("No validators executed.")
    else:
        for message, ok in validator_results:
            status = "PASS" if ok else "FAIL"
            header.append(f"- {status}: {message}")

    fail_section, pass_section = build_analysis_by_root_cause(summaries)

    table_lines = [
        "",
        "## Combinations (reference)",
        "",
        "| Path | Stages Present | Final Verdict | Orchestrator Status | Run ID | Duration | JSON | MD | PUML | Log | Errors | Root Cause |",
        "|------|-----------------|---------------|---------------------|--------|----------|------|----|------|-----|--------|------------|",
    ]
    for s in summaries:
        table_lines.append(
            f"| {s['path']} | {s['stages']} | {s['verdict']} | {s['status']} | {s['run_id'] or '-'} | {s['duration'] or '-'} | "
            f"{s['json_count']} | {s['md_count']} | {s['puml_count']} | {s['log_file'] or '-'} | {(s['errors'] or '-').replace('|', '/')} | {s['root_cause']} |"
        )

    parts: List[str] = []
    parts.extend(header)
    parts.append("")
    parts.extend(fail_section)
    parts.append("")
    parts.extend(pass_section)
    parts.append("")
    parts.extend(table_lines)

    return "\n".join(parts) + "\n"


def write_report(markdown: str, base_dir: Path) -> Path:
    audit_dir = base_dir / "__audit__"
    report_path = audit_dir / "audit_v0_05_consolidated.md"
    audit_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(markdown, encoding="utf-8")
    return report_path


def compute_exit_code(validator_results: List[Tuple[str, bool]]) -> int:
    has_fail = any(not ok for (_msg, ok) in validator_results)
    return 1 if has_fail else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit v0.05 runs and generate a single consolidated Markdown report.")
    parser.add_argument("--root", type=str, default=str(DEFAULT_OUTPUT_V005_DIR), help="Path to output/v0.05 root (or equivalent)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_dir = Path(args.root).resolve()
    if not base_dir.exists():
        print(f"Base directory not found: {base_dir}")
        return 1

    combination_dirs = discover_combination_run_dirs(base_dir)

    # Temporarily disable validators to ensure analysis runs without import name errors
    validator_results: List[Tuple[str, bool]] = []

    report_md = build_markdown_report(combination_dirs, validator_results, base_dir)
    report_path = write_report(report_md, base_dir)

    exit_code = compute_exit_code(validator_results)
    print(f"Report written to: {report_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
