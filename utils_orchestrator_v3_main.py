#!/usr/bin/env python3
"""
Orchestrator V3 Main Entry Point Utility
Main execution function for the V3 ADK orchestrator.
"""

import os
import asyncio
import pathlib
import time
from typing import Dict, Any

from utils_orchestrator_ui import OrchestratorUI
from orchestrator_persona_v3_adk import NetLogoOrchestratorPersonaV3ADK
from utils_orchestrator_v3_agent_config import update_agent_configs


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
    # Note: API key validation will be done per-model after selection
    # to support different providers (OpenAI, Gemini, OpenRouter)
    
    base_names = ui.get_available_base_names()
    if not base_names:
        return
    
    selected_models = ui.select_models()
    if not selected_models:
        return
    
    # Validate API keys for selected models (supports different providers)
    print("\n🔍 Validating API keys for selected models...")
    for model in selected_models:
        if not ui.validate_openai_key(model_name=model):
            print(f"❌ API key validation failed for model: {model}")
            print("   Please ensure the appropriate API key is set in your .env file:")
            from utils_api_key import get_provider_for_model
            provider = get_provider_for_model(model)
            if provider == "gemini":
                print("   GEMINI_API_KEY=your-gemini-api-key")
            elif provider == "router":
                print("   OPENROUTER_API_KEY=your-openrouter-api-key")
            else:
                print("   OPENAI_API_KEY=your-openai-api-key")
            return
    print("✅ API key validation successful for all selected models")
    
    selected_base_names = ui.select_base_names(base_names)
    if not selected_base_names:
        return
    
    timeout_seconds, timeout_preset = ui.select_timeout_preset()
    reasoning_levels = ui.select_reasoning_effort()
    if not reasoning_levels:
        return
    
    selected_verbosity_levels = ui.select_text_verbosity()
    # Ask for MAX_AUDIT when running orchestrator directly
    try:
        ma_input = input("Max audit iterations (MAX_AUDIT) [Enter for 3]: ").strip()
        if ma_input:
            ma_val = int(ma_input)
            if ma_val < 0:
                raise ValueError("MAX_AUDIT must be >= 0")
            os.environ["MAX_AUDIT"] = str(ma_val)
        else:
            os.environ.setdefault("MAX_AUDIT", "3")
    except Exception as e:
        print(f"[WARN] Invalid MAX_AUDIT input, using default 3 ({e})")
        os.environ["MAX_AUDIT"] = "3"
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
                update_agent_configs(
                    orchestrator,
                    reasoning_effort=reasoning_config["effort"],
                    reasoning_summary=reasoning_config["summary"],
                    text_verbosity=None,
                )
                
                for verbosity in selected_verbosity_levels:
                    current_combination += 1
                    ui.print_combination_header(current_combination, total_combinations)
                    update_agent_configs(
                        orchestrator,
                        reasoning_effort=None,
                        reasoning_summary=None,
                        text_verbosity=verbosity,
                    )
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
        "lucim_operation_model_generator", "lucim_operation_model_auditor", "lucim_scenario_generator", "lucim_scenario_auditor", "lucim_plantuml_diagram_generator", "lucim_plantuml_diagram_auditor",
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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Orchestrator interrupted by user.")
