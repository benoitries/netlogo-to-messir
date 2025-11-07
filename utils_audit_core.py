#!/usr/bin/env python3
"""Core helpers for working with auditor payloads."""

from __future__ import annotations

import json
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
    
    Handles both parsed JSON (dict/list) and raw text responses from LLM.
    If payload is a string (raw text), stores it directly in 'data' and attempts to extract
    audit fields by parsing JSON (handles markdown code fences).
    If payload is a dict/list, extracts audit fields (verdict, non-compliant-rules, etc.) from it
    and stores the original structure in 'data'.

    Returns a dict containing:
        - data: The raw text content (if payload is string) or raw audit data (if payload is dict/list)
        - verdict: "compliant" | "non-compliant" (extracted from parsed JSON if available)
        - non_compliant_rules: list (extracted from parsed JSON if available)
        - coverage: dict with required keys (extracted from parsed JSON if available)
        - errors: list (extracted from parsed JSON if available)
    """
    # Store original payload text for data field (always store raw text)
    original_payload_text = payload if isinstance(payload, str) else None
    
    # If payload is a string (raw LLM response), store it directly in data
    # but try to parse JSON to extract audit fields (verdict, non-compliant-rules, etc.)
    if isinstance(payload, str):
        original_text = payload
        parsed_payload = None
        
        # Try to parse JSON to extract audit fields (but keep original text in data)
        try:
            # Try to extract JSON from markdown code fences if present
            text = payload.strip()
            # Remove markdown code fences (```json ... ``` or ``` ... ```)
            if text.startswith("```"):
                lines = text.split("\n")
                # Remove first line (```json or ```)
                if len(lines) > 1:
                    lines = lines[1:]
                # Remove last line (```)
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)
            # Try to parse as JSON
            parsed_payload = json.loads(text)
        except (json.JSONDecodeError, ValueError, AttributeError):
            # If parsing fails, store raw text and return default structure
            return {
                "data": original_text,  # Store raw text content
                "verdict": "non-compliant",
                "non_compliant_rules": [],
                "coverage": dict(_DEFAULT_COVERAGE),
                "errors": [],
            }
        
        # If parsing succeeded, extract audit fields from parsed JSON
        # but still store original text in data
        if parsed_payload is not None:
            data_node, parent = _extract_data_node(parsed_payload)
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

            return {
                "data": original_text,  # Store raw text content (not parsed JSON)
                "verdict": verdict,
                "non_compliant_rules": rules_list,
                "coverage": coverage_dict,
                "errors": errors,
            }

    # If payload is already a dict/list, extract audit fields from it
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
        "data": data_node,  # Store parsed JSON structure (for backward compatibility with dict/list payloads)
        "verdict": verdict,
        "non_compliant_rules": rules_list,
        "coverage": coverage_dict,
        "errors": errors,
    }


