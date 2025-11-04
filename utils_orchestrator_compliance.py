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
    # Try final auditor first
    final_auditor_result = processed_results.get("plantuml_lucim_final_auditor")
    if final_auditor_result and isinstance(final_auditor_result, dict):
        data = final_auditor_result.get("data")
        if isinstance(data, dict) and "verdict" in data:
            verdict = data.get("verdict")
            if verdict == "compliant":
                return {"status": "VERIFIED", "source": "final_auditor", "details": {"verdict": verdict, "step": 6}}
            elif verdict == "non-compliant":
                return {"status": "NON-COMPLIANT", "source": "final_auditor", "details": {"verdict": verdict, "step": 6}}
        errors = final_auditor_result.get("errors", [])
        if errors:
            return {"status": "NON-COMPLIANT", "source": "final_auditor", "details": {"reason": "auditor_errors", "errors": errors, "step": 6}}
    
    # Fallback to initial auditor
    initial_auditor_result = processed_results.get("plantuml_lucim_auditor")
    if initial_auditor_result and isinstance(initial_auditor_result, dict):
        data = initial_auditor_result.get("data")
        if isinstance(data, dict) and "verdict" in data:
            verdict = data.get("verdict")
            if verdict == "compliant":
                return {"status": "VERIFIED", "source": "initial_auditor", "details": {"verdict": verdict, "step": 4}}
            elif verdict == "non-compliant":
                return {"status": "NON-COMPLIANT", "source": "initial_auditor", "details": {"verdict": verdict, "step": 4}}
        errors = initial_auditor_result.get("errors", [])
        if errors:
            return {"status": "NON-COMPLIANT", "source": "initial_auditor", "details": {"reason": "auditor_errors", "errors": errors, "step": 4}}
    
    return {"status": "UNKNOWN", "source": "none", "details": {"reason": "no_auditor_verdict_found"}}

