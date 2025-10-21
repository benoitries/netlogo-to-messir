#!/usr/bin/env python3
"""
Analyze orchestrator runs under output/runs/2025-10-15/ and produce:
- Per-combination metrics (durations, tokens incl. reasoning, compliance for steps 6 and 8)
- Aggregates (counts, means, mins/maxes, success rates)
- Markdown report suitable for a paper's experimentation section

Outputs:
- output/runs/2025-10-15/analysis/summary.csv
- output/runs/2025-10-15/analysis/summary.json
- output/runs/2025-10-15/analysis/experiment_report.md

Notes:
- Read-only across combinations; do not alter existing artifacts.
- Best/worst determined by final compliance, then total duration (shorter is better),
  then total tokens (lower is better) as tie-breakers.
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, asdict
from pathlib import Path
import sys
# Ensure project root is importable when running from scripts/
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from utils_config_constants import OUTPUT_DIR

# Regexes reused from time parser logic
COMP_LINE = re.compile(r"^.*completed in\s+([0-9]+\.[0-9]+|[0-9]+)s")
DETAIL_LINE = re.compile(r"^.*SUCCESS\s+([0-9]+\.[0-9]+|[0-9]+)s")

STEP_DIR_PATTERN = re.compile(r"^(\d{2})-([a-z_]+)$")

TOK_ROW = re.compile(r"INFO -\s+([a-z_\s]+?)\s+✓ SUCCESS\s+([0-9]+\.[0-9]+|[0-9]+)s\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s*$")
AGENT_DONE = re.compile(r"INFO -\s+✅\s+([a-z_]+)\s+completed\s+in\s+([0-9]+\.[0-9]+|[0-9]+)s")
INPUT_LINE = re.compile(r"INFO -\s+Input Tokens\s*=\s*([0-9,]+)")
OUTPUT_LINE = re.compile(r"INFO -\s+Output Tokens\s*=\s*([0-9,]+)\s*\(\s*reasoning\s*=\s*([0-9,]+)\s*,\s*visibleOutput\s*=\s*([0-9,]+)\s*\)")
TOTAL_LINE = re.compile(r"INFO -\s+Total Tokens\s*=\s*([0-9,]+)")


@dataclass
class StepMetrics:
    step_number: int
    agent_id: str
    duration_seconds: Optional[int] = None
    input_tokens: int = 0
    visible_output_tokens: int = 0
    reasoning_tokens: int = 0
    total_output_tokens: int = 0
    tokens_used: int = 0
    compliance_verdict: Optional[str] = None  # Particularly for step 6 and 8


@dataclass
class CombinationMetrics:
    date: str
    time: str
    combination: str  # <case>-<model>-reason-<r>-verb-<v>
    case: str
    model: str
    reasoning: str
    verbosity: str
    total_orchestration_seconds: Optional[int]
    total_duration_by_sum: int
    total_input_tokens: int
    total_visible_output_tokens: int
    total_reasoning_tokens: int
    total_output_tokens: int
    total_tokens_used: int
    step6_verdict: Optional[str]
    step8_verdict: Optional[str]
    final_compliant: bool
    steps: List[StepMetrics]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _parse_orchestrator_times(orchestrator_log: Path) -> Tuple[Dict[int, int], Optional[int]]:
    times: Dict[int, int] = {}
    total: Optional[int] = None
    text = _read_text(orchestrator_log)
    if not text:
        return times, total
    lines = text.splitlines()
    # try total
    for line in lines:
        if "Total orchestration time:" in line:
            m = COMP_LINE.search(line)
            if m:
                try:
                    total = round(float(m.group(1)))
                except Exception:
                    total = None
            break
    # try detail table
    for line in lines:
        m = DETAIL_LINE.search(line)
        if m:
            try:
                sec = round(float(m.group(1)))
            except Exception:
                sec = 0
            # Heuristic: we cannot reliably map from line to step here without labels;
            # fall back to sequence-based capture below if needed.
    # fallback to sequential "Step N:" lines
    current_step = 0
    for line in lines:
        for n in range(1, 9):
            if f"Step {n}:" in line:
                current_step = n
                break
        if "completed in" in line and current_step:
            m = COMP_LINE.search(line)
            if m:
                try:
                    sec = round(float(m.group(1)))
                except Exception:
                    sec = 0
                times[current_step] = sec
    return times, total


def _extract_tokens_from_response_json(fp: Path) -> Dict[str, int]:
    try:
        obj = json.loads(_read_text(fp) or "{}")
    except Exception:
        obj = {}
    return {
        "input_tokens": int(obj.get("input_tokens", 0) or 0),
        "visible_output_tokens": int(obj.get("visible_output_tokens", 0) or 0),
        "reasoning_tokens": int(obj.get("reasoning_tokens", 0) or 0),
        "total_output_tokens": int(obj.get("total_output_tokens", 0) or 0),
        "tokens_used": int(obj.get("tokens_used", 0) or 0),
    }


def _extract_verdict_from_data_json(fp: Path) -> Optional[str]:
    try:
        obj = json.loads(_read_text(fp) or "{}")
    except Exception:
        return None
    # Attempt common fields
    for key in ("verdict", "final_verdict", "final_compliance", "compliance_verdict"):
        val = obj.get(key)
        if isinstance(val, str):
            return val
        if isinstance(val, bool):
            return "COMPLIANT" if val else "NON_COMPLIANT"
    # Try nested
    if isinstance(obj, dict):
        data = obj.get("data")
        if isinstance(data, dict):
            for key in ("verdict", "final_verdict", "final_compliance", "compliance_verdict"):
                val = data.get(key)
                if isinstance(val, str):
                    return val
                if isinstance(val, bool):
                    return "COMPLIANT" if val else "NON_COMPLIANT"
    return None


def _is_compliant(verdict: Optional[str]) -> Optional[bool]:
    if verdict is None:
        return None
    v = str(verdict).strip().lower()
    if "compliant" in v and not ("non" in v or "not" in v or "fail" in v):
        return True
    if "non" in v or "not" in v or "fail" in v:
        return False
    return None


def _to_int(num_str: Optional[str]) -> int:
    if not num_str:
        return 0
    try:
        return int(num_str.replace(",", ""))
    except Exception:
        try:
            return int(float(num_str))
        except Exception:
            return 0


def _parse_tokens_from_orchestrator(orchestrator_log: Path) -> Tuple[Dict[str, Dict[str, int]], Dict[str, int]]:
    """Return (per_agent_tokens, overall_tokens) from orchestrator log.

    per_agent_tokens: { agent_id: {input_tokens, visible_output_tokens, reasoning_tokens, total_output_tokens, tokens_used} }
    overall_tokens: keys possibly include {total_tokens_used, total_input_tokens, total_output_tokens, total_reasoning_tokens}
    """
    per_agent: Dict[str, Dict[str, int]] = {}
    overall: Dict[str, int] = {}
    text = _read_text(orchestrator_log)
    if not text:
        return per_agent, overall
    lines = [ln.strip("\n") for ln in text.splitlines()]

    # Pass 1: Try AGENT EXECUTION DETAILS table rows
    for ln in lines:
        m = TOK_ROW.search(ln)
        if m:
            agent_label = m.group(1).strip().replace(" ", "_")
            # Normalize some labels to match step dir names
            agent_id = agent_label
            # Extract columns
            total_tokens = _to_int(m.group(3))
            input_tokens = _to_int(m.group(4))
            visible_out = _to_int(m.group(5))
            reasoning = _to_int(m.group(6))
            output_tokens = _to_int(m.group(7))
            per_agent[agent_id] = {
                "input_tokens": input_tokens,
                "visible_output_tokens": visible_out,
                "reasoning_tokens": reasoning,
                "total_output_tokens": visible_out + reasoning if (visible_out or reasoning) else output_tokens,
                "tokens_used": total_tokens,
            }

    # Pass 2: If table missing for some agents, parse per-agent blocks after completion lines
    current_agent: Optional[str] = None
    seen_metrics = {k for k in per_agent.keys()}
    i = 0
    while i < len(lines):
        ln = lines[i]
        md = AGENT_DONE.search(ln)
        if md:
            current_agent = md.group(1).strip()
            # Peek next few lines for tokens
            input_tokens = visible_out = reasoning = total_tokens = total_output_tokens = 0
            j = i + 1
            while j < len(lines) and j <= i + 6:
                l2 = lines[j]
                mi = INPUT_LINE.search(l2)
                if mi:
                    input_tokens = _to_int(mi.group(1))
                mo = OUTPUT_LINE.search(l2)
                if mo:
                    output_tokens = _to_int(mo.group(1))
                    reasoning = _to_int(mo.group(2))
                    visible_out = _to_int(mo.group(3))
                    total_output_tokens = visible_out + reasoning if (visible_out or reasoning) else output_tokens
                mt = TOTAL_LINE.search(l2)
                if mt:
                    total_tokens = _to_int(mt.group(1))
                j += 1
            if current_agent and current_agent not in seen_metrics:
                per_agent[current_agent] = {
                    "input_tokens": input_tokens,
                    "visible_output_tokens": visible_out,
                    "reasoning_tokens": reasoning,
                    "total_output_tokens": total_output_tokens or (visible_out + reasoning),
                    "tokens_used": total_tokens or (input_tokens + total_output_tokens),
                }
        i += 1

    # Pass 3: Overall summary totals
    # Look for lines like:
    # "Total Tokens Used: 37,136" etc.
    for ln in lines:
        if "Total Tokens Used:" in ln:
            overall["total_tokens_used"] = _to_int(ln.split(":")[-1].strip())
        elif "Total Input Tokens:" in ln:
            overall["total_input_tokens"] = _to_int(ln.split(":")[-1].strip())
        elif "Total Output Tokens:" in ln and "Visible" not in ln:
            overall["total_output_tokens"] = _to_int(ln.split(":")[-1].strip())
        elif "Total Reasoning Tokens:" in ln:
            overall["total_reasoning_tokens"] = _to_int(ln.split(":")[-1].strip())

    return per_agent, overall


def parse_combination(date_dir: Path, time_dir: Path, combo_dir: Path) -> Optional[CombinationMetrics]:
    # Extract parts: <case>-<model>-reason-<r>-verb-<v>
    combo = combo_dir.name
    parts = combo.split("-reason-")
    case_model = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    reasoning, verbosity = "", ""
    if "-verb-" in rest:
        r, v = rest.split("-verb-", 1)
        reasoning, verbosity = r, v
    # Model may contain dashes; case is everything up to last dash of case_model's first token split logic.
    # Heuristic: case is the NetLogo case name present in input-netlogo filenames; assume it's the leading token up to first "-" that matches an input file; fallback to first token.
    tokens = case_model.split("-")
    case = tokens[0]
    model = case_model[len(case)+1:] if len(case_model) > len(case)+1 else case_model

    # Orchestrator log
    orch_logs = list(combo_dir.glob("*_orchestrator.log"))
    times_by_step: Dict[int, int] = {}
    total_orch: Optional[int] = None
    tokens_by_agent: Dict[str, Dict[str, int]] = {}
    overall_tokens: Dict[str, int] = {}
    if orch_logs:
        times_by_step, total_orch = _parse_orchestrator_times(orch_logs[0])
        tokens_by_agent, overall_tokens = _parse_tokens_from_orchestrator(orch_logs[0])

    steps: List[StepMetrics] = []
    totals = {
        "input_tokens": 0,
        "visible_output_tokens": 0,
        "reasoning_tokens": 0,
        "total_output_tokens": 0,
        "tokens_used": 0,
    }
    step6_verdict: Optional[str] = None
    step8_verdict: Optional[str] = None

    for step_dir in sorted([d for d in combo_dir.iterdir() if d.is_dir()]):
        m = STEP_DIR_PATTERN.match(step_dir.name)
        if not m:
            continue
        step_number = int(m.group(1))
        agent_id = m.group(2)
        # Prefer orchestrator log tokens when available
        tkn = tokens_by_agent.get(agent_id)
        if not tkn:
            # Some labels in table are spaced; normalize alternative keys
            alt = agent_id.replace("_", " ")
            tkn = tokens_by_agent.get(alt)
        if not tkn:
            # fallback to response.json
            resp = next(iter(step_dir.glob("*_response.json")), None)
            if resp is None:
                resp = next(iter(step_dir.glob("output-response.json")), None)
            tkn = _extract_tokens_from_response_json(resp) if resp else {
                "input_tokens": 0,
                "visible_output_tokens": 0,
                "reasoning_tokens": 0,
                "total_output_tokens": 0,
                "tokens_used": 0,
            }
        for k in totals:
            totals[k] += int(tkn.get(k, 0) or 0)
        data_json = next(iter(step_dir.glob("*_data.json")), None)
        if data_json is None:
            data_json = next(iter(step_dir.glob("output-data.json")), None)
        verdict = _extract_verdict_from_data_json(data_json) if data_json else None
        if step_number == 6:
            step6_verdict = verdict
        if step_number == 8:
            step8_verdict = verdict
        steps.append(
            StepMetrics(
                step_number=step_number,
                agent_id=agent_id,
                duration_seconds=times_by_step.get(step_number),
                input_tokens=int(tkn.get("input_tokens", 0) or 0),
                visible_output_tokens=int(tkn.get("visible_output_tokens", 0) or 0),
                reasoning_tokens=int(tkn.get("reasoning_tokens", 0) or 0),
                total_output_tokens=int(tkn.get("total_output_tokens", 0) or 0),
                tokens_used=int(tkn.get("tokens_used", 0) or 0),
                compliance_verdict=verdict,
            )
        )

    total_duration_by_sum = sum(v for v in times_by_step.values() if isinstance(v, int))

    # If overall tokens present, override totals to ensure consistency
    if overall_tokens:
        totals["tokens_used"] = overall_tokens.get("total_tokens_used", totals["tokens_used"]) or totals["tokens_used"]
        totals["input_tokens"] = overall_tokens.get("total_input_tokens", totals["input_tokens"]) or totals["input_tokens"]
        totals["total_output_tokens"] = overall_tokens.get("total_output_tokens", totals["total_output_tokens"]) or totals["total_output_tokens"]
        totals["reasoning_tokens"] = overall_tokens.get("total_reasoning_tokens", totals["reasoning_tokens"]) or totals["reasoning_tokens"]
        # visible_output_tokens cannot be derived directly; keep summed value

    final_flag = _is_compliant(step8_verdict)
    if final_flag is None:
        final_flag = _is_compliant(step6_verdict) or False

    return CombinationMetrics(
        date=date_dir.name,
        time=time_dir.name,
        combination=combo_dir.name,
        case=case,
        model=model,
        reasoning=reasoning,
        verbosity=verbosity,
        total_orchestration_seconds=total_orch,
        total_duration_by_sum=total_duration_by_sum,
        total_input_tokens=totals["input_tokens"],
        total_visible_output_tokens=totals["visible_output_tokens"],
        total_reasoning_tokens=totals["reasoning_tokens"],
        total_output_tokens=totals["total_output_tokens"],
        total_tokens_used=totals["tokens_used"],
        step6_verdict=step6_verdict,
        step8_verdict=step8_verdict,
        final_compliant=bool(final_flag),
        steps=steps,
    )


def discover_metrics_for_date(target_date: str = "2025-10-15") -> List[CombinationMetrics]:
    results: List[CombinationMetrics] = []
    date_dir = OUTPUT_DIR / "runs" / target_date
    if not date_dir.exists():
        return results
    for time_dir in sorted([d for d in date_dir.iterdir() if d.is_dir()], key=lambda p: p.name):
        for combo_dir in sorted([d for d in time_dir.iterdir() if d.is_dir()], key=lambda p: p.name):
            cm = parse_combination(date_dir, time_dir, combo_dir)
            if cm:
                results.append(cm)
    return results


def save_csv_json(md: List[CombinationMetrics], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # CSV
    import csv
    csv_path = out_dir / "summary.csv"
    fieldnames = [
        "date","time","combination","case","model","reasoning","verbosity",
        "total_orchestration_seconds","total_duration_by_sum",
        "total_input_tokens","total_visible_output_tokens","total_reasoning_tokens",
        "total_output_tokens","total_tokens_used",
        "step6_verdict","step8_verdict","final_compliant",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for cm in md:
            row = {k: getattr(cm, k) for k in fieldnames}
            writer.writerow(row)
    # JSON
    json_path = out_dir / "summary.json"
    json_path.write_text(json.dumps([asdict(cm) for cm in md], indent=2), encoding="utf-8")


def _rate_success(md: List[CombinationMetrics]) -> Dict[str, float]:
    total = len(md)
    if total == 0:
        return {"rate_final_compliant": 0.0}
    final = sum(1 for cm in md if cm.final_compliant)
    return {"rate_final_compliant": round(final / total, 3)}


def _select_best_worst(md: List[CombinationMetrics]) -> Tuple[List[CombinationMetrics], List[CombinationMetrics]]:
    if not md:
        return [], []
    # Sort by: final_compliant desc, total_orch asc (fallback to sum), total_tokens_used asc
    def key(cm: CombinationMetrics):
        tot = cm.total_orchestration_seconds if cm.total_orchestration_seconds is not None else cm.total_duration_by_sum
        return (-int(cm.final_compliant), tot, cm.total_tokens_used)
    sorted_md = sorted(md, key=key)
    best = [sorted_md[0]]
    worst = [sorted_md[-1]]
    return best, worst


def render_markdown(md: List[CombinationMetrics], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("## Experimentation Report — 2025-10-15 Runs")
    lines.append("")
    lines.append("### Overview")
    lines.append("This report summarizes all orchestrator combinations executed on 2025-10-15. Metrics include total duration, token usage (incl. reasoning), and compliance outcomes at steps 6 and 8. Aggregates and best/worst runs are presented.")
    lines.append("")

    # Aggregates
    n = len(md)
    rates = _rate_success(md)
    durations = [cm.total_orchestration_seconds if cm.total_orchestration_seconds is not None else cm.total_duration_by_sum for cm in md]
    tokens_used_all = [cm.total_tokens_used for cm in md]
    input_all = [cm.total_input_tokens for cm in md]
    visible_all = [cm.total_visible_output_tokens for cm in md]
    reasoning_all = [cm.total_reasoning_tokens for cm in md]
    total_out_all = [cm.total_output_tokens for cm in md]

    lines.append("### Aggregated Metrics")
    lines.append(f"- **combinations analyzed**: {n}")
    if durations:
        lines.append(f"- **duration (s)**: mean {round(statistics.mean(durations), 1)}, min {min(durations)}, max {max(durations)}")
    if tokens_used_all:
        lines.append(f"- **tokens used (total)**: mean {round(statistics.mean(tokens_used_all), 1)}, min {min(tokens_used_all)}, max {max(tokens_used_all)}")
    lines.append(f"- **final compliance rate**: {rates['rate_final_compliant'] * 100:.1f}%")
    lines.append("")

    # Token breakdown
    lines.append("### Token Breakdown (per combination totals)")
    if input_all:
        lines.append(f"- **input tokens**: mean {round(statistics.mean(input_all), 1)}, min {min(input_all)}, max {max(input_all)}")
    if visible_all:
        lines.append(f"- **visible output tokens**: mean {round(statistics.mean(visible_all), 1)}, min {min(visible_all)}, max {max(visible_all)}")
    if reasoning_all:
        lines.append(f"- **reasoning tokens**: mean {round(statistics.mean(reasoning_all), 1)}, min {min(reasoning_all)}, max {max(reasoning_all)}")
    if total_out_all:
        lines.append(f"- **total output tokens (visible + reasoning)**: mean {round(statistics.mean(total_out_all), 1)}, min {min(total_out_all)}, max {max(total_out_all)}")
    lines.append("")

    # Best / Worst
    best, worst = _select_best_worst(md)
    lines.append("### Best Run(s)")
    if best:
        for cm in best:
            total_s = cm.total_orchestration_seconds or cm.total_duration_by_sum
            lines.append(f"- `{cm.time}/{cm.combination}` — compliant={cm.final_compliant}, total_s={total_s}, tokens_used={cm.total_tokens_used}, input={cm.total_input_tokens}, visible={cm.total_visible_output_tokens}, reasoning={cm.total_reasoning_tokens}, out_total={cm.total_output_tokens}")
    else:
        lines.append("- None")
    lines.append("")
    lines.append("### Worst Run(s)")
    if worst:
        for cm in worst:
            total_s = cm.total_orchestration_seconds or cm.total_duration_by_sum
            lines.append(f"- `{cm.time}/{cm.combination}` — compliant={cm.final_compliant}, total_s={total_s}, tokens_used={cm.total_tokens_used}, input={cm.total_input_tokens}, visible={cm.total_visible_output_tokens}, reasoning={cm.total_reasoning_tokens}, out_total={cm.total_output_tokens}")
    else:
        lines.append("- None")
    lines.append("")

    # Strengths / Limitations
    lines.append("### Strengths and Limitations")
    lines.append("- **strengths**: clear stage outputs and token accounting enable reproducible metrics; compliance step presence allows final verdict consolidation.")
    lines.append("- **limitations**: missing or heterogeneous response/data JSON schemas across steps can hide verdicts; some combinations may lack orchestrator total time.")
    lines.append("")

    # Table snippet
    lines.append("### Sample of Combinations (top 10)")
    lines.append("")
    lines.append("| time | combination | compliant | total_s | tokens_used | input | visible | reasoning | out_total | step6 | step8 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for cm in md[:10]:
        total_s = cm.total_orchestration_seconds or cm.total_duration_by_sum
        lines.append(
            f"| {cm.time} | `{cm.combination}` | {int(cm.final_compliant)} | {total_s} | {cm.total_tokens_used} | {cm.total_input_tokens} | {cm.total_visible_output_tokens} | {cm.total_reasoning_tokens} | {cm.total_output_tokens} | {cm.step6_verdict or ''} | {cm.step8_verdict or ''} |")

    (out_dir / "experiment_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    date = "2025-10-15"
    out_dir = OUTPUT_DIR / "runs" / date / "analysis"
    metrics = discover_metrics_for_date(date)
    save_csv_json(metrics, out_dir)
    render_markdown(metrics, out_dir)
    print(f"OK: wrote analysis to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
