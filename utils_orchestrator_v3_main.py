#!/usr/bin/env python3
"""
Orchestrator V3 Main Entry Point Utility
Main execution function for the V3 ADK orchestrator.
"""

import os
import pathlib
import time
from typing import Dict, Any

from utils_orchestrator_ui import OrchestratorUI
from orchestrator_persona_v3_adk import NetLogoOrchestratorPersonaV3ADK


async def main():
    """Main execution function - persona v3 ADK version."""
    try:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        os.environ.setdefault("INPUT_PERSONA_DIR", str(repo_root / "experimentation" / "input" / "input-persona"))
        os.environ.setdefault("INPUT_NETLOGO_DIR", str(repo_root / "experimentation" / "input" / "input-netlogo"))
        os.environ.setdefault("INPUT_VALID_EXAMPLES_DIR", str(repo_root / "experimentation" / "input" / "input-valid-examples"))
    except Exception:
        pass
    
    ui = OrchestratorUI()
    if not ui.validate_openai_key():
        return
    
    base_names = ui.get_available_base_names()
    if not base_names:
        return
    
    selected_models = ui.select_models()
    if not selected_models:
        return
    
    selected_base_names = ui.select_base_names(base_names)
    if not selected_base_names:
        return
    
    timeout_seconds, timeout_preset = ui.select_timeout_preset()
    reasoning_levels = ui.select_reasoning_effort()
    if not reasoning_levels:
        return
    
    selected_verbosity_levels = ui.select_text_verbosity()
    # Ask for max_correction when running orchestrator directly
    try:
        mc_input = input("Max correction iterations [Enter for 2]: ").strip()
        if mc_input:
            mc_val = int(mc_input)
            if mc_val < 0:
                raise ValueError("max_correction must be >= 0")
            os.environ["MAX_CORRECTION"] = str(mc_val)
        else:
            os.environ.setdefault("MAX_CORRECTION", "2")
    except Exception as e:
        print(f"[WARN] Invalid max_correction input, using default 2 ({e})")
        os.environ["MAX_CORRECTION"] = "2"
    all_results = {}
    total_combinations = (
        len(selected_models) * len(selected_base_names) *
        len(reasoning_levels) * len(selected_verbosity_levels)
    )
    current_combination = 0
    total_execution_start_time = time.time()
    
    for model in selected_models:
        for base_name in selected_base_names:
            for reasoning_config in reasoning_levels:
                orchestrator = NetLogoOrchestratorPersonaV3ADK(model_name=model)
                orchestrator.update_reasoning_config(reasoning_config["effort"], reasoning_config["summary"])
                
                for verbosity in selected_verbosity_levels:
                    current_combination += 1
                    ui.print_combination_header(current_combination, total_combinations)
                    orchestrator.update_text_config(verbosity)
                    ui.print_parameter_bundle(
                        model=model, base_name=base_name,
                        reasoning_effort=reasoning_config["effort"],
                        reasoning_summary=reasoning_config["summary"],
                        text_verbosity=verbosity,
                    )
                    
                    results = await orchestrator.run(base_name)
                    
                    reasoning_suffix = f"{reasoning_config['effort']}-{reasoning_config['summary']}"
                    result_key = f"{base_name}_{model}_{reasoning_suffix}_{verbosity}"
                    all_results[result_key] = results
    
    total_execution_time = time.time() - total_execution_start_time
    total_files = len(all_results)
    total_agents = 0
    total_successful_agents = 0
    
    agent_keys = [
        "lucim_operation_synthesizer", "lucim_scenario_synthesizer",
        "plantuml_writer", "plantuml_lucim_auditor", "plantuml_lucim_corrector", "plantuml_lucim_final_auditor"
    ]
    
    for result_key, result in all_results.items():
        if result and isinstance(result.get("results"), dict) and result["results"]:
            inner_results = next(iter(result["results"].values()))
            if isinstance(inner_results, dict):
                for key in agent_keys:
                    if key in inner_results:
                        total_agents += 1
                        agent_result = inner_results.get(key) or {}
                        if isinstance(agent_result, dict) and agent_result.get("data"):
                            total_successful_agents += 1
    
    overall_success_rate = (total_successful_agents / total_agents * 100) if total_agents > 0 else 0
    
    ui.print_final_summary(
        total_execution_time, total_files, total_agents,
        total_successful_agents, overall_success_rate, all_results
    )

