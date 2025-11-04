#!/usr/bin/env python3
"""
Shared helpers to build and normalize the PlantUML LUCIM Auditor JSON schema
as defined in the persona PSN_6 (lines 33–63).

Target top-level structure:
{
  "data": {
    "verdict": "compliant|non-compliant",
    "non-compliant-rules": [{"rule": str, "line": str, "msg": str}],
    "coverage": {
      "total_rules_in_dsl": str,
      "evaluated": [str],
      "not_applicable": [str],
      "missing_evaluation": []
    }
  },
  "errors": []
}
"""

from typing import Any, Dict, List


def _ensure_list(value: Any) -> List:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    # Coerce scalars to single-item list as a defensive fallback
    return [value]


def build_auditor_payload(
    verdict: str,
    non_compliant_rules: List[Dict[str, Any]] = None,
    coverage: Dict[str, Any] = None,
    errors: List[str] = None,
) -> Dict[str, Any]:
    ncr = non_compliant_rules if isinstance(non_compliant_rules, list) else []
    cov = coverage if isinstance(coverage, dict) else {}
    cov.setdefault("total_rules_in_dsl", "0")
    cov.setdefault("evaluated", [])
    cov.setdefault("not_applicable", [])
    # Persona requires missing_evaluation to be an empty list
    cov["missing_evaluation"] = []

    # Normalize verdict to strict enum
    normalized_verdict = _normalize_verdict_text(verdict)

    top = {
        "data": {
            "verdict": normalized_verdict,
            "non-compliant-rules": ncr,
            "coverage": cov,
        },
        "errors": errors if isinstance(errors, list) else [],
    }
    return top


def normalize_auditor_like_response(parsed: Any) -> Dict[str, Any]:
    """Normalize arbitrary parsed JSON into the exact auditor schema.

    Rules:
    - If top-level has "data", use it; otherwise treat parsed as the data node.
    - Ensure required keys exist with correct types.
    - Force coverage.missing_evaluation to an empty list as per persona.
    - Always include top-level "errors" as a list (default empty).
    """
    top_errors: List[str] = []
    node: Dict[str, Any] = {}

    if isinstance(parsed, dict):
        # Prefer nested data if present
        candidate = parsed.get("data") if isinstance(parsed.get("data"), dict) else parsed
        node = candidate if isinstance(candidate, dict) else {}
        errs = parsed.get("errors")
        if isinstance(errs, list):
            top_errors = errs

    verdict_raw = node.get("verdict") if isinstance(node.get("verdict"), str) else "non-compliant"
    verdict = _normalize_verdict_text(verdict_raw)
    ncr = node.get("non-compliant-rules")
    ncr_list = ncr if isinstance(ncr, list) else []

    cov = node.get("coverage") if isinstance(node.get("coverage"), dict) else {}
    total_rules = cov.get("total_rules_in_dsl")
    if not isinstance(total_rules, (str, int)):
        total_rules = "0"
    total_rules_str = str(total_rules)
    evaluated = _ensure_list(cov.get("evaluated"))
    not_applicable = _ensure_list(cov.get("not_applicable"))

    normalized = build_auditor_payload(
        verdict=verdict,
        non_compliant_rules=ncr_list,
        coverage={
            "total_rules_in_dsl": total_rules_str,
            "evaluated": evaluated,
            "not_applicable": not_applicable,
            # missing_evaluation enforced in builder
        },
        errors=top_errors,
    )
    return normalized


def _normalize_verdict_text(verdict_text: str) -> str:
    """Normalize arbitrary verdict text to one of {"compliant", "non-compliant"}.

    Heuristics:
    - Case-insensitive, strips emojis and punctuation.
    - If contains "non" close to "compliant" (e.g., "non compliant", "non-compliant"), return "non-compliant".
    - If contains a check mark or the phrase "fully compliant", return "compliant".
    - Fallback to "non-compliant" if ambiguous.
    """
    if not isinstance(verdict_text, str):
        return "non-compliant"

    text = verdict_text.strip().lower()

    # Quick emoji/marker hints
    if "❌" in verdict_text:
        return "non-compliant"
    if "✅" in verdict_text:
        return "compliant"

    # Normalize separators
    text = text.replace("_", " ").replace("-", " ")

    # Clear common punctuation
    for ch in [".", "!", ":", ";", ",", "|"]:
        text = text.replace(ch, " ")

    # Token-based checks
    tokens = text.split()
    joined = " ".join(tokens)

    # If mentions non and compliant together → non-compliant
    if "non compliant" in joined or "not compliant" in joined:
        return "non-compliant"

    # Phrases indicating compliance
    if "fully compliant" in joined or "compliant" in tokens or "compliance: ok" in joined:
        return "compliant"

    # Exact enum support
    if verdict_text in ("compliant", "non-compliant"):
        return verdict_text

    # Fallback conservative
    return "non-compliant"


