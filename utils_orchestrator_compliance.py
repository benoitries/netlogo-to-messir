#!/usr/bin/env python3
"""
Orchestrator Compliance Extraction Utility
Extracts compliance status from processed results.
"""

from typing import Dict, Any


def extract_compliance_from_results(processed_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract compliance status from processed results.
    
    Args:
        processed_results: Dictionary containing all processing results
        
    Returns:
        Dictionary with compliance status, source, and details
    """
    # Prefer the v3 PlantUML LUCIM auditor result (step 6 in limited-agents pipeline)
    # Current key naming in v3: "lucim_plantuml_diagram_auditor"
    # Backward-compat keys kept for older runs: "lucim_plantuml_diagram_auditor", "plantuml_lucim_final_auditor"

    def _evaluate_auditor(auditor_obj: Dict[str, Any], source: str, step: int) -> Dict[str, Any] | None:
        if not auditor_obj or not isinstance(auditor_obj, dict):
            return None
        data = auditor_obj.get("data")
        if isinstance(data, dict):
            verdict = data.get("verdict")
            if isinstance(verdict, str):
                v = verdict.strip().lower()
                if v == "compliant":
                    return {"status": "VERIFIED", "source": source, "details": {"verdict": verdict, "step": step}}
                if v == "non-compliant":
                    return {"status": "NON-COMPLIANT", "source": source, "details": {"verdict": verdict, "step": step}}
        # If explicit errors exist, treat as non-compliant
        errors = auditor_obj.get("errors", [])
        if errors:
            return {"status": "NON-COMPLIANT", "source": source, "details": {"reason": "auditor_errors", "errors": errors, "step": step}}
        return None

    # 1) v3 key
    res = _evaluate_auditor(processed_results.get("lucim_plantuml_diagram_auditor"), "diagram_auditor_v3", 6)
    if res:
        return res

    # 2) backward-compat: initial auditor (older naming)
    res = _evaluate_auditor(processed_results.get("lucim_plantuml_diagram_auditor"), "diagram_auditor_legacy", 6)
    if res:
        return res

    # 3) backward-compat: final auditor (if ever present in older flows)
    res = _evaluate_auditor(processed_results.get("plantuml_lucim_final_auditor"), "final_auditor_legacy", 6)
    if res:
        return res

    # 4) Deterministic python audits (if provided) as a last resort
    py_audits = processed_results.get("python_audits")
    if isinstance(py_audits, dict):
        diagram_py = py_audits.get("diagram")
        if isinstance(diagram_py, dict):
            verdict = diagram_py.get("verdict")
            if isinstance(verdict, str):
                v = verdict.strip().lower()
                if v == "compliant":
                    return {"status": "VERIFIED", "source": "python_audit", "details": {"verdict": verdict, "step": 6}}
                if v == "non-compliant":
                    return {"status": "NON-COMPLIANT", "source": "python_audit", "details": {"verdict": verdict, "step": 6}}

    # Binary fallback: if no authoritative verdict was found, mark as NON-COMPLIANT
    # Rationale: UNKNOWN is disallowed; absence of proof of compliance => non-compliant.
    return {"status": "NON-COMPLIANT", "source": "fallback", "details": {"reason": "no_auditor_verdict_found", "step": 6}}

