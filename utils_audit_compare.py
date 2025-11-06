"""
Utilities to compare agent auditor verdicts vs deterministic Python auditors,
and to log a concise summary inside the orchestrator logs.
"""
from __future__ import annotations

from typing import Dict, Any


def _normalize_verdict(value: Any) -> bool | None:
    """Normalize a verdict to boolean where True means compliant.

    Accepted inputs:
    - True/False
    - "compliant"/"non-compliant" (case-insensitive)
    - Other truthy/falsy values are NOT coerced (return None) to avoid
      incorrect interpretation (e.g., any non-empty string becoming True).
    """
    # Explicit booleans
    if isinstance(value, bool):
        return value
    # Strings mapping
    if isinstance(value, str):
        v = value.strip().lower()
        if v == "compliant":
            return True
        if v == "non-compliant":
            return False
        if v in ("true", "yes", "ok", "pass"):
            return True
        if v in ("false", "no", "fail"):
            return False
    # Unknown type/value => None (unknown)
    return None


def compare_verdicts(agent_audit: Dict[str, Any] | None, python_audit: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    Compare two auditor-like dicts of shape {"verdict": bool, "violations": [...]}
    Returns a small comparison summary.
    """
    agent_raw = (agent_audit or {}).get("verdict")
    py_raw = (python_audit or {}).get("verdict")
    agent_verdict_norm = _normalize_verdict(agent_raw)
    py_verdict_norm = _normalize_verdict(py_raw)

    # If any side is unknown, mark as no match decision but keep booleans as None
    if agent_verdict_norm is None or py_verdict_norm is None:
        match = False
    else:
        match = agent_verdict_norm == py_verdict_norm
    agent_violations = (agent_audit or {}).get("violations") or []
    py_violations = (python_audit or {}).get("violations") or []
    return {
        "match": match,
        "agent_verdict": agent_verdict_norm,
        "python_verdict": py_verdict_norm,
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


