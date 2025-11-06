#!/usr/bin/env python3
"""
Orchestrator V3 Run Utility
Handles the main run orchestration flow.
"""

from typing import Dict, Any

from utils_logging import setup_orchestration_logger, format_parameter_bundle, attach_stdio_to_logger
from utils_orchestrator_logging import OrchestratorLogger
from utils_adk_monitoring import get_global_monitor
from utils_orchestrator_compliance import extract_compliance_from_results
from utils_audit_compare import summarize_comparisons


async def run_orchestrator_v3(orchestrator_instance, base_name: str) -> Dict[str, Any]:
    """
    Run the orchestrator for a given base name with v3 pipeline processing.
    
    Args:
        orchestrator_instance: Orchestrator instance
        base_name: Base name of the NetLogo files to process
        
    Returns:
        Dictionary containing all processing results
    """
    tv = orchestrator_instance.agent_configs["lucim_operation_model_generator"].get("text_verbosity", "medium")
    reff = orchestrator_instance.agent_configs["lucim_operation_model_generator"].get("reasoning_effort", "medium")
    rsum = orchestrator_instance.agent_configs["lucim_operation_model_generator"].get("reasoning_summary", "auto")
    
    orchestrator_instance.logger = setup_orchestration_logger(
        base_name, orchestrator_instance.model, orchestrator_instance.timestamp,
        reasoning_effort=reff, text_verbosity=tv,
        persona_set=orchestrator_instance.selected_persona_set or orchestrator_instance.persona_set,
        version="v3-adk"
    )
    
    orchestrator_instance.orchestrator_logger = OrchestratorLogger(orchestrator_instance.logger)
    attach_stdio_to_logger(orchestrator_instance.logger)
    orchestrator_instance.adk_monitor = get_global_monitor(external_logger=orchestrator_instance.logger)
    
    orchestrator_instance.logger.info("[ADK] ADK monitoring initialized with orchestrator logger")
    orchestrator_instance.logger.info(f"Using persona set: {orchestrator_instance.selected_persona_set}")
    orchestrator_instance.logger.info(format_parameter_bundle(
        model=orchestrator_instance.model, base_name=base_name,
        reasoning_effort=reff, reasoning_summary=rsum, text_verbosity=tv
    ))
    orchestrator_instance.logger.info(f"Starting v3 pipeline processing for base name: {base_name} (ADK mode)")
    
    files = orchestrator_instance.fileio.find_netlogo_files(base_name)
    if not files:
        return {"error": f"No files found for base name '{base_name}'", "results": {}}
    
    results = {}
    for file_info in files:
        base_name = file_info["base_name"]
        results[base_name] = await orchestrator_instance.process_netlogo_file_v3_adk(file_info)
        orchestrator_instance.orchestrator_logger.log_workflow_status(base_name, results[base_name])
        orchestrator_instance.orchestrator_logger.log_error_details(results[base_name])
    
    return finalize_run_results(orchestrator_instance, base_name, files, results)


def finalize_run_results(orchestrator_instance, base_name: str, files: list, results: Dict[str, Any]) -> Dict[str, Any]:
    """Finalize and log run results summary."""
    orchestrator_instance.logger.info(f"Completed processing for {base_name}")
    orchestrator_instance.logger.info(f"\n{'='*60}\nORCHESTRATION SUMMARY FOR: {base_name}\n{'='*60}")
    
    final_result = results.get(base_name, {})
    # Some failure paths wrap actual step outputs under "results".
    # Use the inner dict for logging when present so audits are not N/A.
    effective_results = final_result.get("results", final_result) if isinstance(final_result, dict) else {}
    orchestrator_instance.orchestrator_logger.log_execution_timing(orchestrator_instance.execution_times)
    orchestrator_instance.orchestrator_logger.log_detailed_agent_status(effective_results)
    orchestrator_instance.orchestrator_logger.log_audit_analysis(effective_results)
    orchestrator_instance.orchestrator_logger.log_output_files(
        base_name, orchestrator_instance.timestamp, orchestrator_instance.model, effective_results
    )
    
    successful_agents = sum(1 for key, value in effective_results.items() 
                           if isinstance(value, dict) and value.get("data") is not None)
    total_agents = len([k for k in effective_results.keys() 
                       if k not in ["execution_times", "token_usage", "detailed_timing"]])
    
    final_compliance = extract_compliance_from_results(effective_results)
    orchestrator_instance.orchestrator_logger.log_pipeline_completion(successful_agents, total_agents, final_compliance)
    orchestrator_instance.orchestrator_logger.log_compliance_status(final_compliance)

    # Auditor metrics (step 6 vs step 8)
    initial_audit = effective_results.get("lucim_plantuml_diagram_auditor") or {}
    final_audit = {}
    if isinstance(initial_audit, dict) and isinstance(final_audit, dict) and initial_audit and final_audit:
        orchestrator_instance.orchestrator_logger.log_auditor_metrics(initial_audit, final_audit)

    orchestrator_instance.logger.info(f"{'='*60}")

    # SUMMARY: auditor vs python unit-test-like deterministic auditors
    comparisons = (final_result or {}).get("auditor_vs_python") or {}
    if comparisons:
        agg = summarize_comparisons(comparisons)
        orchestrator_instance.logger.info("[AUDIT-COMPARE] Summary (agent auditors vs deterministic Python):")
        orchestrator_instance.logger.info(
            f"[AUDIT-COMPARE] Matches: {agg.get('matches',0)}/{agg.get('total',0)} | Mismatches: {agg.get('mismatches',0)}"
        )
        for stage, cmpres in comparisons.items():
            status = "MATCH" if cmpres.get('match') else "MISMATCH"
            orchestrator_instance.logger.info(
                f"[AUDIT-COMPARE] {stage}: {status} (agent={cmpres.get('agent_verdict')}, python={cmpres.get('python_verdict')})"
            )
    
    return {
        "base_name": base_name,
        "files_processed": len(files),
        "total_agents": total_agents,
        "successful_agents": successful_agents,
        "failed_agents": total_agents - successful_agents,
        "success_rate": (successful_agents/total_agents)*100 if total_agents > 0 else 0,
        "results": results,
        "final_compliance": final_compliance
    }

