#!/usr/bin/env python3
"""
ADK Workflow Steps Builder Utility
Builds workflow steps for the V3 ADK orchestrator pipeline.
"""

import pathlib
from typing import Dict, Any, List, Tuple, Callable, Optional

from utils_adk_step_adapter import AgentStepAdapter
from utils_adk_v3_workflow import condition_check_audit_result
from utils_config_constants import LUCIM_RULES_FILE


def build_v3_workflow_steps(orchestrator_instance,
                           base_name: str,
                           run_dir: pathlib.Path,
                           code_content: str,
                           lucim_dsl_content: str,
                           netlogo_lucim_mapping_content: str) -> List[Tuple]:
    """
    Build workflow steps for V3 ADK pipeline.
    
    Args:
        orchestrator_instance: Orchestrator instance
        base_name: Base name of the NetLogo file
        run_dir: Run directory for output files
        code_content: NetLogo code content
        lucim_dsl_content: LUCIM DSL content
        netlogo_lucim_mapping_content: NetLogo to LUCIM mapping content
        
    Returns:
        List of (step_adapter, static_args, options) tuples
    """
    steps = []
    
    # Step 1: LUCIM Operation Synthesizer
    step1 = AgentStepAdapter(
        orchestrator_instance, orchestrator_instance.lucim_operation_synthesizer_agent,
        "synthesize_lucim_operation_from_source_code",
        "lucim_operation_synthesizer", 1, base_name, orchestrator_instance.model, run_dir
    )
    steps.append((step1, [code_content, lucim_dsl_content, netlogo_lucim_mapping_content], {}))
    
    # Step 2: LUCIM Scenario Synthesizer (conditional on step 1 success)
    def check_step1_success(results):
        return results.get("lucim_operation_synthesizer", {}).get("data") is not None
    
    step2 = AgentStepAdapter(
        orchestrator_instance, orchestrator_instance.lucim_scenario_synthesizer_agent,
        "write_scenarios",
        "lucim_scenario_synthesizer", 2, base_name, orchestrator_instance.model, run_dir,
        conditional_check=check_step1_success
    )
    
    def get_step2_args():
        return [
            orchestrator_instance.processed_results["lucim_operation_synthesizer"]["data"],
            lucim_dsl_content
        ]
    
    steps.append((step2, None, {"dynamic_args": get_step2_args}))
    
    # Step 3: PlantUML Writer (conditional on step 2 success)
    def check_step2_success(results):
        return results.get("lucim_scenario_synthesizer", {}).get("data") is not None
    
    step3 = AgentStepAdapter(
        orchestrator_instance, orchestrator_instance.plantuml_writer_agent,
        "generate_plantuml_diagrams",
        "plantuml_writer", 3, base_name, orchestrator_instance.model, run_dir,
        conditional_check=check_step2_success
    )
    
    def get_step3_args():
        return [orchestrator_instance.processed_results["lucim_scenario_synthesizer"]["data"]]
    
    steps.append((step3, None, {"dynamic_args": get_step3_args}))
    
    # Step 4: PlantUML Auditor (conditional on step 3 success)
    def check_step3_success(results):
        if not results.get("plantuml_writer", {}).get("data"):
            return False
        plantuml_dir = orchestrator_instance.fileio.create_agent_output_directory(run_dir, 3, "plantuml_writer")
        plantuml_file_path = orchestrator_instance.fileio.get_plantuml_file_path(plantuml_dir)
        return plantuml_file_path and orchestrator_instance.fileio.validate_plantuml_file(plantuml_file_path)
    
    step4 = AgentStepAdapter(
        orchestrator_instance, orchestrator_instance.plantuml_lucim_auditor_agent,
        "audit_plantuml_diagrams",
        "plantuml_lucim_auditor", 4, base_name, orchestrator_instance.model, run_dir,
        conditional_check=check_step3_success
    )
    
    def get_step4_args():
        plantuml_dir = orchestrator_instance.fileio.create_agent_output_directory(run_dir, 3, "plantuml_writer")
        plantuml_file_path = orchestrator_instance.fileio.get_plantuml_file_path(plantuml_dir)
        return [plantuml_file_path, str(LUCIM_RULES_FILE)]
    
    steps.append((step4, None, {"dynamic_args": get_step4_args}))
    
    # Step 5: PlantUML Corrector (conditional on non-compliant audit)
    step5 = AgentStepAdapter(
        orchestrator_instance, orchestrator_instance.plantuml_lucim_corrector_agent,
        "correct_plantuml_diagrams",
        "plantuml_lucim_corrector", 5, base_name, orchestrator_instance.model, run_dir,
        conditional_check=condition_check_audit_result
    )
    
    def get_step5_args():
        return [
            orchestrator_instance.processed_results["plantuml_writer"]["data"],
            orchestrator_instance.processed_results["plantuml_lucim_auditor"]["data"],
            lucim_dsl_content
        ]
    
    steps.append((step5, None, {"dynamic_args": get_step5_args}))
    
    # Step 6: Final Auditor (conditional on corrector execution)
    def check_corrector_success(results):
        return results.get("plantuml_lucim_corrector", {}).get("data") is not None
    
    step6 = AgentStepAdapter(
        orchestrator_instance, orchestrator_instance.plantuml_lucim_final_auditor_agent,
        "audit_plantuml_diagrams",
        "plantuml_lucim_final_auditor", 6, base_name, orchestrator_instance.model, run_dir,
        conditional_check=check_corrector_success
    )
    
    def get_step6_args():
        corrector_dir = orchestrator_instance.fileio.create_agent_output_directory(run_dir, 5, "plantuml_lucim_corrector")
        corrected_plantuml_file_path = orchestrator_instance.fileio.get_plantuml_file_path(corrector_dir)
        return [corrected_plantuml_file_path, str(LUCIM_RULES_FILE), 6]
    
    steps.append((step6, None, {"dynamic_args": get_step6_args}))
    
    return steps

