"""
Utilities to compare agent auditor verdicts vs deterministic Python auditors,
and to log a concise summary inside the orchestrator logs.
"""
from __future__ import annotations

from typing import Dict, Any


def compare_verdicts(agent_audit: Dict[str, Any] | None, python_audit: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    Compare two auditor-like dicts of shape {"verdict": bool, "violations": [...]}
    Returns a small comparison summary.
    """
    agent_verdict = bool((agent_audit or {}).get("verdict", False))
    py_verdict = bool((python_audit or {}).get("verdict", False))
    agent_violations = (agent_audit or {}).get("violations") or []
    py_violations = (python_audit or {}).get("violations") or []
    return {
        "match": agent_verdict == py_verdict,
        "agent_verdict": agent_verdict,
        "python_verdict": py_verdict,
        "agent_violations_count": len(agent_violations),
        "python_violations_count": len(py_violations),
    }


def log_comparison(logger, title: str, comparison: Dict[str, Any]) -> None:
    """Log a one-line comparison summary to the provided logger."""
    if logger is None:
        return
    match = comparison.get("match")
    a_v = comparison.get("agent_verdict")
    p_v = comparison.get("python_verdict")
    avc = comparison.get("agent_violations_count")
    pvc = comparison.get("python_violations_count")
    status = "MATCH" if match else "MISMATCH"
    logger.info(
        f"[AUDIT-COMPARE] {title}: {status} (agent={a_v}, python={p_v}, agent_viol={avc}, python_viol={pvc})"
    )


def summarize_comparisons(comparisons: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Compute a small aggregate summary over stage comparisons."""
    total = len(comparisons)
    matches = sum(1 for c in comparisons.values() if c.get("match"))
    return {"total": total, "matches": matches, "mismatches": total - matches}


