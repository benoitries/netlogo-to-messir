#!/usr/bin/env python3
"""Core helpers for working with auditor payloads."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


_DEFAULT_COVERAGE: Dict[str, Any] = {
    "total_rules_in_dsl": "0",
    "evaluated": [],
    "not_applicable": [],
    "missing_evaluation": [],
}


def _ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_verdict(value: Any) -> str:
    if isinstance(value, bool):
        return "compliant" if value else "non-compliant"

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "non-compliant"

        if "✅" in text:
            return "compliant"
        if "❌" in text:
            return "non-compliant"

        lowered = text.lower()
        if "non" in lowered and "compliant" in lowered:
            return "non-compliant"
        if "compliant" in lowered:
            return "compliant"
        if lowered in {"true", "yes", "ok"}:
            return "compliant"

    return "non-compliant"


def _extract_data_node(payload: Any) -> Tuple[Any, Dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}, {}

    data_candidate = payload.get("data")
    if isinstance(data_candidate, dict):
        return data_candidate, payload
    if isinstance(data_candidate, list):
        return data_candidate, payload

    return payload, payload


def extract_audit_core(payload: Any) -> Dict[str, Any]:
    """Extract canonical audit fields from an arbitrary payload.

    Returns a dict containing:
        - data: The raw audit data (dict/list or empty dict if unavailable)
        - verdict: "compliant" | "non-compliant"
        - non_compliant_rules: list
        - coverage: dict with required keys
        - errors: list
    """

    data_node, parent = _extract_data_node(payload)

    container = data_node if isinstance(data_node, dict) else {}
    verdict = _normalize_verdict(container.get("verdict"))

    rules = container.get("non-compliant-rules")
    if not isinstance(rules, list):
        rules = container.get("non_compliant_rules")
    if not isinstance(rules, list) and isinstance(parent, dict):
        rules = parent.get("non-compliant-rules")
    if not isinstance(rules, list) and isinstance(parent, dict):
        rules = parent.get("non_compliant_rules")
    if not isinstance(rules, list):
        rules = container.get("violations") or parent.get("violations") if isinstance(parent, dict) else []
    rules_list = rules if isinstance(rules, list) else []

    coverage = container.get("coverage")
    if not isinstance(coverage, dict) and isinstance(parent, dict):
        coverage = parent.get("coverage")
    coverage_dict = dict(_DEFAULT_COVERAGE)
    if isinstance(coverage, dict):
        coverage_dict.update({
            "total_rules_in_dsl": str(coverage.get("total_rules_in_dsl", coverage_dict["total_rules_in_dsl"])),
            "evaluated": _ensure_list(coverage.get("evaluated")),
            "not_applicable": _ensure_list(coverage.get("not_applicable")),
        })
        coverage_dict["missing_evaluation"] = _ensure_list(coverage.get("missing_evaluation"))

    errors = []
    potential_errors = []
    if isinstance(container.get("errors"), list):
        potential_errors.extend(container.get("errors") or [])
    if isinstance(parent, dict) and isinstance(parent.get("errors"), list):
        potential_errors.extend(parent.get("errors") or [])
    if potential_errors:
        errors = list(potential_errors)

    if not isinstance(data_node, (dict, list)):
        data_node = {}

    return {
        "data": data_node,
        "verdict": verdict,
        "non_compliant_rules": rules_list,
        "coverage": coverage_dict,
        "errors": errors,
    }


