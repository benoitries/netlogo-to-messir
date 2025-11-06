#!/usr/bin/env python3
"""
ADK Workflow Steps Builder Utility
Builds workflow steps for the V3 ADK orchestrator pipeline.
"""

import pathlib
from typing import List, Tuple

from utils_adk_step_adapter import AgentStepAdapter
from utils_config_constants import RULES_LUCIM_PLANTUML_DIAGRAM


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
        orchestrator_instance, orchestrator_instance.lucim_operation_model_generator_agent,
        "generate_lucim_operation_model",
        "lucim_operation_model_generator", 1, base_name, orchestrator_instance.model, run_dir
    )
    steps.append((step1, [code_content, netlogo_lucim_mapping_content, None, None], {}))
    
    # Step 2: LUCIM Scenario Generator (conditional on step 1 success)
    def check_step1_success(results):
        return results.get("lucim_operation_model_generator", {}).get("data") is not None
    
    step2 = AgentStepAdapter(
        orchestrator_instance, orchestrator_instance.lucim_scenario_generator_agent,
        "generate_scenarios",
        "lucim_scenario_generator", 2, base_name, orchestrator_instance.model, run_dir,
        conditional_check=check_step1_success
    )
    
    def get_step2_args():
        # For first run, scenario auditor feedback and previous scenario are empty
        scenario_auditor_feedback = None
        previous_scenario = None
        return [
            orchestrator_instance.processed_results["lucim_operation_model_generator"]["data"],
            lucim_dsl_content,
            scenario_auditor_feedback,
            previous_scenario,
        ]
    
    steps.append((step2, None, {"dynamic_args": get_step2_args}))
    
    # Step 3: PlantUML Writer (conditional on step 2 success)
    def check_step2_success(results):
        return results.get("lucim_scenario_generator", {}).get("data") is not None
    
    step3 = AgentStepAdapter(
        orchestrator_instance, orchestrator_instance.lucim_plantuml_diagram_generator_agent,
        "generate_plantuml_diagrams",
        "lucim_plantuml_diagram_generator", 3, base_name, orchestrator_instance.model, run_dir,
        conditional_check=check_step2_success
    )
    
    def get_step3_args():
        # First run: required params provided but empty/None as allowed
        return [
            orchestrator_instance.processed_results["lucim_scenario_generator"]["data"],
            [],
            None,
        ]
    
    steps.append((step3, None, {"dynamic_args": get_step3_args}))
    
    # Step 4: PlantUML Auditor (conditional on step 3 success)
    def check_step3_success(results):
        if not results.get("lucim_plantuml_diagram_generator", {}).get("data"):
            return False
        plantuml_dir = orchestrator_instance.fileio.create_agent_output_directory(run_dir, 3, "lucim_plantuml_diagram_generator")
        plantuml_file_path = orchestrator_instance.fileio.get_plantuml_file_path(plantuml_dir)
        return plantuml_file_path and orchestrator_instance.fileio.validate_plantuml_file(plantuml_file_path)
    
    step4 = AgentStepAdapter(
        orchestrator_instance, orchestrator_instance.lucim_plantuml_diagram_auditor_agent,
        "audit_plantuml_diagrams",
        "lucim_plantuml_diagram_auditor", 4, base_name, orchestrator_instance.model, run_dir,
        conditional_check=check_step3_success
    )
    
    def get_step4_args():
        plantuml_dir = orchestrator_instance.fileio.create_agent_output_directory(run_dir, 3, "lucim_plantuml_diagram_generator")
        plantuml_file_path = orchestrator_instance.fileio.get_plantuml_file_path(plantuml_dir)
        return [plantuml_file_path]
    
    steps.append((step4, None, {"dynamic_args": get_step4_args}))
    
    # Note: No corrector/final auditor steps per policy (deterministic flow)
    return steps

