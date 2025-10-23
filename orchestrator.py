#!/usr/bin/env python3
"""
NetLogo Orchestrator Agent
Orchestrates the processing of NetLogo files using Syntax and Semantics agents in parallel using Google ADK inspired ParallelAgent.
"""

import os
import asyncio
import json
import datetime
import pathlib
import time
import logging
from typing import Dict, Any, List

from agent_1_netlogo_abstract_syntax_extractor import NetLogoAbstractSyntaxExtractorAgent
from agent_2_netlogo_behavior_extractor import NetLogoBehaviorExtractorAgent
from agent_3_lucim_environment_synthesizer import NetLogoLucimEnvironmentSynthesizerAgent
from agent_4_lucim_scenario_synthesizer import NetLogoLUCIMScenarioSynthesizerAgent
from agent_5_plantuml_writer import NetLogoPlantUMLWriterAgent
from agent_6_plantuml_auditor import NetLogoPlantUMLLUCIMAuditorAgent
from utils_format import FormatUtils
from agent_7_plantuml_corrector import NetLogoPlantUMLLUCIMCorrectorAgent

from utils_config_constants import (
    INPUT_NETLOGO_DIR, OUTPUT_DIR, INPUT_PERSONA_DIR,
    AGENT_CONFIGS, AVAILABLE_MODELS, DEFAULT_MODEL, ensure_directories,
    validate_agent_response, LUCIM_RULES_FILE
)
from utils_logging import setup_orchestration_logger, format_parameter_bundle, attach_stdio_to_logger
from utils_path import get_run_base_dir
from pathlib import Path
from utils_config_constants import OUTPUT_DIR

# Ensure all directories exist
ensure_directories()

class NetLogoOrchestrator:
    """Orchestrator for processing NetLogo files using NetLogo Abstract Syntax Extractor and Semantics agents in parallel."""
    
    def __init__(self, model_name: str = DEFAULT_MODEL):
        """
        Initialize the NetLogo Orchestrator.
        
        Args:
            model_name: AI model to use for processing
        """
        self.model = model_name
        # Format: YYYYMMDD_HHMM for better readability
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        self.step_counter = 1  # Initialize step counter
        
        # Initialize logger (will be set up properly when processing starts)
        self.logger = None
        
        # Timing tracking
        self.execution_times = {
            "total_orchestration": 0,
            "netlogo_abstract_syntax_extractor": 0,
            "behavior_extractor": 0,
            "lucim_environment_synthesizer": 0,
            "lucim_scenario_synthesizer": 0,
            "plantuml_writer": 0,
            "plantuml_lucim_auditor": 0,
            "plantuml_lucim_corrector": 0,
            "plantuml_lucim_final_auditor": 0
        }
        
        # Token usage tracking (no caps)
        self.token_usage = {
            "netlogo_abstract_syntax_extractor": {"used": 0},
            "behavior_extractor": {"used": 0},
            "lucim_environment_synthesizer": {"used": 0},
            "lucim_scenario_synthesizer": {"used": 0},
            "plantuml_writer": {"used": 0},
            "plantuml_lucim_auditor": {"used": 0},
            "plantuml_lucim_corrector": {"used": 0},
            "plantuml_lucim_final_auditor": {"used": 0}
        }
        
        # Detailed timing tracking with start/end timestamps
        self.detailed_timing = {
            "netlogo_abstract_syntax_extractor": {"start": 0, "end": 0, "duration": 0},
            "behavior_extractor": {"start": 0, "end": 0, "duration": 0},
            "lucim_environment_synthesizer": {"start": 0, "end": 0, "duration": 0},
            "lucim_scenario_synthesizer": {"start": 0, "end": 0, "duration": 0},
            "plantuml_writer": {"start": 0, "end": 0, "duration": 0},
            "plantuml_lucim_auditor": {"start": 0, "end": 0, "duration": 0},
            "plantuml_lucim_corrector": {"start": 0, "end": 0, "duration": 0},
            "plantuml_lucim_final_auditor": {"start": 0, "end": 0, "duration": 0}
        }
        
        # Token caps removed entirely
        
        
        # Store agent configurations for reasoning level updates
        self.agent_configs = AGENT_CONFIGS.copy()
        
        # Initialize agents (no max token caps)
        self.netlogo_abstract_syntax_extractor_agent = NetLogoAbstractSyntaxExtractorAgent(model_name, self.timestamp)
        # Pass IL-SYN file absolute paths to syntax parser agent (can be overridden externally)
        try:
            base_dir = pathlib.Path(__file__).resolve().parent
            ilsyn_mapping_path = (base_dir / "input-persona" / "DSL_IL_SYN-mapping.md").resolve()
            ilsyn_description_path = (base_dir / "input-persona" / "DSL_IL_SYN-description.md").resolve()
            if hasattr(self.netlogo_abstract_syntax_extractor_agent, "update_il_syn_inputs"):
                self.netlogo_abstract_syntax_extractor_agent.update_il_syn_inputs(str(ilsyn_mapping_path), str(ilsyn_description_path))
            else:
                # Backward compatibility: set attributes directly if method unavailable
                self.netlogo_abstract_syntax_extractor_agent.il_syn_mapping_path = str(ilsyn_mapping_path)
                self.netlogo_abstract_syntax_extractor_agent.il_syn_description_path = str(ilsyn_description_path)
            print("OK: Configured IL-SYN reference paths for NetLogo Abstract Syntax Extractor")
        except Exception as e:
            print(f"[WARNING] Unable to set IL-SYN paths for NetLogo Abstract Syntax Extractor: {e}")
        self.behavior_extractor_agent = NetLogoBehaviorExtractorAgent(model_name, self.timestamp)
        # Configure IL-SEM inputs for semantics agent (absolute paths)
        il_sem_mapping = INPUT_PERSONA_DIR / "DSL_IL_SEM-mapping.md"
        il_sem_description = INPUT_PERSONA_DIR / "DSL_IL_SEM-description.md"
        if hasattr(self.behavior_extractor_agent, "update_il_sem_inputs"):
            self.behavior_extractor_agent.update_il_sem_inputs(str(il_sem_mapping), str(il_sem_description))
        self.lucim_environment_synthesizer_agent = NetLogoLucimEnvironmentSynthesizerAgent(model_name, self.timestamp)
        self.lucim_scenario_synthesizer_agent = NetLogoLUCIMScenarioSynthesizerAgent(model_name, self.timestamp)
        self.plantuml_writer_agent = NetLogoPlantUMLWriterAgent(model_name, self.timestamp)
        self.plantuml_lucim_auditor_agent = NetLogoPlantUMLLUCIMAuditorAgent(model_name, self.timestamp)
        self.plantuml_lucim_corrector_agent = NetLogoPlantUMLLUCIMCorrectorAgent(model_name, self.timestamp)
        self.plantuml_lucim_final_auditor_agent = NetLogoPlantUMLLUCIMAuditorAgent(model_name, self.timestamp)

    def update_agent_configs(self, reasoning_effort: str = None, reasoning_summary: str = None, text_verbosity: str = None):
        """
        Update configuration for all agents.
        
        Args:
            reasoning_effort: "minimal", "low", "medium", or "high"
            reasoning_summary: "auto" or "manual"
            text_verbosity: "low", "medium", or "high"
        """
        # Update agent configuration dictionaries
        for agent_name in self.agent_configs:
            if reasoning_effort is not None:
                self.agent_configs[agent_name]["reasoning_effort"] = reasoning_effort
            if reasoning_summary is not None:
                self.agent_configs[agent_name]["reasoning_summary"] = reasoning_summary
            if text_verbosity is not None:
                self.agent_configs[agent_name]["text_verbosity"] = text_verbosity

        # List of (agent attr, text_support_flag)
        agent_list = [
            ("netlogo_abstract_syntax_extractor_agent", True),
            ("behavior_extractor_agent", True),
            ("lucim_environment_synthesizer_agent", True),
            ("lucim_scenario_synthesizer_agent", True),
            ("plantuml_writer_agent", True),
            ("plantuml_lucim_auditor_agent", True),
            ("plantuml_lucim_corrector_agent", True),
            ("plantuml_lucim_final_auditor_agent", True),
        ]

        for agent_attr, supports_text in agent_list:
            agent = getattr(self, agent_attr, None)
            if agent is not None:
                # Prefer unified apply_config if available
                bundle = {}
                if reasoning_effort is not None:
                    bundle["reasoning_effort"] = reasoning_effort
                if reasoning_summary is not None:
                    bundle["reasoning_summary"] = reasoning_summary
                if text_verbosity is not None:
                    bundle["text_verbosity"] = text_verbosity

                if hasattr(agent, "apply_config") and bundle:
                    try:
                        agent.apply_config(bundle)
                        continue
                    except Exception as e:
                        print(f"[WARNING] apply_config failed on {agent_attr}: {e}; falling back to legacy setters")

                # Fallback to legacy setters
                if reasoning_effort is not None and reasoning_summary is not None and hasattr(agent, "update_reasoning_config"):
                    agent.update_reasoning_config(reasoning_effort, reasoning_summary)
                if text_verbosity is not None and hasattr(agent, "update_text_config"):
                    agent.update_text_config(text_verbosity)

    def update_reasoning_config(self, reasoning_effort: str, reasoning_summary: str):
        """Backward-compatible wrapper to update reasoning across agents."""
        self.update_agent_configs(reasoning_effort=reasoning_effort, reasoning_summary=reasoning_summary)

    def update_text_config(self, text_verbosity: str):
        """Backward-compatible wrapper to update text verbosity across agents."""
        self.update_agent_configs(text_verbosity=text_verbosity)

    
    def find_netlogo_files(self, base_name: str) -> List[Dict[str, Any]]:
        """
        Find NetLogo files matching the given base name.
        
        Args:
            base_name: Base name to search for (e.g., "climate-change", "ecosys")
            
        Returns:
            List of dictionaries containing file information
        """
        files = []
        
        # Support both legacy and new naming conventions
        candidate_files = [
            INPUT_NETLOGO_DIR / f"{base_name}-netlogo-code.md",
            INPUT_NETLOGO_DIR / f"{base_name}-code.md",
        ]
        
        code_file = next((p for p in candidate_files if p.exists()), None)
        
        if code_file is not None:
            # Find corresponding interface images
            interface_images = []
            for img_file in INPUT_NETLOGO_DIR.glob(f"{base_name}-netlogo-interface-*.png"):
                interface_images.append(str(img_file))
            
            files.append({
                "code_file": code_file,
                "interface_images": interface_images,
                "base_name": base_name
            })
        else:
            if self.logger:
                self.logger.warning(f"Warning: No code file found for base name '{base_name}'")
        
        return files
    
    
    def _execute_agent_with_tracking(self, agent_name: str, agent_func, *args, **kwargs):
        """
        Execute an agent with detailed timing and token tracking.
        
        Args:
            agent_name: Name of the agent
            agent_func: Agent function to execute
            *args, **kwargs: Arguments for the agent function
            
        Returns:
            Agent execution result
        """
        # Start timing
        start_time = time.time()
        self.detailed_timing[agent_name]["start"] = start_time
        
        self.logger.info(f"🚀 Starting {agent_name} agent execution...")
        # No max tokens configured
        
        try:
            # Execute the agent
            result = agent_func(*args, **kwargs)
            
            # End timing
            end_time = time.time()
            duration = end_time - start_time
            self.detailed_timing[agent_name]["end"] = end_time
            self.detailed_timing[agent_name]["duration"] = duration
            
            # Update execution times
            self.execution_times[agent_name] = duration
            
            # Extract token usage from result (if available)
            if result and isinstance(result, dict):
                # Try to extract token usage from the result
                tokens_used = result.get("tokens_used", 0)
                input_tokens = result.get("input_tokens", 0)
                output_tokens = result.get("output_tokens", 0)
                reasoning_tokens = result.get("reasoning_tokens", 0)
                self.token_usage[agent_name]["used"] = tokens_used
                
                self.logger.info(f"✅ {agent_name} completed in {FormatUtils.format_duration(duration)}")
                # Clarified logging: no token caps, just report numbers
                # Explicitly separate visible vs reasoning output tokens, and their sum
                # Prefer explicit fields if present in result
                explicit_visible = result.get("visible_output_tokens") if isinstance(result, dict) else None
                # Prefer API output_tokens (completion channel, reasoning+visible) for total output
                # Treat 0 or negative as unavailable to avoid inconsistent zeros when visible/reasoning are present
                explicit_total_out = None
                try:
                    if output_tokens is not None and int(output_tokens) > 0:
                        explicit_total_out = int(output_tokens)
                except Exception:
                    explicit_total_out = None
                reasoning_output_tokens = (reasoning_tokens or 0)
                # Derive visible: prefer explicit; else from total_output - reasoning; else output - reasoning; clamp >= 0
                derived_visible = None
                if explicit_visible is not None:
                    derived_visible = int(explicit_visible)
                elif explicit_total_out is not None:
                    derived_visible = int(explicit_total_out) - reasoning_output_tokens
                else:
                    derived_visible = (output_tokens or 0) - reasoning_output_tokens
                visible_output_tokens = max(int(derived_visible), 0)
                # Derive total output: prefer explicit (when positive); else visible + reasoning
                total_output_tokens = (
                    int(explicit_total_out)
                    if explicit_total_out is not None
                    else (visible_output_tokens + reasoning_output_tokens)
                )

                self.logger.info(f"   Input Tokens = {input_tokens:,}")
                self.logger.info(
                    f"   Output Tokens = {total_output_tokens:,} ( reasoning = {reasoning_output_tokens:,}, visibleOutput={visible_output_tokens:,})"
                )
                self.logger.info(
                    f"   Total Tokens = {tokens_used:,}"
                )
            else:
                self.logger.info(f"✅ {agent_name} completed in {FormatUtils.format_duration(duration)}")
                self.logger.info(f"   Token usage: Not available")
            
            return result
            
        except Exception as e:
            # End timing even on error
            end_time = time.time()
            duration = end_time - start_time
            self.detailed_timing[agent_name]["end"] = end_time
            self.detailed_timing[agent_name]["duration"] = duration
            self.execution_times[agent_name] = duration
            
            self.logger.error(f"❌ {agent_name} failed after {FormatUtils.format_duration(duration)}: {str(e)}")
            raise
    
    def _generate_detailed_summary(self, base_name: str, processed_results: Dict[str, Any]):
        """
        Generate a detailed summary with timing and token usage information.
        """
        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"DETAILED EXECUTION SUMMARY FOR: {base_name}")
        self.logger.info(f"{'='*80}")
        
        # Define agent names first
        agent_names = [
            "netlogo_abstract_syntax_extractor", "behavior_extractor", "lucim_environment_synthesizer", "lucim_scenario_synthesizer",
            "plantuml_writer", "plantuml_lucim_auditor", "plantuml_lucim_corrector", "plantuml_lucim_final_auditor"
        ]
        
        # Calculate totals
        total_time = sum(self.detailed_timing[agent]["duration"] for agent in self.detailed_timing)
        total_tokens_used = sum(self.token_usage[agent]["used"] for agent in self.token_usage)
        # No token caps summary
        
        # Calculate input/output token totals from processed results
        agent_to_result_key = {
            "netlogo_abstract_syntax_extractor": "ast",
            "behavior_extractor": "semantics",
            "lucim_environment_synthesizer": "lucim_environment_synthesizer",
            "lucim_scenario_synthesizer": "lucim_scenario_synthesizer",
            "plantuml_writer": "plantuml_writer",
            "plantuml_lucim_auditor": "plantuml_lucim_auditor",
            "plantuml_lucim_corrector": "plantuml_lucim_corrector",
            "plantuml_lucim_final_auditor": "plantuml_lucim_final_auditor",
        }
        total_input_tokens = 0
        total_output_tokens = 0
        total_reasoning_tokens = 0
        for agent in agent_names:
            result_key = agent_to_result_key.get(agent, agent)
            if processed_results.get(result_key, {}).get("data"):
                total_input_tokens += processed_results[result_key].get("input_tokens", 0)
                total_output_tokens += processed_results[result_key].get("output_tokens", 0)
                total_reasoning_tokens += processed_results[result_key].get("reasoning_tokens", 0)
        
        # Agent execution summary table
        self.logger.info(f"\n📊 AGENT EXECUTION DETAILS:")
        self.logger.info(f"{'Agent':<25} {'Status':<10} {'Time':<15} {'Total Tokens':<15} {'Input':<10} {'VisibleOut':<12} {'Reasoning':<10} {'Output Tokens':<14}")
        self.logger.info(f"{'-'*120}")
        
        for agent in agent_names:
            duration = self.detailed_timing[agent]["duration"]
            tokens_used = self.token_usage[agent]["used"]
            result_key = agent_to_result_key.get(agent, agent)
            line_data = processed_results.get(result_key, {})
            input_tokens = line_data.get("input_tokens", 0)
            reasoning_tokens = line_data.get("reasoning_tokens", 0)
            explicit_visible = line_data.get("visible_output_tokens")
            explicit_total_out = line_data.get("total_output_tokens")
            # Robust derivation for summary row
            if explicit_visible is not None:
                visible_output_tokens = int(explicit_visible)
            elif explicit_total_out is not None:
                visible_output_tokens = int(explicit_total_out) - (reasoning_tokens or 0)
            else:
                visible_output_tokens = (line_data.get("output_tokens", 0) or 0) - (reasoning_tokens or 0)
            visible_output_tokens = max(int(visible_output_tokens), 0)
            total_output_tokens = int(explicit_total_out) if explicit_total_out is not None else (visible_output_tokens + (reasoning_tokens or 0))
            
            # Determine status prioritizing presence of data (loaded vs executed)
            data_present = bool(processed_results.get(result_key, {}).get("data"))
            if data_present and duration == 0:
                status = "✓ SUCCESS (loaded)"
            elif duration > 0 and data_present:
                status = "✓ SUCCESS"
            elif duration > 0 and not data_present:
                status = "✗ FAILED"
            else:
                status = "⏭️ SKIPPED"
                duration = 0
                tokens_used = 0
                input_tokens = 0
                visible_output_tokens = 0
                reasoning_tokens = 0
                total_output_tokens = 0
        
            # Log visible vs reasoning output tokens and their sum
            self.logger.info(
                f"{agent:<25} {status:<10} {FormatUtils.format_duration(duration):<15} {tokens_used:<15,} "
                f"{input_tokens:<10,} {visible_output_tokens:<12,} {reasoning_tokens:<10,} {total_output_tokens:<10,}"
            )
        
        # Overall summary
        self.logger.info(f"\n📈 OVERALL SUMMARY:")
        self.logger.info(f"   Total Execution Time: {FormatUtils.format_duration(total_time)}")
        self.logger.info(f"   Total Tokens Used: {total_tokens_used:,}")
        self.logger.info(f"   Total Input Tokens: {total_input_tokens:,}")
        self.logger.info(f"   Total Output Tokens: {total_output_tokens:,}")
        self.logger.info(f"   Total Reasoning Tokens: {total_reasoning_tokens:,}")
        # No Total Max Tokens or Efficiency (caps removed)
        
        # Performance metrics
        successful_agents = sum(1 for agent in agent_names if processed_results.get(agent, {}).get("data"))
        total_agents = len(agent_names)
        success_rate = (successful_agents / total_agents * 100) if total_agents > 0 else 0
        
        self.logger.info(f"   Successful Agents: {successful_agents}/{total_agents}")
        self.logger.info(f"   Success Rate: {success_rate:.1f}%")
        
        # Timing breakdown
        self.logger.info(f"\n⏱️ TIMING BREAKDOWN:")
        sorted_agents = sorted(agent_names, key=lambda x: self.detailed_timing[x]["duration"], reverse=True)
        for agent in sorted_agents:
            duration = self.detailed_timing[agent]["duration"]
            if duration > 0:
                percentage = (duration / total_time * 100) if total_time > 0 else 0
                self.logger.info(f"   {agent:<25}: {duration:.2f}s ({percentage:.1f}%)")
        
        self.logger.info(f"{'='*80}")
    
    def _generate_orchestration_summary(self, all_results: Dict[str, Any]):
        """
        Generate a comprehensive summary across all orchestrations.
        """
        self.logger.info(f"\n{'='*100}")
        self.logger.info(f"COMPREHENSIVE ORCHESTRATION SUMMARY")
        self.logger.info(f"{'='*100}")
        
        total_orchestrations = len(all_results)
        # Sum execution times and token totals from inner processed results per orchestration
        total_execution_time = 0
        total_input_tokens_all = 0
        total_output_tokens_all = 0
        total_reasoning_tokens_all = 0
        for orchestration_key, result in all_results.items():
            inner_results = None
            if isinstance(result.get("results"), dict) and result["results"]:
                inner_results = next(iter(result["results"].values()))
            if isinstance(inner_results, dict):
                total_execution_time += inner_results.get("execution_times", {}).get("total_orchestration", 0)
                # Sum input/output/reasoning tokens across agents for this orchestration
                agent_keys = [
                    "ast", "semantics", "lucim_environment_synthesizer", "lucim_scenario_synthesizer",
                    "plantuml_writer", "plantuml_lucim_auditor", "plantuml_lucim_corrector", "plantuml_lucim_final_auditor"
                ]
                for key in agent_keys:
                    if key in inner_results and isinstance(inner_results.get(key), dict):
                        total_input_tokens_all += inner_results[key].get("input_tokens", 0)
                        total_output_tokens_all += inner_results[key].get("output_tokens", 0)
                        total_reasoning_tokens_all += inner_results[key].get("reasoning_tokens", 0)
        
        # Per-orchestration summary table
        self.logger.info(f"\n📋 PER-ORCHESTRATION DETAILS:")
        self.logger.info(f"{'Orchestration':<30} {'Status':<10} {'Total Time':<20} {'Total Tokens':<15} {'Success Rate':<12}")
        self.logger.info(f"{'-'*85}")
        
        for orchestration_key, result in all_results.items():
            base_name, model = orchestration_key.split("_", 1)
            # Read time and tokens from the inner processed results
            inner_results = None
            if isinstance(result.get("results"), dict) and result["results"]:
                inner_results = next(iter(result["results"].values()))
            total_time = 0
            total_tokens = 0
            if isinstance(inner_results, dict):
                total_time = inner_results.get("execution_times", {}).get("total_orchestration", 0)
                total_tokens = sum(
                    inner_results.get("token_usage", {}).get(agent, {}).get("used", 0)
                    for agent in ["netlogo_abstract_syntax_extractor", "behavior_extractor", "lucim_environment_synthesizer", "scenario_writer", 
                                 "plantuml_writer", "plantuml_lucim_auditor", "plantuml_lucim_corrector", "plantuml_lucim_final_auditor"]
                )

            # Calculate success rate based on inner agent results of this orchestration
            inner_results = None
            if isinstance(result.get("results"), dict) and result["results"]:
                # There is typically one base_name key; take its dict
                inner_results = next(iter(result["results"].values()))

            agent_keys = [
                "ast", "semantics", "lucim_environment_synthesizer", "scenario_writer",
                "plantuml_writer", "plantuml_lucim_auditor", "plantuml_lucim_corrector", "plantuml_lucim_final_auditor"
            ]

            successful_agents = 0
            total_agents = 0
            if isinstance(inner_results, dict):
                for key in agent_keys:
                    if key in inner_results:
                        total_agents += 1
                        agent_result = inner_results.get(key) or {}
                        if isinstance(agent_result, dict) and agent_result.get("data"):
                            successful_agents += 1

            success_rate = (successful_agents / total_agents * 100) if total_agents > 0 else 0

            status = "✓ SUCCESS" if success_rate >= 80 else "⚠️ PARTIAL" if success_rate >= 50 else "✗ FAILED"

            self.logger.info(f"{orchestration_key:<30} {status:<10} {FormatUtils.format_duration(total_time):<20} {total_tokens:<15,} {success_rate:<12.1f}%")
        
        # Overall statistics
        # Aggregate tokens used across all orchestrations from their inner results
        total_tokens_used = 0
        total_reasoning_tokens_all = 0
        for result in all_results.values():
            inner_results = None
            if isinstance(result.get("results"), dict) and result["results"]:
                inner_results = next(iter(result["results"].values()))
            if isinstance(inner_results, dict):
                total_tokens_used += sum(
                    inner_results.get("token_usage", {}).get(agent, {}).get("used", 0)
                    for agent in ["netlogo_abstract_syntax_extractor", "behavior_extractor", "lucim_environment_synthesizer", "scenario_writer", 
                                 "plantuml_writer", "plantuml_lucim_auditor", "plantuml_lucim_corrector", "plantuml_lucim_final_auditor"]
                )
                # Sum reasoning tokens across agents if present
                agent_keys = [
                    "ast", "semantics", "lucim_environment_synthesizer", "lucim_scenario_synthesizer",
                    "plantuml_writer", "plantuml_lucim_auditor", "plantuml_lucim_corrector", "plantuml_lucim_final_auditor"
                ]
                for key in agent_keys:
                    if key in inner_results and isinstance(inner_results.get(key), dict):
                        total_reasoning_tokens_all += inner_results[key].get("reasoning_tokens", 0)
        
        self.logger.info(f"\n📊 OVERALL STATISTICS:")
        self.logger.info(f"   Total Orchestrations: {total_orchestrations}")
        self.logger.info(f"   Total Execution Time: {FormatUtils.format_duration(total_execution_time)}")
        self.logger.info(f"   Total Tokens Used: {total_tokens_used:,}")
        self.logger.info(f"   Total Reasoning Tokens: {total_reasoning_tokens_all:,}")
        self.logger.info(f"   Average Time per Orchestration: {FormatUtils.format_duration(total_execution_time/total_orchestrations)}")
        self.logger.info(f"   Average Tokens per Orchestration: {total_tokens_used/total_orchestrations:,.0f}")
        # New: Average input/output/reasoning tokens per orchestration
        self.logger.info(f"   Average Input Tokens per Orchestration: {total_input_tokens_all/total_orchestrations:,.0f}")
        self.logger.info(f"   Average Output Tokens per Orchestration: {total_output_tokens_all/total_orchestrations:,.0f}")
        self.logger.info(f"   Average Reasoning Tokens per Orchestration: {total_reasoning_tokens_all/total_orchestrations:,.0f}")
        
        self.logger.info(f"{'='*100}")
    
    def load_existing_results(self, base_name: str, model: str, step: int) -> Dict[str, Any]:
        """
        Load existing results from a specific step.
        
        Args:
            base_name: Base name of the model
            model: Model name
            step: Step number to load
            
        Returns:
            Dictionary containing the loaded results or None if not found
        """
        import json
        import glob
        from utils_path import get_run_base_dir
        
        # 1) Try new per-run/per-combination layout first
        # Determine reasoning/text verbosity from agent configs (same combo used across steps)
        tv = None
        reff = None
        try:
            if isinstance(self.agent_configs, dict) and "netlogo_abstract_syntax_extractor" in self.agent_configs:
                tv = self.agent_configs["netlogo_abstract_syntax_extractor"].get("text_verbosity")
                reff = self.agent_configs["netlogo_abstract_syntax_extractor"].get("reasoning_effort")
        except Exception:
            pass
        try:
            run_dir = get_run_base_dir(self.timestamp, base_name, model, reff or "medium", tv or "medium")
            step_to_agent = {
                1: "netlogo_abstract_syntax_extractor",
                2: "behavior_extractor",
                3: "lucim_environment_synthesizer",
                4: "lucim_scenario_synthesizer",
                5: "plantuml_writer",
                6: "plantuml_lucim_auditor",
                7: "plantuml_lucim_corrector",
                8: "plantuml_lucim_final_auditor"
            }
            agent_name = step_to_agent.get(step)
            if agent_name:
                agent_dir = run_dir / f"{int(step):02d}-{agent_name}"
                json_path = agent_dir / "output-response.json"
                if json_path.exists():
                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            result = json.load(f)
                            self.logger.info(f"Loaded existing results for step {step} from {json_path.name}")
                            # Update token usage tracking from loaded results
                            if result and isinstance(result, dict) and agent_name in self.token_usage:
                                self.token_usage[agent_name]["used"] = result.get("tokens_used", 0)
                                result["input_tokens"] = result.get("input_tokens", 0)
                                result["output_tokens"] = result.get("output_tokens", 0)
                                result["reasoning_tokens"] = result.get("reasoning_tokens", 0)
                                if self.detailed_timing[agent_name]["duration"] == 0:
                                    self.execution_times.setdefault(agent_name, 0)
                            return result
                    except Exception as e:
                        self.logger.warning(f"Warning: Could not load results from new layout for step {step}: {e}")
        except Exception:
            # If any issue computing run_dir, fall back to legacy search
            pass
        
        # No legacy fallback: enforce new layout only
        return None
        
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
                self.logger.info(f"Loaded existing results for step {step} from {pathlib.Path(latest_file).name}")
                
                # Update token usage tracking from loaded results
                if result and isinstance(result, dict):
                    tokens_used = result.get("tokens_used", 0)
                    input_tokens = result.get("input_tokens", 0)
                    output_tokens = result.get("output_tokens", 0)
                    reasoning_tokens = result.get("reasoning_tokens", 0)
                    
                    # Map step number to agent name
                    step_to_agent = {
                        1: "netlogo_abstract_syntax_extractor",
                        2: "behavior_extractor", 
                        3: "lucim_environment_synthesizer",
                        4: "lucim_scenario_synthesizer",
                        5: "plantuml_writer",
                        6: "plantuml_lucim_auditor",
                        7: "plantuml_lucim_corrector",
                        8: "plantuml_lucim_final_auditor"
                    }
                    
                    agent_name = step_to_agent.get(step)
                    if agent_name and agent_name in self.token_usage:
                        self.token_usage[agent_name]["used"] = tokens_used
                        # Store input/output tokens in the result for later use
                        result["input_tokens"] = input_tokens
                        result["output_tokens"] = output_tokens
                        result["reasoning_tokens"] = reasoning_tokens
                        
                        # Do not overwrite actual timing captured during the current run.
                        # If no timing exists yet (default 0), keep it; otherwise preserve real durations.
                        if self.detailed_timing[agent_name]["duration"] == 0:
                            self.execution_times.setdefault(agent_name, 0)
                
                # The response files contain the data directly in fields like 'messir_concepts', 'ast', etc.
                # We need to return them in the expected format for the orchestrator
                return result
        except Exception as e:
            self.logger.warning(f"Warning: Could not load existing results for step {step}: {e}")
            return None
    
    def _process_with_netlogo_abstract_syntax_extractor_agent(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single NetLogo file using the Syntax Parser agent.
        
        Args:
            file_info: Dictionary containing file information
            
        Returns:
            Dictionary containing the Syntax Parser processing results
        """
        code_file = file_info["code_file"]
        base_name = file_info["base_name"]
        
        self.logger.info(f"Processing {base_name} with Syntax Parser agent...")
        
        # Read the NetLogo code
        try:
            code_content = code_file.read_text(encoding="utf-8")
        except Exception as e:
            return {
                "agent_type": "netlogo_abstract_syntax_extractor",
                "reasoning_summary": f"Error reading code file: {e}",
                "data": None,
                "errors": [f"File reading error: {e}"]
            }
        
        # Use the AST agent to parse the code
        # Prepare per-run/per-combination directory and step output dir before invoking agent
        step_str = f"{int(self.step_counter):02d}"
        agent_id = "netlogo_abstract_syntax_extractor"
        tv = None
        if isinstance(self.agent_configs, dict) and "netlogo_abstract_syntax_extractor" in self.agent_configs:
            tv = self.agent_configs["netlogo_abstract_syntax_extractor"].get("text_verbosity")
        reff = None
        if isinstance(self.agent_configs, dict) and "netlogo_abstract_syntax_extractor" in self.agent_configs:
            reff = self.agent_configs["netlogo_abstract_syntax_extractor"].get("reasoning_effort")
        run_dir = get_run_base_dir(self.timestamp, base_name, self.model, reff or "medium", tv or "medium")
        agent_output_dir = run_dir / f"{step_str}-{agent_id}"
        agent_output_dir.mkdir(parents=True, exist_ok=True)
        result = self.netlogo_abstract_syntax_extractor_agent.parse_netlogo_code(
            code_content,
            f"{base_name}-netlogo-code.md",
            output_dir=agent_output_dir
        )
        
        # Add agent type identifier
        result["agent_type"] = "netlogo_abstract_syntax_extractor"
        
        # Save results using the AST agent's save method
        self.netlogo_abstract_syntax_extractor_agent.save_results(result, base_name, self.model, self.step_counter, output_dir=agent_output_dir)
        self.step_counter += 1
        
        return result
    
    def _process_with_behavior_extractor_agent(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single NetLogo file using the Semantics Parser agent.
        
        Args:
            file_info: Dictionary containing file information
            
        Returns:
            Dictionary containing the Semantics Parser processing results
        """
        code_file = file_info["code_file"]
        interface_images = file_info["interface_images"]
        base_name = file_info["base_name"]
        
        self.logger.info(f"Processing {base_name} with Semantics Parser agent...")
        
        # Use the Semantics agent with Stage 2 inputs only (no AST, no raw code)
        result = self.behavior_extractor_agent.parse_from_ilsem_and_ui(
            interface_images,
            base_name
        )
        
        # Add agent type identifier
        result["agent_type"] = "behavior_extractor"
        
        # Save results using the Semantics Parser agent's save method
        step_str = f"{int(self.step_counter):02d}"
        agent_id = "behavior_extractor"
        # New per-run/per-combination directory using centralized path builder
        tv = None
        if isinstance(self.agent_configs, dict) and "netlogo_abstract_syntax_extractor" in self.agent_configs:
            tv = self.agent_configs["netlogo_abstract_syntax_extractor"].get("text_verbosity")
        reff = None
        if isinstance(self.agent_configs, dict) and "netlogo_abstract_syntax_extractor" in self.agent_configs:
            reff = self.agent_configs["netlogo_abstract_syntax_extractor"].get("reasoning_effort")
        run_dir = get_run_base_dir(self.timestamp, base_name, self.model, reff or "medium", tv or "medium")
        agent_output_dir = run_dir / f"{step_str}-{agent_id}"
        agent_output_dir.mkdir(parents=True, exist_ok=True)
        # Validation must occur post-enrichment; save_results constructs the complete_response and validates internally
        self.behavior_extractor_agent.save_results(result, base_name, self.model, self.step_counter, output_dir=agent_output_dir)
        self.step_counter += 1
        
        return result
    
    async def process_netlogo_file_sequential(self, file_info: Dict[str, Any], start_step: int = 1) -> Dict[str, Any]:
        """
        Process a single NetLogo file using sequential agent calls.
        
        Args:
            file_info: Dictionary containing file information
            start_step: Step number to start from (1-7). Steps 1 to start_step-1 will be skipped.
            
        Returns:
            Dictionary containing all processing results
        """
        base_name = file_info["base_name"]
        # Prepare per-run/per-case directories
        # New structure: output/runs/<YYYY-MM-DD>/<HHMM>/<case>-<model>-reason-<effort>-verb-<verbosity>
        tv = None
        if isinstance(self.agent_configs, dict) and "netlogo_abstract_syntax_extractor" in self.agent_configs:
            tv = self.agent_configs["netlogo_abstract_syntax_extractor"].get("text_verbosity")
        reff = None
        if isinstance(self.agent_configs, dict) and "netlogo_abstract_syntax_extractor" in self.agent_configs:
            reff = self.agent_configs["netlogo_abstract_syntax_extractor"].get("reasoning_effort")
        run_dir = get_run_base_dir(self.timestamp, base_name, self.model, reff or "medium", tv or "medium")
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Start timing the total orchestration
        total_orchestration_start_time = time.time()
        
        self.logger.info(f"Starting sequential processing for {base_name}...")
        self.logger.info(f"Continuing single-pass after parallel stage: starting from step {start_step}")
        
        # Prepare input data
        code_file = file_info["code_file"]
        interface_images = file_info["interface_images"]
        
        # Read code for Step 1 (Syntax Parser) only; Stage 2 does not use raw code
        try:
            code_content = code_file.read_text(encoding="utf-8")
        except Exception as e:
            return {
                "error": f"Error reading code file: {e}",
                "results": {}
            }

        processed_results = {}
        
        # Load existing results for steps before start_step
        if start_step > 1:
            self.logger.info(f"Loading existing results for steps 1 to {start_step-1}...")
            
            # Load AST results (Step 1)
            if start_step > 1:
                ast_result = self.load_existing_results(base_name, self.model, 1)
                if ast_result:
                    processed_results["ast"] = ast_result
                    self.logger.info(f"✓ Loaded AST results from step 1")
                else:
                    self.logger.warning(f"⚠️  No existing AST results found for step 1")
            
            # Load Semantics results (Step 2)
            if start_step > 2:
                semantics_result = self.load_existing_results(base_name, self.model, 2)
                if semantics_result:
                    processed_results["semantics"] = semantics_result
                    self.logger.info(f"✓ Loaded Semantics results from step 2")
                else:
                    self.logger.warning(f"⚠️  No existing Semantics results found for step 2")
            
            # Load Messir Mapper results (Step 3)
            if start_step > 3:
                lucim_environment_result = self.load_existing_results(base_name, self.model, 3)
                if lucim_environment_result:
                    processed_results["lucim_environment_synthesizer"] = lucim_environment_result
                    self.logger.info(f"✓ Loaded LUCIM Environment Synthesizer results from step 3")
                else:
                    self.logger.warning(f"⚠️  No existing Messir Mapper results found for step 3")
            
            # Load Scenario Writer results (Step 4)
            if start_step > 4:
                scenario_result = self.load_existing_results(base_name, self.model, 4)
                if scenario_result:
                    processed_results["lucim_scenario_synthesizer"] = scenario_result
                    self.logger.info(f"✓ Loaded LUCIM Scenario Synthesizer results from step 4")
                else:
                    self.logger.warning(f"⚠️  No existing LUCIM Scenario Synthesizer results found for step 4")
            
            # Load PlantUML Writer results (Step 5)
            if start_step > 5:
                plantuml_result = self.load_existing_results(base_name, self.model, 5)
                if plantuml_result:
                    processed_results["plantuml_writer"] = plantuml_result
                    self.logger.info(f"✓ Loaded PlantUML Writer results from step 5")
                else:
                    self.logger.warning(f"⚠️  No existing PlantUML Writer results found for step 5")
            
            # Load PlantUML Messir Auditor results (Step 6)
            if start_step > 6:
                audit_result = self.load_existing_results(base_name, self.model, 6)
                if audit_result:
                    processed_results["plantuml_lucim_auditor"] = audit_result
                    self.logger.info(f"✓ Loaded PlantUML Messir Auditor results from step 6")
                else:
                    self.logger.warning(f"⚠️  No existing PlantUML Messir Auditor results found for step 6")
            
            # Load PlantUML Messir Corrector results (Step 7)
            if start_step > 7:
                corrector_result = self.load_existing_results(base_name, self.model, 7)
                if corrector_result:
                    processed_results["plantuml_lucim_corrector"] = corrector_result
                    self.logger.info(f"✓ Loaded PlantUML Messir Corrector results from step 7")
                else:
                    self.logger.warning(f"⚠️  No existing PlantUML Messir Corrector results found for step 7")
            
            self.logger.info(f"Resume preparation completed. Starting execution from step {start_step}")
        
        # Step 1: Syntax Parser Agent
        if start_step <= 1:
            self.logger.info(f"Step 1: Running NetLogo Abstract Syntax Extractor agent for {base_name}...")
            
            try:
                netlogo_abstract_syntax_extractor_result = self._execute_agent_with_tracking(
                    "netlogo_abstract_syntax_extractor",
                    self.netlogo_abstract_syntax_extractor_agent.parse_netlogo_code,
                    code_content, 
                    f"{base_name}-netlogo-code.md"
                )
                
                # Add agent type identifier
                netlogo_abstract_syntax_extractor_result["agent_type"] = "netlogo_abstract_syntax_extractor"
                
                # Save results using the NetLogo Abstract Syntax Extractor agent's save method
                agent_output_dir = run_dir / "01-netlogo_abstract_syntax_extractor"
                agent_output_dir.mkdir(parents=True, exist_ok=True)
                self.netlogo_abstract_syntax_extractor_agent.save_results(netlogo_abstract_syntax_extractor_result, base_name, self.model, "1", output_dir=agent_output_dir)  # Step 1 for NetLogo Abstract Syntax Extractor
                self.step_counter = 2  # Set step counter for next sequential agent
                
                processed_results["ast"] = netlogo_abstract_syntax_extractor_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "netlogo_abstract_syntax_extractor",
                    "reasoning_summary": f"Syntax Parser agent failed: {str(e)}",
                    "data": None,
                    "errors": [f"Syntax Parser agent error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 1: Syntax Parser agent failed for {base_name}: {str(e)}")
                processed_results["ast"] = error_result
        else:
            self.logger.info(f"Step 1: Skipping Syntax Parser agent for {base_name} (continue after parallel stage from step {start_step})")
        
        # Step 2: Semantics Parser Agent (independent of Step 1)
        if start_step <= 2:
            self.logger.info(f"Step 2: Running Semantics Parser agent for {base_name}...")
            
            try:
                behavior_extractor_result = self._execute_agent_with_tracking(
                    "behavior_extractor",
                    self.behavior_extractor_agent.parse_from_ilsem_and_ui,
                    interface_images,
                    base_name
                )
                
                # Add agent type identifier
                behavior_extractor_result["agent_type"] = "behavior_extractor"
                
                # Save results using the Semantics Parser agent's save method
                agent_output_dir = run_dir / "02-behavior_extractor"
                agent_output_dir.mkdir(parents=True, exist_ok=True)
                self.behavior_extractor_agent.save_results(behavior_extractor_result, base_name, self.model, "2", output_dir=agent_output_dir)  # Step 2 for Semantics Parser
                self.step_counter = 3  # Set step counter for next sequential agent
                
                processed_results["semantics"] = behavior_extractor_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "behavior_extractor",
                    "reasoning_summary": f"NetLogo Behavior Extractor agent failed: {str(e)}",
                    "data": None,
                    "errors": [f"NetLogo Behavior Extractor agent error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 2: NetLogo Behavior Extractor agent failed for {base_name}: {str(e)}")
                processed_results["semantics"] = error_result
        elif start_step > 2:
            self.logger.info(f"Step 2: Skipping NetLogo Behavior Extractor agent for {base_name} (continue after parallel stage from step {start_step})")
        
        # Step 3: Messir Mapper Agent (using AST and State Machine from previous steps)
        if start_step <= 3 and (processed_results.get("ast", {}).get("data") and 
            processed_results.get("semantics", {}).get("data")):
            
            self.logger.info(f"Step 3: Running Messir Mapper agent for {base_name}...")
            
            # iCrash files are no longer used
            icrash_contents = []
            
            # Load LUCIM DSL content
            messir_dsl_content = ""
            try:
                messir_dsl_content = LUCIM_RULES_FILE.read_text(encoding="utf-8")
                self.logger.info(f"Loaded LUCIM DSL content from {LUCIM_RULES_FILE}")
            except FileNotFoundError:
                self.logger.error(f"MANDATORY INPUT MISSING: LUCIM DSL file not found: {LUCIM_RULES_FILE}")
                messir_result = {
                    "reasoning_summary": "MISSING MANDATORY INPUT: LUCIM DSL file not found",
                    "data": None,
                    "errors": [f"MANDATORY INPUT MISSING: LUCIM DSL file not found: {LUCIM_RULES_FILE}"],
                    "tokens_used": 0,
                    "input_tokens": 0,
                    "output_tokens": 0
                }
                processed_results["lucim_environment_synthesizer"] = lucim_environment_result
                return processed_results
            
            try:
                lucim_environment_result = self._execute_agent_with_tracking(
                    "lucim_environment_synthesizer",
                    self.lucim_environment_synthesizer_agent.synthesize_lucim_environment,
                    processed_results["semantics"]["data"],
                    base_name,
                    processed_results["ast"]["data"],  # Step 01 AST data (MANDATORY)
                    messir_dsl_content,  # LUCIM DSL content (MANDATORY)
                    icrash_contents
                )
                
                # Add agent type identifier
                lucim_environment_result["agent_type"] = "lucim_environment_synthesizer"
                
                # Save results using the LUCIM Environment Synthesizer agent's save method
                agent_output_dir = run_dir / "03-lucim_environment_synthesizer"
                agent_output_dir.mkdir(parents=True, exist_ok=True)
                self.lucim_environment_synthesizer_agent.save_results(lucim_environment_result, base_name, self.model, "3", output_dir=agent_output_dir)  # Step 3 for LUCIM Environment Synthesizer
                self.step_counter = 4  # Set step counter for next sequential agent
                
                processed_results["lucim_environment_synthesizer"] = lucim_environment_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "lucim_environment_synthesizer",
                    "reasoning_summary": f"LUCIM Environment synthesis failed: {str(e)}",
                    "data": None,
                    "errors": [f"LUCIM Environment synthesis error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 3: LUCIM Environment Synthesizer agent failed for {base_name}: {str(e)}")
                processed_results["lucim_environment_synthesizer"] = error_result
        elif start_step > 3:
            self.logger.info(f"Step 3: Skipping LUCIM Environment Synthesizer agent for {base_name} (continue after parallel stage from step {start_step})")
        else:
            self.logger.info(f"Skipping Step 3: LUCIM Environment Synthesizer agent for {base_name} (AST or State Machine failed)")
        
        # Step 4: Scenario Writer Agent (using mandatory inputs: Step 02 state machine, Step 03 LUCIM environment, LUCIM DSL, iCrash refs)
        if start_step <= 4 and (processed_results.get("ast", {}).get("data") and 
            processed_results.get("lucim_environment_synthesizer", {}).get("data") and
            processed_results.get("semantics", {}).get("data")):
            
            self.logger.info(f"Step 4: Running Scenario Writer agent for {base_name}...")
            
            try:
                # Load mandatory inputs for Scenario Writer
                state_machine = processed_results["semantics"]["data"]
                lucim_environment = processed_results["lucim_environment_synthesizer"]["data"]
                
                # Load LUCIM DSL full definition
                messir_rules_content = ""
                try:
                    messir_rules_content = LUCIM_RULES_FILE.read_text(encoding="utf-8")
                except FileNotFoundError:
                    self.logger.error(f"ERROR: LUCIM DSL file not found: {LUCIM_RULES_FILE}")
                    raise SystemExit(f"ERROR: LUCIM DSL file not found: {LUCIM_RULES_FILE}")
                
                # iCrash files are no longer used
                icrash_refs_content = "iCrash reference files are no longer used"
                
                scenario_result = self._execute_agent_with_tracking(
                    "lucim_scenario_synthesizer",
                    self.lucim_scenario_synthesizer_agent.write_scenarios,
                    state_machine,
                    lucim_environment,
                    messir_rules_content,
                    icrash_refs_content,
                    base_name
                )
                
                # Add agent type identifier
                scenario_result["agent_type"] = "lucim_scenario_synthesizer"
                
                # Save results using the Scenario writer agent's save method
                agent_output_dir = run_dir / "04-lucim_scenario_synthesizer"
                agent_output_dir.mkdir(parents=True, exist_ok=True)
                self.lucim_scenario_synthesizer_agent.save_results(scenario_result, base_name, self.model, "4", output_dir=agent_output_dir)  # Step 4 for LUCIM Scenario Synthesizer
                self.step_counter = 5  # Set step counter for next sequential agent
                
                processed_results["lucim_scenario_synthesizer"] = scenario_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "lucim_scenario_synthesizer",
                    "reasoning_summary": f"Scenario writing failed: {str(e)}",
                    "data": None,
                    "errors": [f"Scenario writing error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 4: LUCIM Scenario Synthesizer agent failed for {base_name}: {str(e)}")
                processed_results["lucim_scenario_synthesizer"] = error_result
        elif start_step > 4:
            self.logger.info(f"Step 4: Skipping LUCIM Scenario Synthesizer agent for {base_name} (continue after parallel stage from step {start_step})")
        else:
            self.logger.info(f"Skipping Step 4: LUCIM Scenario Synthesizer agent for {base_name} (AST, MessirConcepts, or State Machine failed)")
        
        # Step 5: PlantUML Writer Agent (using scenarios from previous step)
        if start_step <= 5 and processed_results.get("lucim_scenario_synthesizer", {}).get("data"):
            
            self.logger.info(f"Step 5: Running PlantUML Writer agent for {base_name}...")
            
            try:
                plantuml_writer_result = self._execute_agent_with_tracking(
                    "plantuml_writer",
                    self.plantuml_writer_agent.generate_plantuml_diagrams,
                    processed_results["lucim_scenario_synthesizer"]["data"],
                    base_name
                )
                
                # Add agent type identifier
                plantuml_writer_result["agent_type"] = "plantuml_writer"
                
                # Save results using the PlantUML writer agent's save method
                agent_output_dir = run_dir / "05-plantuml_writer"
                agent_output_dir.mkdir(parents=True, exist_ok=True)
                self.plantuml_writer_agent.save_results(plantuml_writer_result, base_name, self.model, "5", output_dir=agent_output_dir)  # Step 5 for PlantUML Writer
                self.step_counter = 6  # Set step counter for next sequential agent
                
                processed_results["plantuml_writer"] = plantuml_writer_result

                # If a standalone .puml file was written, log its path for traceability
                try:
                    puml_path = plantuml_writer_result.get("puml_file")
                    if puml_path:
                        self.logger.info(f"Step 5: PlantUML .puml saved: {puml_path}")
                except Exception:
                    # Non-fatal: continue even if logging fails
                    pass
                
            except Exception as e:
                error_result = {
                    "agent_type": "plantuml_writer",
                    "reasoning_summary": f"PlantUML writing failed: {str(e)}",
                    "data": None,
                    "errors": [f"PlantUML writing error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 5: PlantUML Writer agent failed for {base_name}: {str(e)}")
                processed_results["plantuml_writer"] = error_result
        elif start_step > 5:
            self.logger.info(f"Step 5: Skipping PlantUML Writer agent for {base_name} (continue after parallel stage from step {start_step})")
        else:
            self.logger.info(f"Skipping Step 5: PlantUML Writer agent for {base_name} (Scenarios failed)")
        
        # Step 6: PlantUML Messir Auditor Agent (using PlantUML diagrams from previous step)
        if start_step <= 6 and processed_results.get("plantuml_writer", {}).get("data"):
            
            self.logger.info(f"Step 6: Running PlantUML Messir Auditor agent for {base_name}...")
            
            try:
                # Get scenarios data for context
                scenarios_data = processed_results.get("lucim_scenario_synthesizer", {}).get("data", {})
                
                # Load LUCIM DSL content (MANDATORY)
                messir_dsl_content = ""
                try:
                    messir_dsl_content = LUCIM_RULES_FILE.read_text(encoding="utf-8")
                    self.logger.info(f"Loaded LUCIM DSL content for PlantUML Auditor")
                except FileNotFoundError:
                    self.logger.error(f"MANDATORY INPUT MISSING: LUCIM DSL file not found: {LUCIM_RULES_FILE}")
                    plantuml_lucim_auditor_result = {
                        "reasoning_summary": "MISSING MANDATORY INPUT: LUCIM DSL file not found",
                        "data": None,
                        "errors": [f"MANDATORY INPUT MISSING: LUCIM DSL file not found: {LUCIM_RULES_FILE}"],
                        "tokens_used": 0,
                        "input_tokens": 0,
                        "output_tokens": 0
                    }
                    processed_results["plantuml_lucim_auditor"] = plantuml_lucim_auditor_result
                    return processed_results
                
                # Get PlantUML file path (MANDATORY)
                plantuml_file_path = processed_results["plantuml_writer"].get("puml_file", "")
                if not plantuml_file_path:
                    self.logger.error(f"MANDATORY INPUT MISSING: .puml file path not found in PlantUML Writer results")
                    plantuml_lucim_auditor_result = {
                        "reasoning_summary": "MISSING MANDATORY INPUT: .puml file path not found",
                        "data": None,
                        "errors": [f"MANDATORY INPUT MISSING: .puml file path not found in PlantUML Writer results"],
                        "tokens_used": 0,
                        "input_tokens": 0,
                        "output_tokens": 0
                    }
                    processed_results["plantuml_lucim_auditor"] = plantuml_lucim_auditor_result
                    return processed_results
                
                plantuml_lucim_auditor_result = self._execute_agent_with_tracking(
                    "plantuml_lucim_auditor",
                    self.plantuml_lucim_auditor_agent.audit_plantuml_diagrams,
                    plantuml_file_path,
                    str(LUCIM_RULES_FILE),
                    base_name
                )
                
                # Add agent type identifier
                plantuml_lucim_auditor_result["agent_type"] = "plantuml_lucim_auditor"
                
                # Save results using the PlantUML Messir auditor agent's save method
                agent_output_dir = run_dir / "06-plantuml_lucim_auditor"
                agent_output_dir.mkdir(parents=True, exist_ok=True)
                self.plantuml_lucim_auditor_agent.save_results(plantuml_lucim_auditor_result, base_name, self.model, "6", output_dir=agent_output_dir)  # Step 6 for PlantUML Messir Auditor
                self.step_counter = 7  # Set step counter for next sequential agent
                
                processed_results["plantuml_lucim_auditor"] = plantuml_lucim_auditor_result
                
                # Early exit: if compliant after Step 6, end flow gracefully (skip steps 7 and 8)
                try:
                    audit_data = plantuml_lucim_auditor_result.get("data", {}) if isinstance(plantuml_lucim_auditor_result, dict) else {}
                    if audit_data and audit_data.get("verdict") == "compliant":
                        self.logger.info("Step 6 verdict is compliant. Ending flow gracefully. Skipping steps 7 and 8.")
                        # Calculate total orchestration time
                        total_orchestration_time = time.time() - total_orchestration_start_time
                        self.execution_times["total_orchestration"] = total_orchestration_time
                        self.logger.info(f"Total orchestration time: {FormatUtils.format_duration(total_orchestration_time)}")
                        # Generate summary and finalize
                        self._generate_detailed_summary(base_name, processed_results)
                        processed_results["execution_times"] = self.execution_times.copy()
                        processed_results["token_usage"] = self.token_usage.copy()
                        processed_results["detailed_timing"] = self.detailed_timing.copy()
                        return processed_results
                except Exception as _e:
                    # Non-fatal: continue normal flow if early-exit bookkeeping fails
                    self.logger.warning(f"Early-exit check failed softly: {_e}")
            except Exception as e:
                error_result = {
                    "agent_type": "plantuml_lucim_auditor",
                    "reasoning_summary": f"PlantUML Messir auditing failed: {str(e)}",
                    "data": None,
                    "errors": [f"PlantUML Messir auditing error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 6: PlantUML Messir Auditor agent failed for {base_name}: {str(e)}")
                processed_results["plantuml_lucim_auditor"] = error_result
        elif start_step > 6:
            self.logger.info(f"Step 6: Skipping PlantUML Messir Auditor agent for {base_name} (continue after parallel stage from step {start_step})")
        else:
            self.logger.info(f"Skipping Step 6: PlantUML Messir Auditor agent for {base_name} (PlantUML diagrams failed)")
        
        # Note: Scenario Writer is already executed in the sequential processing (Step 4)
        # No need to duplicate it here
        
        # Note: PlantUML Writer is already executed in the sequential processing (Step 5)
        # No need to duplicate it here
        
        # Note: PlantUML Messir Auditor is already executed in the sequential processing (Step 6)
        # No need to duplicate it here
        
        # Step 7: PlantUML Messir Corrector Agent (only if Step 6 succeeded)
        if start_step <= 7:
            # Check if Step 6 (PlantUML Messir Auditor) succeeded and provided expected input
            plantuml_data = processed_results.get("plantuml_writer", {}).get("data")
            audit_data = processed_results.get("plantuml_lucim_auditor", {}).get("data")
            # Check for errors in both top-level errors and data.errors fields
            audit_top_level_errors = processed_results.get("plantuml_lucim_auditor", {}).get("errors", [])
            audit_data_errors = audit_data.get("errors", []) if audit_data else []
            audit_has_errors = bool(audit_top_level_errors) or bool(audit_data_errors)
            
            # Extract non-compliant rules from audit data
            non_compliant_rules = audit_data.get("non-compliant-rules", []) if audit_data else []
            
            # Run corrector if we have non-compliant rules OR syntax errors to fix
            has_issues_to_fix = bool(non_compliant_rules) or bool(audit_data_errors)
            if plantuml_data and audit_data and has_issues_to_fix:
                self.logger.info(f"Step 7: Running PlantUML Messir Corrector agent for {base_name} (found {len(non_compliant_rules)} non-compliant rules, {len(audit_data_errors)} syntax errors)...")
                
                try:
                    # Load LUCIM DSL content (MANDATORY)
                    messir_dsl_content = ""
                    try:
                        messir_dsl_content = LUCIM_RULES_FILE.read_text(encoding="utf-8")
                        self.logger.info(f"Loaded LUCIM DSL content for PlantUML Corrector")
                    except FileNotFoundError:
                        self.logger.error(f"MANDATORY INPUT MISSING: LUCIM DSL file not found: {LUCIM_RULES_FILE}")
                        plantuml_lucim_corrector_result = {
                            "reasoning_summary": "MISSING MANDATORY INPUT: LUCIM DSL file not found",
                            "data": None,
                            "errors": [f"MANDATORY INPUT MISSING: LUCIM DSL file not found: {LUCIM_RULES_FILE}"],
                            "tokens_used": 0,
                            "input_tokens": 0,
                            "output_tokens": 0
                        }
                        processed_results["plantuml_lucim_corrector"] = plantuml_lucim_corrector_result
                        return processed_results
                    
                    plantuml_lucim_corrector_result = self._execute_agent_with_tracking(
                        "plantuml_lucim_corrector",
                        self.plantuml_lucim_corrector_agent.correct_plantuml_diagrams,
                        plantuml_data,
                        non_compliant_rules,
                        messir_dsl_content,
                        base_name
                    )
                    
                    # Add agent type identifier
                    plantuml_lucim_corrector_result["agent_type"] = "plantuml_lucim_corrector"
                    
                    # Save results using the PlantUML Messir corrector agent's save method
                    agent_output_dir = run_dir / "07-plantuml_lucim_corrector"
                    agent_output_dir.mkdir(parents=True, exist_ok=True)
                    self.plantuml_lucim_corrector_agent.save_results(plantuml_lucim_corrector_result, base_name, self.model, "7", output_dir=agent_output_dir)  # Step 7 for PlantUML Messir Corrector
                    self.step_counter = 8  # Set step counter for next sequential agent
                    
                    processed_results["plantuml_lucim_corrector"] = plantuml_lucim_corrector_result
                    plantuml_lucim_corrector_executed = True
                    plantuml_lucim_corrector_success = True
                    
                except Exception as e:
                    error_result = {
                        "agent_type": "plantuml_lucim_corrector",
                        "reasoning_summary": f"PlantUML Messir correction failed: {str(e)}",
                        "data": None,
                        "errors": [f"PlantUML Messir correction error: {str(e)}"]
                    }
                    self.logger.error(f"✗ Step 7: PlantUML Messir Corrector agent failed for {base_name}: {str(e)}")
                    processed_results["plantuml_lucim_corrector"] = error_result
                    plantuml_lucim_corrector_executed = True
                    plantuml_lucim_corrector_success = False
                    
            elif plantuml_data and audit_data and not has_issues_to_fix:
                # Skip corrector if there are no issues to fix (no non-compliant rules and no syntax errors)
                self.logger.info(f"Step 7: Skipping PlantUML Messir Corrector agent for {base_name} (no issues to fix)")
                processed_results["plantuml_lucim_corrector"] = {
                    "agent_type": "plantuml_lucim_corrector",
                    "reasoning_summary": "Corrector skipped - no issues to fix",
                    "data": plantuml_data,  # Pass through original data
                    "errors": [],
                    "skipped": True
                }
                plantuml_lucim_corrector_executed = False
                plantuml_lucim_corrector_success = True
                
            else:
                # Step 6 failed or missing prerequisites
                missing_prereq = []
                if not plantuml_data:
                    missing_prereq.append("PlantUML diagrams")
                if not audit_data:
                    missing_prereq.append("audit results")
                if audit_has_errors and not non_compliant_rules:
                    missing_prereq.append("audit completed successfully or found non-compliant rules to fix")
                
                error_result = {
                    "agent_type": "plantuml_lucim_corrector",
                    "reasoning_summary": f"Corrector skipped - Step 6 (auditor) failed or missing prerequisites: {', '.join(missing_prereq)}",
                    "data": None,
                    "errors": [f"Missing prerequisites: {', '.join(missing_prereq)}"]
                }
                self.logger.info(f"Step 7: Skipping PlantUML Messir Corrector agent for {base_name} (Step 6 failed or missing prerequisites)")
                processed_results["plantuml_lucim_corrector"] = error_result
                plantuml_lucim_corrector_executed = False
                plantuml_lucim_corrector_success = False
        else:
            self.logger.info(f"Step 7: Skipping PlantUML Messir Corrector agent for {base_name} (continue after parallel stage from step {start_step})")
            # Add a placeholder entry to indicate the corrector was skipped due to resume
            processed_results["plantuml_lucim_corrector"] = {
                "agent_type": "plantuml_lucim_corrector",
                "reasoning_summary": f"Corrector skipped - continue after parallel stage from step {start_step}",
                "data": None,
                "errors": [],
                "skipped": True
            }
            plantuml_lucim_corrector_executed = False
            plantuml_lucim_corrector_success = True
        
        # Step 8: Final PlantUML Messir Auditor (always run)
        if start_step <= 8:
            self.logger.info(f"Step 8: Running PlantUML Messir Final Auditor agent for {base_name}...")
            
            try:
                # Determine what to audit based on corrector status
                corrector_has_data = processed_results.get("plantuml_lucim_corrector", {}).get("data") is not None
                corrector_has_errors = bool(processed_results.get("plantuml_lucim_corrector", {}).get("errors", []))
                
                if corrector_has_data and not corrector_has_errors:
                    # Audit the corrected PlantUML diagram from the corrector
                    plantuml_data_to_audit = processed_results["plantuml_lucim_corrector"]["data"]
                    self.logger.info(f"Step 8: Auditing corrected PlantUML diagrams")
                else:
                    # Audit the original PlantUML diagram (corrector failed, was skipped, or has errors)
                    plantuml_data_to_audit = processed_results.get("plantuml_writer", {}).get("data")
                    if plantuml_data_to_audit:
                        if corrector_has_errors:
                            self.logger.info(f"Step 8: Auditing original PlantUML diagrams (corrector failed)")
                        else:
                            self.logger.info(f"Step 8: Auditing original PlantUML diagrams (corrector was skipped)")
                    else:
                        # No PlantUML data available
                        raise Exception("No PlantUML data available for final audit")
                
                # Get scenarios data for context
                scenarios_data = processed_results.get("lucim_scenario_synthesizer", {}).get("data", {})
                
                # Determine the .puml file path for the corrected diagrams
                puml_file_path = ""
                if corrector_has_data and not corrector_has_errors:
                    # Use corrected .puml file from Step 7
                    corrector_output_dir = run_dir / "07-plantuml_lucim_corrector"
                    puml_files = list(corrector_output_dir.glob("*.puml"))
                    if puml_files:
                        puml_file_path = str(puml_files[0])
                        self.logger.info(f"Step 8: Using corrected .puml file: {puml_file_path}")
                    else:
                        self.logger.warning(f"Step 8: No .puml file found in corrector output, using data only")
                else:
                    # Use original .puml file from Step 5
                    plantuml_writer_output_dir = run_dir / "05-plantuml_writer"
                    puml_files = list(plantuml_writer_output_dir.glob("*.puml"))
                    if puml_files:
                        puml_file_path = str(puml_files[0])
                        self.logger.info(f"Step 8: Using original .puml file: {puml_file_path}")
                    else:
                        self.logger.warning(f"Step 8: No .puml file found in writer output, using data only")
                
                # LUCIM DSL file path (mandatory)
                mucim_dsl_file_path = str(LUCIM_RULES_FILE)
                self.logger.info(f"Step 8: Using LUCIM DSL file: {mucim_dsl_file_path}")
                
                # Enforce mandatory inputs for final audit: require existing .puml and LUCIM DSL
                from pathlib import Path as _Path
                missing_reasons = []
                if not puml_file_path:
                    missing_reasons.append(".puml file path is empty")
                elif not _Path(puml_file_path).exists():
                    missing_reasons.append(f".puml file does not exist: {puml_file_path}")
                if not _Path(mucim_dsl_file_path).exists():
                    missing_reasons.append(f"LUCIM DSL file not found: {mucim_dsl_file_path}")

                plantuml_lucim_final_auditor_result = None
                if missing_reasons:
                    reason = "; ".join(missing_reasons)
                    plantuml_lucim_final_auditor_result = {
                        "reasoning_summary": f"MISSING MANDATORY INPUT: {reason}",
                        "data": None,
                        "errors": [f"MISSING MANDATORY INPUT: {reason}"],
                        "tokens_used": 0,
                        "input_tokens": 0,
                        "output_tokens": 0
                    }
                    self.logger.error(f"MANDATORY INPUTS MISSING for Step 8: {reason}")
                else:
                    # Use the strict auditor API: (puml_file_path, mucim_dsl_file_path, base_name)
                    plantuml_lucim_final_auditor_result = self._execute_agent_with_tracking(
                        "plantuml_lucim_final_auditor",
                        self.plantuml_lucim_final_auditor_agent.audit_plantuml_diagrams,
                        puml_file_path,
                        mucim_dsl_file_path,
                        base_name
                    )
                
                # Add agent type identifier
                plantuml_lucim_final_auditor_result["agent_type"] = "plantuml_lucim_final_auditor"
                
                # Save results using the PlantUML Messir auditor agent's save method
                agent_output_dir = run_dir / "08-plantuml_lucim_final_auditor"
                agent_output_dir.mkdir(parents=True, exist_ok=True)
                self.plantuml_lucim_final_auditor_agent.save_results(plantuml_lucim_final_auditor_result, base_name, self.model, "8", output_dir=agent_output_dir)  # Step 8 for Final Auditor
                self.step_counter = 9  # Set step counter for next sequential agent
                
                processed_results["plantuml_lucim_final_auditor"] = plantuml_lucim_final_auditor_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "plantuml_lucim_final_auditor",
                    "reasoning_summary": f"PlantUML Messir final audit failed: {str(e)}",
                    "data": None,
                    "errors": [f"PlantUML Messir final audit error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 8: PlantUML Messir Final Auditor agent failed for {base_name}: {str(e)}")
                processed_results["plantuml_lucim_final_auditor"] = error_result
        else:
            self.logger.info(f"Step 8: Skipping PlantUML Messir Final Auditor agent for {base_name} (continue after parallel stage from step {start_step})")
            # Add a placeholder entry to indicate the final auditor was skipped due to resume
            processed_results["plantuml_lucim_final_auditor"] = {
                "agent_type": "plantuml_lucim_final_auditor",
                "reasoning_summary": f"Final auditor skipped - continue after parallel stage from step {start_step}",
                "data": None,
                "errors": [],
                "skipped": True
            }
        
        # Calculate total orchestration time
        total_orchestration_time = time.time() - total_orchestration_start_time
        self.execution_times["total_orchestration"] = total_orchestration_time
        
        self.logger.info(f"Completed processing for {base_name}")
        self.logger.info(f"Total orchestration time: {FormatUtils.format_duration(total_orchestration_time)}")
        
        # Generate enhanced detailed summary with timing and token usage
        self._generate_detailed_summary(base_name, processed_results)
        
        # Add timing and token usage information to the results
        processed_results["execution_times"] = self.execution_times.copy()
        processed_results["token_usage"] = self.token_usage.copy()
        processed_results["detailed_timing"] = self.detailed_timing.copy()
        
        return processed_results

    async def process_netlogo_file_parallel_first_stage(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run Step 1 (syntax) and an independent semantics derivation in parallel.
        (No AST-based re-run; Stage 2 uses only IL-SEM + UI images.)
        Mirrors the OpenAI Cookbook fan-out/fan-in pattern via asyncio.gather.
        """
        base_name = file_info["base_name"]
        # New per-run/per-combination directory using centralized path builder
        tv = None
        if isinstance(self.agent_configs, dict) and "netlogo_abstract_syntax_extractor" in self.agent_configs:
            tv = self.agent_configs["netlogo_abstract_syntax_extractor"].get("text_verbosity")
        reff = None
        if isinstance(self.agent_configs, dict) and "netlogo_abstract_syntax_extractor" in self.agent_configs:
            reff = self.agent_configs["netlogo_abstract_syntax_extractor"].get("reasoning_effort")
        run_dir = get_run_base_dir(self.timestamp, base_name, self.model, reff or "medium", tv or "medium")
        run_dir.mkdir(parents=True, exist_ok=True)

        total_orchestration_start_time = time.time()
        self.logger.info(f"Starting parallel first stage for {base_name} (syntax + semantics)...")

        code_file = file_info["code_file"]
        try:
            code_content = code_file.read_text(encoding="utf-8")
        except Exception as e:
            return {"error": f"Error reading code file: {e}", "results": {}}

        async def run_syntax():
            # Offload blocking call to a worker thread so it does not block the event loop
            return await asyncio.to_thread(
                self._execute_agent_with_tracking,
                "netlogo_abstract_syntax_extractor",
                self.netlogo_abstract_syntax_extractor_agent.parse_netlogo_code,
                code_content,
                f"{base_name}-netlogo-code.md"
            )

        async def run_semantics_direct():
            # Offload blocking call to a worker thread so it does not block the event loop
            return await asyncio.to_thread(
                self._execute_agent_with_tracking,
                "behavior_extractor",
                self.behavior_extractor_agent.parse_from_ilsem_and_ui,
                file_info["interface_images"],
                base_name
            )

        # Fan-out: run both concurrently with an optional watchdog and heartbeat
        from utils_config_constants import HEARTBEAT_SECONDS
        import utils_config_constants as cfg
        async def heartbeat_task():
            try:
                while True:
                    await asyncio.sleep(HEARTBEAT_SECONDS)
                    self.logger.info(f"[heartbeat] Parallel first stage still running for {base_name}...")
            except asyncio.CancelledError:
                return

        hb = asyncio.create_task(heartbeat_task())
        try:
            syntax_coro = run_syntax()
            sem_coro = run_semantics_direct()
            syntax_task = asyncio.create_task(syntax_coro)
            sem_task = asyncio.create_task(sem_coro)
            # If orchestrator parallel timeout is configured (not None), wrap with wait_for
            orchestrator_timeout = getattr(cfg, "ORCHESTRATOR_PARALLEL_TIMEOUT", None)
            if orchestrator_timeout is not None:
                await asyncio.wait_for(
                    asyncio.gather(syntax_task, sem_task, return_exceptions=True),
                    timeout=orchestrator_timeout
                )
            else:
                # No watchdog timeout: wait indefinitely for both tasks
                await asyncio.gather(syntax_task, sem_task, return_exceptions=True)
            syntax_result = await syntax_task
            semantics_result_direct = await sem_task
        except asyncio.TimeoutError:
            self.logger.error(f"Parallel first stage timed out after {getattr(cfg, 'ORCHESTRATOR_PARALLEL_TIMEOUT', 'N/A')}s for {base_name}")
            # Cancel any still-running task
            for t in [locals().get('syntax_task'), locals().get('sem_task')]:
                try:
                    if t and not t.done():
                        t.cancel()
                except Exception:
                    pass
            syntax_result = syntax_result if 'syntax_result' in locals() else RuntimeError("netlogo_abstract_syntax_extractor timed out")
            semantics_result_direct = semantics_result_direct if 'semantics_result_direct' in locals() else RuntimeError("behavior_extractor (direct) timed out")
        finally:
            hb.cancel()

        processed_results: Dict[str, Any] = {}

        # Handle syntax result
        if isinstance(syntax_result, Exception):
            self.logger.error(f"Syntax Parser failed in parallel path: {syntax_result}")
            processed_results["ast"] = {
                "agent_type": "netlogo_abstract_syntax_extractor",
                "reasoning_summary": f"Syntax Parser agent failed: {syntax_result}",
                "data": None,
                "errors": [f"Syntax Parser agent error: {syntax_result}"]
            }
        else:
            syntax_result["agent_type"] = "netlogo_abstract_syntax_extractor"
            agent_output_dir = run_dir / "01-netlogo_abstract_syntax_extractor"
            agent_output_dir.mkdir(parents=True, exist_ok=True)
            self.netlogo_abstract_syntax_extractor_agent.save_results(syntax_result, base_name, self.model, "1", output_dir=agent_output_dir)
            self.step_counter = max(self.step_counter, 2)
            processed_results["ast"] = syntax_result

        # Handle semantics direct result
        if isinstance(semantics_result_direct, Exception):
            self.logger.error(f"Semantics Parser (direct) failed in parallel path: {semantics_result_direct}")
            processed_results["semantics"] = {
                "agent_type": "behavior_extractor",
                "reasoning_summary": f"Semantics Parser direct failed: {semantics_result_direct}",
                "data": None,
                "errors": [f"Semantics Parser direct error: {semantics_result_direct}"]
            }
        else:
            semantics_result = semantics_result_direct

            semantics_result["agent_type"] = "behavior_extractor"
            agent_output_dir = run_dir / "02-behavior_extractor"
            agent_output_dir.mkdir(parents=True, exist_ok=True)
            self.behavior_extractor_agent.save_results(semantics_result, base_name, self.model, "2", output_dir=agent_output_dir)
            self.step_counter = max(self.step_counter, 3)
            processed_results["semantics"] = semantics_result

        # Total timing
        total_orchestration_time = time.time() - total_orchestration_start_time
        self.execution_times["total_orchestration"] = total_orchestration_time
        self.logger.info(f"Parallel first stage completed in {FormatUtils.format_duration(total_orchestration_time)}")

        # Bookkeeping only (no intermediate detailed summary in single-pass mode)
        processed_results["execution_times"] = self.execution_times.copy()
        processed_results["token_usage"] = self.token_usage.copy()
        processed_results["detailed_timing"] = self.detailed_timing.copy()
        return processed_results
    
    async def run(self, base_name: str, start_step: int = 1) -> Dict[str, Any]:
        """
        Run the orchestrator for a given base name with sequential processing.
        
        Args:
            base_name: Base name of the NetLogo files to process
            start_step: Step number to start from (1-8). Steps 1 to start_step-1 will be skipped.
            
        Returns:
            Dictionary containing all processing results
        """
        # Set up logging for this orchestration run, including reasoning and text verbosity
        tv = None
        if isinstance(self.agent_configs, dict) and "netlogo_abstract_syntax_extractor" in self.agent_configs:
            tv = self.agent_configs["netlogo_abstract_syntax_extractor"].get("text_verbosity")
        reff = None
        rsum = None
        if isinstance(self.agent_configs, dict) and "netlogo_abstract_syntax_extractor" in self.agent_configs:
            reff = self.agent_configs["netlogo_abstract_syntax_extractor"].get("reasoning_effort")
            rsum = self.agent_configs["netlogo_abstract_syntax_extractor"].get("reasoning_summary")

        self.logger = setup_orchestration_logger(
            base_name,
            self.model,
            self.timestamp,
            reasoning_effort=reff or "medium",
            text_verbosity=tv or "medium",
        )
        # Also mirror stdout/stderr into the orchestrator log file
        attach_stdio_to_logger(self.logger)
        
        # Single parameter bundle line including text verbosity (only here)
        bundle_line = format_parameter_bundle(
            model=self.model,
            base_name=base_name,
            reasoning_effort=reff,
            reasoning_summary=rsum,
            text_verbosity=tv
        )
        self.logger.info(bundle_line)
        
        self.logger.info(f"Starting sequential processing for base name: {base_name}")
        self.logger.info(f"Starting from step {start_step}")
        
        # Find files matching the base name
        files = self.find_netlogo_files(base_name)
        
        if not files:
            return {
                "error": f"No files found for base name '{base_name}'",
                "results": {}
            }
        
        results = {}
        
        # Process each file with sequential or parallel-first-stage
        for file_info in files:
            base_name = file_info["base_name"]
            if start_step <= 2:
                result = await self.process_netlogo_file_parallel_first_stage(file_info)
                # After parallel first stage, continue sequentially from step 3
                if isinstance(result, dict):
                    # Merge continuation from step 3
                    cont = await self.process_netlogo_file_sequential(file_info, start_step=3)
                    # Merge maps conservatively; keep earlier entries from parallel stage
                    for k, v in cont.items():
                        if k not in result:
                            result[k] = v
            else:
                result = await self.process_netlogo_file_sequential(file_info, start_step)
            results[base_name] = result
            
                    # Print status
            netlogo_abstract_syntax_extractor_success = result.get("ast", {}).get("data") is not None
            behavior_extractor_success = result.get("semantics", {}).get("data") is not None
            lucim_environment_success = result.get("lucim_environment_synthesizer", {}).get("data") is not None
            scenario_success = result.get("lucim_scenario_synthesizer", {}).get("data") is not None
            plantuml_writer_success = result.get("plantuml_writer", {}).get("data") is not None
            plantuml_lucim_auditor_success = result.get("plantuml_lucim_auditor", {}).get("data") is not None
            plantuml_lucim_corrector_success = result.get("plantuml_lucim_corrector", {}).get("data") is not None
            plantuml_lucim_final_auditor_success = result.get("plantuml_lucim_final_auditor", {}).get("data") is not None
            
            # Check if PlantUML Messir Corrector was executed (only if diagrams were non-compliant)
            plantuml_lucim_corrector_executed = "plantuml_lucim_corrector" in result
            plantuml_lucim_final_auditor_executed = "plantuml_lucim_final_auditor" in result
            
            # Determine if agents were skipped (not present in result) vs failed (present but failed)
            # A step is skipped if it's not in the result at all, not if it failed
            semantics_skipped = "semantics" not in result
            lucim_environment_skipped = "lucim_environment_synthesizer" not in result
            scenario_skipped = "lucim_scenario_synthesizer" not in result
            plantuml_writer_skipped = "plantuml_writer" not in result
            plantuml_lucim_auditor_skipped = "plantuml_lucim_auditor" not in result
            
            self.logger.info(f"{base_name} results:")
            self.logger.info(f"  Step 1 - Syntax Parser: {'✓' if netlogo_abstract_syntax_extractor_success else '✗'}")
            self.logger.info(f"  Step 2 - NetLogo Behavior Extractor: {'✓' if behavior_extractor_success else '✗'}")
            self.logger.info(f"  Step 3 - LUCIM Environment Synthesizer: {'✓' if lucim_environment_success else '✗'}")
            self.logger.info(f"  Step 4 - Scenario Writer: {'✓' if scenario_success else '✗'}")
            self.logger.info(f"  Step 5 - PlantUML Writer: {'✓' if plantuml_writer_success else '✗'}")
            self.logger.info(f"  Step 6 - PlantUML Messir Auditor: {'✓' if plantuml_lucim_auditor_success else '✗'}")
            if plantuml_lucim_corrector_executed:
                self.logger.info(f"  Step 7 - PlantUML Messir Corrector: {'✓' if plantuml_lucim_corrector_success else '✗'}")
            if plantuml_lucim_final_auditor_executed:
                self.logger.info(f"  Step 8 - PlantUML Messir Final Auditor: {'✓' if plantuml_lucim_final_auditor_success else '✗'}")
            else:
                self.logger.info(f"  Step 7 - PlantUML Messir Corrector: SKIPPED (diagrams already compliant)")
            
            if not netlogo_abstract_syntax_extractor_success and result.get("ast", {}).get("errors"):
                self.logger.warning(f"    Step 1 - Syntax Parser errors: {len(result['ast']['errors'])} found")
            if not behavior_extractor_success and result.get("semantics", {}).get("errors"):
                self.logger.warning(f"    Step 2 - NetLogo Behavior Extractor errors: {len(result['semantics']['errors'])} found")
            if not lucim_environment_success and result.get("lucim_environment_synthesizer", {}).get("errors"):
                self.logger.warning(f"    Step 3 - LUCIM Environment Synthesizer errors: {len(result['lucim_environment_synthesizer']['errors'])} found")
            if not scenario_success and result.get("lucim_scenario_synthesizer", {}).get("errors"):
                self.logger.warning(f"    Step 4 - LUCIM scenario synthesis errors: {len(result['lucim_scenario_synthesizer']['errors'])} found")
            if not plantuml_writer_success and result.get("plantuml_writer", {}).get("errors"):
                self.logger.warning(f"    Step 5 - PlantUML writing errors: {len(result['plantuml_writer']['errors'])} found")
            if not plantuml_lucim_auditor_success and result.get("plantuml_lucim_auditor", {}).get("errors"):
                self.logger.warning(f"    Step 6 - PlantUML Messir auditing errors: {len(result['plantuml_lucim_auditor']['errors'])} found")
            
            if plantuml_lucim_corrector_executed and not plantuml_lucim_corrector_success and result.get("plantuml_lucim_corrector", {}).get("errors"):
                self.logger.warning(f"    Step 7 - PlantUML Messir correction errors: {len(result['plantuml_lucim_corrector']['errors'])} found")
        
        self.logger.info(f"Completed processing for {base_name}")
        
        # Print comprehensive orchestration summary
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"ORCHESTRATION SUMMARY FOR: {base_name}")
        self.logger.info(f"{'='*60}")
        
        # Count total agents (PlantUML Messir Corrector is conditional)
        total_agents = 6  # Syntax Parser, Semantics, Messir Mapper, Scenario Writer, PlantUML Writer, PlantUML Messir Auditor
        successful_agents = 0
        failed_agents = 0
        
        # Count successful and failed agents
        if netlogo_abstract_syntax_extractor_success: successful_agents += 1
        else: failed_agents += 1
        
        if behavior_extractor_success: successful_agents += 1
        else: failed_agents += 1
        
        if messir_success: successful_agents += 1
        else: failed_agents += 1
        
        if scenario_success: successful_agents += 1
        else: failed_agents += 1
        
        if plantuml_writer_success: successful_agents += 1
        else: failed_agents += 1
        
        if plantuml_lucim_auditor_success: successful_agents += 1
        else: failed_agents += 1
        
        # Add PlantUML Messir Corrector only if it was executed
        if plantuml_lucim_corrector_executed:
            total_agents += 1
            if plantuml_lucim_corrector_success: successful_agents += 1
            else: failed_agents += 1
        
        # Add PlantUML Messir Final Auditor only if it was executed
        if plantuml_lucim_final_auditor_executed:
            total_agents += 1
            if plantuml_lucim_final_auditor_success: successful_agents += 1
            else: failed_agents += 1
        
        self.logger.info(f"📊 OVERALL STATUS:")
        self.logger.info(f"   Total Agents: {total_agents}")
        self.logger.info(f"   Successful: {successful_agents} ✓")
        self.logger.info(f"   Failed: {failed_agents} ✗")
        self.logger.info(f"   Success Rate: {(successful_agents/total_agents)*100:.1f}%")
        
        print(f"\n⏱️  EXECUTION TIMING:")
        self.logger.info(f"   Total Orchestration Time: {FormatUtils.format_duration(self.execution_times['total_orchestration'])}")
        
        # Calculate and display individual agent times
        total_agent_time = 0
        agent_times = []
        
        if self.execution_times["netlogo_abstract_syntax_extractor"] > 0:
            agent_times.append(("Step 1 - Syntax Parser", self.execution_times["netlogo_abstract_syntax_extractor"]))
            total_agent_time += self.execution_times["netlogo_abstract_syntax_extractor"]
        
        if self.execution_times["behavior_extractor"] > 0:
            agent_times.append(("Step 2 - Semantics Parser", self.execution_times["behavior_extractor"]))
            total_agent_time += self.execution_times["behavior_extractor"]
        
        if self.execution_times["lucim_environment_synthesizer"] > 0:
            agent_times.append(("Step 3 - LUCIM Environment Synthesizer", self.execution_times["lucim_environment_synthesizer"]))
            total_agent_time += self.execution_times["lucim_environment_synthesizer"]
        
        if self.execution_times["lucim_scenario_synthesizer"] > 0:
            agent_times.append(("Step 4 - LUCIM Scenario Synthesizer", self.execution_times["lucim_scenario_synthesizer"]))
            total_agent_time += self.execution_times["lucim_scenario_synthesizer"]
        
        if self.execution_times["plantuml_writer"] > 0:
            agent_times.append(("Step 5 - PlantUML Writer", self.execution_times["plantuml_writer"]))
            total_agent_time += self.execution_times["plantuml_writer"]
        
        if self.execution_times["plantuml_lucim_auditor"] > 0:
            agent_times.append(("Step 6 - PlantUML Messir Auditor", self.execution_times["plantuml_lucim_auditor"]))
            total_agent_time += self.execution_times["plantuml_lucim_auditor"]
        
        if self.execution_times["plantuml_lucim_corrector"] > 0:
            agent_times.append(("Step 7 - PlantUML Messir Corrector", self.execution_times["plantuml_lucim_corrector"]))
            total_agent_time += self.execution_times["plantuml_lucim_corrector"]
        
        if self.execution_times["plantuml_lucim_final_auditor"] > 0:
            agent_times.append(("Step 8 - PlantUML Messir Final Auditor", self.execution_times["plantuml_lucim_final_auditor"]))
            total_agent_time += self.execution_times["plantuml_lucim_final_auditor"]
        
        # Sort agents by execution time (descending)
        agent_times.sort(key=lambda x: x[1], reverse=True)
        
        self.logger.info(f"   Total Agent Execution Time: {FormatUtils.format_duration(total_agent_time)}")
        self.logger.info(f"   Overhead Time: {FormatUtils.format_duration(self.execution_times['total_orchestration'] - total_agent_time)}")
        
        if agent_times:
            self.logger.info(f"   \n   📈 AGENT TIMING BREAKDOWN:")
            for agent_name, agent_time in agent_times:
                percentage = (agent_time / total_agent_time * 100) if total_agent_time > 0 else 0
                self.logger.info(f"      {agent_name}: {FormatUtils.format_duration(agent_time)} ({percentage:.1f}%)")
        
        print(f"\n🔍 DETAILED AGENT STATUS:")
        self.logger.info(f"   Step 1 - Syntax Parser Agent: {'✓ SUCCESS' if netlogo_abstract_syntax_extractor_success else '✗ FAILED'}")
        
        # Step 2 - Semantics Parser
        if semantics_skipped:
            self.logger.info(f"   Step 2 - Semantics Parser Agent: ⏭️  SKIPPED (Syntax Parser failed)")
        else:
            self.logger.info(f"   Step 2 - Semantics Parser Agent: {'✓ SUCCESS' if behavior_extractor_success else '✗ FAILED'}")
        
        # Step 3 - Messir Mapper
        if messir_skipped:
            self.logger.info(f"   Step 3 - Messir Mapper Agent: ⏭️  SKIPPED (AST or State Machine failed)")
        else:
            self.logger.info(f"   Step 3 - Messir Mapper Agent: {'✓ SUCCESS' if messir_success else '✗ FAILED'}")
        
        # Step 4 - Scenario Writer
        if scenario_skipped:
            self.logger.info(f"   Step 4 - Scenario Writer Agent: ⏭️  SKIPPED (AST, MessirConcepts, or State Machine failed)")
        else:
            self.logger.info(f"   Step 4 - Scenario Writer Agent: {'✓ SUCCESS' if scenario_success else '✗ FAILED'}")
        
        # Step 5 - PlantUML Writer
        if plantuml_writer_skipped:
            self.logger.info(f"   Step 5 - PlantUML Writer Agent: ⏭️  SKIPPED (Scenarios failed)")
        else:
            self.logger.info(f"   Step 5 - PlantUML Writer Agent: {'✓ SUCCESS' if plantuml_writer_success else '✗ FAILED'}")
        
        # Step 6 - PlantUML Messir Auditor
        if plantuml_lucim_auditor_skipped:
            self.logger.info(f"   Step 6 - PlantUML Messir Auditor Agent: ⏭️  SKIPPED (PlantUML diagrams failed)")
        else:
            self.logger.info(f"   Step 6 - PlantUML Messir Auditor Agent: {'✓ SUCCESS' if plantuml_lucim_auditor_success else '✗ FAILED'}")
        
        # Step 7 - PlantUML Messir Corrector
        if not plantuml_lucim_corrector_executed:
            self.logger.info(f"   Step 7 - PlantUML Messir Corrector Agent: ⏭️  SKIPPED (diagrams already compliant)")
        else:
            self.logger.info(f"   Step 7 - PlantUML Messir Corrector Agent: {'✓ SUCCESS' if plantuml_lucim_corrector_success else '✗ FAILED'}")
        
        # Step 8 - PlantUML Messir Final Auditor
        if not plantuml_lucim_final_auditor_executed:
            self.logger.info(f"   Step 8 - PlantUML Messir Final Auditor Agent: ⏭️  SKIPPED (corrector was skipped or not required)")
        else:
            self.logger.info(f"   Step 8 - PlantUML Messir Final Auditor Agent: {'✓ SUCCESS' if plantuml_lucim_final_auditor_success else '✗ FAILED'}")
        
        self.logger.info(f"\n📁 OUTPUT FILES GENERATED:")
        for result_key, result_data in result.items():
            if result_data and isinstance(result_data, dict):
                agent_type = result_data.get("agent_type", "unknown")
                if agent_type == "netlogo_abstract_syntax_extractor":
                    self.logger.info(f"   • Syntax Parser: {base_name}_{self.timestamp}_{self.model}_1a_netlogo_abstract_syntax_extractor_v1_*.md")
                elif agent_type == "behavior_extractor":
                    self.logger.info(f"   • Semantics Parser: {base_name}_{self.timestamp}_{self.model}_1b_behavior_extractor_v1_*.json/md")
                elif agent_type == "lucim_environment_synthesizer":
                    self.logger.info(f"   • LUCIM Environment Synthesizer: {base_name}_{self.timestamp}_{self.model}_3_lucim_environment_synthesizer_v1_*.json/md")
                elif agent_type == "lucim_scenario_synthesizer":
                    self.logger.info(f"   • Scenarios: {base_name}_{self.timestamp}_{self.model}_3_scenario_v1_*.md")
                elif agent_type == "plantuml_writer":
                    self.logger.info(f"   • PlantUML Diagrams: {base_name}_{self.timestamp}_{self.model}_4_plantuml_*.json/md/.puml")
                elif agent_type == "plantuml_lucim_auditor":
                    self.logger.info(f"   • PlantUML Messir Audit: {base_name}_{self.timestamp}_{self.model}_5_messir_audit_*.json/md/.puml")
                elif agent_type == "plantuml_lucim_corrector":
                    self.logger.info(f"   • PlantUML Messir Corrector: {base_name}_{self.timestamp}_{self.model}_7_messir_corrector_*.json/md/.puml")
                elif agent_type == "plantuml_lucim_final_auditor":
                    self.logger.info(f"   • PlantUML Messir Final Auditor: {base_name}_{self.timestamp}_{self.model}_8_messir_final_auditor_*.json/md/.puml")
                elif agent_type == "plantuml_lucim_auditor" and not plantuml_lucim_corrector_executed:
                    self.logger.info(f"   • PlantUML Messir Auditor (Compliant): {base_name}_{self.timestamp}_{self.model}_6_messir_audit_*.json/md/.puml")
        
        self.logger.info(f"\n🎯 PIPELINE COMPLETION:")
        if successful_agents == total_agents:
            self.logger.info(f"   🎉 FULL SUCCESS: All {total_agents} agents completed successfully!")
            self.logger.info(f"   📋 Final output includes Messir-compliant PlantUML sequence diagrams")
        elif successful_agents >= 6:  # At least core pipeline completed (all 6 agents)
            self.logger.info(f"   ⚠️  PARTIAL SUCCESS: {successful_agents}/{total_agents} agents completed")
            self.logger.info(f"   📋 Some outputs available, but pipeline incomplete")
        else:
            self.logger.info(f"   ❌ PIPELINE FAILED: Only {successful_agents}/{total_agents} agents completed")
            self.logger.info(f"   📋 Limited outputs available")
        
        # Compute canonical final compliance from auditor/corrector results (single source of truth)
        final_compliance = {
            "status": "UNKNOWN",  # VERIFIED | NON-COMPLIANT | UNKNOWN
            "source": "none",
            "details": {}
        }

        # Prefer Step 8 (final auditor) if available
        final_audit_data = result.get("plantuml_lucim_final_auditor", {}).get("data") if plantuml_lucim_final_auditor_success else None
        initial_audit_data = result.get("plantuml_lucim_auditor", {}).get("data") if plantuml_lucim_auditor_success else None

        if isinstance(final_audit_data, dict) and final_audit_data.get("verdict") in ("compliant", "non-compliant"):
            final_compliance["source"] = "final_auditor_step8"
            final_compliance["details"] = {"verdict": final_audit_data.get("verdict")}
            final_compliance["status"] = "VERIFIED" if final_audit_data.get("verdict") == "compliant" else "NON-COMPLIANT"
        elif isinstance(initial_audit_data, dict) and initial_audit_data.get("verdict") in ("compliant", "non-compliant"):
            # If no final auditor verdict, fallback to initial auditor
            final_compliance["source"] = "auditor_step6"
            final_compliance["details"] = {"verdict": initial_audit_data.get("verdict")}
            final_compliance["status"] = "VERIFIED" if initial_audit_data.get("verdict") == "compliant" else "NON-COMPLIANT"
        else:
            final_compliance["source"] = "unknown"

        # Log using the canonical field only
        self.logger.info(f"\n🔍 COMPLIANCE STATUS:")
        if final_compliance["status"] == "VERIFIED":
            self.logger.info(f"   ✅ FINAL COMPLIANCE: VERIFIED")
            self.logger.info(f"   🎯 Result: Final audit confirms Messir compliance")
        elif final_compliance["status"] == "NON-COMPLIANT":
            self.logger.info(f"   ❌ FINAL COMPLIANCE: NON-COMPLIANT")
            self.logger.info(f"   📊 Result: One or more LUCIM rules were violated")
        else:
            self.logger.info(f"   ❓ COMPLIANCE STATUS: UNKNOWN")
            self.logger.info(f"   ⚠️  Result: No authoritative compliance verdict available")
        
        self.logger.info(f"{'='*60}")
        
        return {
            "base_name": base_name,
            "files_processed": len(files),
            "total_agents": total_agents,
            "successful_agents": successful_agents,
            "failed_agents": failed_agents,
            "success_rate": (successful_agents/total_agents)*100 if total_agents > 0 else 0,
            "results": results,
            "final_compliance": final_compliance
        }

    def read_icrash_file_content(self, icrash_file: pathlib.Path) -> Dict[str, str]:
        """
        Read the content of an iCrash PDF file.
        
        Args:
            icrash_file: Path to the iCrash PDF file
            
        Returns:
            Dictionary containing filename, filepath, and content
        """
        try:
            # For now, we'll use a simple approach to extract text from PDF
            # In a production environment, you might want to use a proper PDF library like PyPDF2 or pdfplumber
            
            # Try to read the file as text first (in case it's not a real PDF)
            try:
                with open(icrash_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                return {
                    "filename": icrash_file.name,
                    "filepath": str(icrash_file),
                    "content": content
                }
            except UnicodeDecodeError:
                # If it's a real PDF, we'll use a fallback approach
                # For now, we'll create a reference based on the filename
                if "actors" in icrash_file.name.lower():
                    content = "iCrash Actors Reference: Contains definitions of system actors and their roles in the iCrash case study. Use this to understand actor naming conventions and responsibilities."
                elif "casestudy" in icrash_file.name.lower():
                    content = "iCrash Case Study: Contains the complete case study description with system requirements, actors, and event patterns. Use this as the primary reference for Messir UCI mapping."
                else:
                    content = f"iCrash Reference File: {icrash_file.name} - Contains relevant patterns and examples for Messir UCI mapping."
                
                return {
                    "filename": icrash_file.name,
                    "filepath": str(icrash_file),
                    "content": content
                }
                
        except Exception as e:
            self.logger.warning(f"Warning: Could not read icrash file {icrash_file}: {e}")
            return {
                "filename": icrash_file.name,
                "filepath": str(icrash_file),
                "content": f"Error reading file: {e}"
            }



async def main():
    """Main execution function."""
    
    # Validate OpenAI API key before any user interaction
    from utils_openai_client import validate_openai_key
    print("Validating OpenAI API key...")
    if not validate_openai_key():
        print("Exiting due to invalid OpenAI API key")
        return
    
    # Available AI models
    available_models = AVAILABLE_MODELS
    
    # Get available base names from supported patterns
    code_files = set()
    for pattern in ("*-netlogo-code.md", "*-code.md"):
        for f in INPUT_NETLOGO_DIR.glob(pattern):
            code_files.add(f)
    
    if not code_files:
        print(f"No NetLogo code files found in {INPUT_NETLOGO_DIR} (expected *-netlogo-code.md or *-code.md)")
        return
    
    base_names = []
    for i, code_file in enumerate(sorted(code_files), 1):
        stem = code_file.stem
        if stem.endswith("-netlogo-code"):
            base_name = stem.replace("-netlogo-code", "")
        elif stem.endswith("-code"):
            base_name = stem.replace("-code", "")
        else:
            # Fallback: keep original stem
            base_name = stem
        base_names.append(base_name)
    
    # Model selection
    print("NetLogo Orchestrator - AI Model Selection")
    print("="*50)
    print("Available AI Models:")
    print("0. All models")
    for i, model in enumerate(available_models, 1):
        print(f"{i}. {model}")
    
    print("\nEnter the number of the AI model to use")
    print(f" - Press Enter once to immediately start the default run: {DEFAULT_MODEL or 'default-model'}, 3d-solids, low effort (parallel steps 1+2)")
    print(" - Or type a number (or 'q' to quit):")
    
    while True:
        try:
            model_input = input("Model > ").strip()
            
            if model_input.lower() == 'q':
                print("Exiting...")
                return
            
            # Short-circuit: single Enter triggers immediate default run
            if model_input == "":
                print("\nStarting default run (single Enter detected):")
                print(" - Steps 1+2 will run in parallel, then continue from step 3")

                # Prepare orchestrator and apply reasoning config (token caps removed)
                model = DEFAULT_MODEL
                base_name = "3d-solids"
                orchestrator = NetLogoOrchestrator(model_name=model)
                orchestrator.update_reasoning_config("low", "auto")
                orchestrator.update_text_config("medium")
                # Single parameter bundle line (includes text verbosity)
                default_bundle = format_parameter_bundle(
                    model=model,
                    base_name=base_name,
                    reasoning_effort="low",
                    reasoning_summary="auto",
                    text_verbosity="medium"
                )
                print(default_bundle)

                # Execute from step 1 (steps 1+2 are parallel internally)
                results = await orchestrator.run(base_name, start_step=1)

                # Summarize and exit main()
                ok = bool(results)
                print(f"\nDefault run finished. Success: {ok}")
                return
            
            model_number = int(model_input)
            if model_number == 0:
                selected_models = available_models
                break
            elif 1 <= model_number <= len(available_models):
                selected_models = [available_models[model_number - 1]]
                break
            else:
                print(f"Error: Invalid number {model_number}. Available options: 0-{len(available_models)}")
                print("Please enter a valid number, press Enter for default, or 'q' to quit:")
        except ValueError:
            print("Error: Please enter a valid number, press Enter for default, or 'q' to quit:")
    
    if len(selected_models) == 1:
        print(f"\nSelected AI Model: {selected_models[0]}")
    else:
        print(f"\nSelected AI Models: {', '.join(selected_models)}")
    
    # Base name selection
    print("\nNetLogo Orchestrator - Available Models")
    print("="*40)
    print("0. All cases (excluding: my-ecosys)")
    for i, base_name in enumerate(base_names, 1):
        print(f"{i:2d}. {base_name}")
    
    print("\nEnter the number of the NetLogo model to process (or press Enter for default 'my-ecosys', or 'q' to quit):")
    
    while True:
        try:
            user_input = input("NetLogo Model > ").strip()
            
            if user_input.lower() == 'q':
                print("Exiting...")
                return
            
            # Default to 'my-ecosys' if no input provided (fallback to first if missing)
            if user_input == "":
                default_base_name = "my-ecosys"
                chosen_base_name = default_base_name if default_base_name in base_names else base_names[0]
                selected_base_names = [chosen_base_name]
                print(f"Using default: {chosen_base_name}")
                break
            
            number = int(user_input)
            if number == 0:
                # Run all cases except explicitly excluded ones
                selected_base_names = [bn for bn in base_names if bn != "my-ecosys"]
                break
            elif 1 <= number <= len(base_names):
                selected_base_names = [base_names[number - 1]]
                break
            else:
                print(f"Error: Invalid number {number}. Available options: 0-{len(base_names)}")
                print("Please enter a valid number, press Enter for default, or 'q' to quit:")
        except ValueError:
            print("Error: Please enter a valid number, press Enter for default, or 'q' to quit:")
    
    if len(selected_base_names) == 1:
        print(f"\nProcessing model: {selected_base_names[0]}")
    else:
        print(f"\nProcessing models: {', '.join(selected_base_names)}")
    
    # Step selection for resume functionality
    print("\nNetLogo Orchestrator - Step Selection")
    print("="*40)
    print("Available Steps:")
    print("1. Syntax Parser (AST generation)")
    print("2. Semantics Parser (State Machine generation)")
    print("3. Messir Mapper (Messir concepts mapping)")
    print("4. Scenario Writer (Use case scenarios)")
    print("5. PlantUML Writer (Sequence diagrams)")
    print("6. PlantUML Messir Auditor (Compliance audit)")
    print("7. PlantUML Messir Corrector (Compliance correction)")
    print("8. PlantUML Messir Final Auditor (Final compliance verification)")
    
    print("\nEnter the step number to start from (1-8, or press Enter for default step 1, or 'q' to quit):")
    print("Note: Steps 1+2 are always executed in parallel, then continues from step 3.")
    print("Note: Starting from step N (N>=1) will skip steps 1 to N-1 and use existing results if available.")
    
    while True:
        try:
            step_input = input("Start from step > ").strip()
            
            if step_input.lower() == 'q':
                print("Exiting...")
                return
            
            # Default to step 1 if no input provided
            if step_input == "":
                start_step = 1
                print("Using default: Step 1 (Syntax Parser)")
                break
            
            start_step = int(step_input)
            if 1 <= start_step <= 8:
                break
            else:
                print(f"Error: Invalid step number {start_step}. Available options: 1-8")
                print("Please enter a valid step number, press Enter for default, or 'q' to quit:")
        except ValueError:
            print("Error: Please enter a valid number, press Enter for default, or 'q' to quit:")
    
    print(f"\nStarting workflow from step {start_step}")

    # Timeout preset selection (applies to all agents and orchestrator watchdog)
    print(f"\n{'='*60}")
    print("TIMEOUT PRESET SELECTION")
    print(f"{'='*60}")
    import utils_config_constants as cfg
    # Determine display of current defaults from utils_config_constants.py
    current_orch_default = getattr(cfg, "ORCHESTRATOR_PARALLEL_TIMEOUT", None)
    if current_orch_default is None:
        default_label = "No timeout"
    else:
        default_label = f"{current_orch_default}s"
    print("Choose timeout preset (applies to agents polling and orchestrator watchdog):")
    print("0. No timeout (agents and orchestrator)")
    print("1. Medium timeout (900s)")
    print("2. Long timeout (1800s)")
    print(f"Press Enter for default from utils_config_constants.py ({default_label})")
    print("Note: default utils_config_constants.py now sets NO TIMEOUT for both agents and orchestrator.")

    preset_map = {0: None, 1: 900, 2: 1800}
    while True:
        timeout_input = input("Timeout preset > ").strip()
        if timeout_input == "":
            # Keep utils_config_constants.py defaults as-is
            chosen_seconds = current_orch_default
            chosen_preset = "default"
            print(f"Using default from utils_config_constants.py: {default_label}")
            break
        try:
            timeout_choice = int(timeout_input)
            if timeout_choice in preset_map:
                chosen_seconds = preset_map[timeout_choice]
                chosen_preset = timeout_choice
                # Apply to orchestrator watchdog
                setattr(cfg, "ORCHESTRATOR_PARALLEL_TIMEOUT", chosen_seconds)
                # Apply to all agent timeouts (None -> unlimited)
                if hasattr(cfg, "AGENT_TIMEOUTS") and isinstance(cfg.AGENT_TIMEOUTS, dict):
                    for k in list(cfg.AGENT_TIMEOUTS.keys()):
                        cfg.AGENT_TIMEOUTS[k] = chosen_seconds
                label = "No timeout" if chosen_seconds is None else f"{chosen_seconds}s"
                print(f"Applied timeout preset {timeout_choice} → {label}")
                break
            else:
                print("Error: Invalid choice. Available options: 0,1,2 or Enter for default")
        except ValueError:
            print("Error: Please enter 0, 1, 2 or press Enter for default")
    
    # Token caps removed: no token configuration to display
    
    # Reasoning effort selection
    print(f"\n{'='*60}")
    print("REASONING EFFORT SELECTION")
    print(f"{'='*60}")
    print("Available reasoning effort levels:")
    print("1. Minimal effort (fastest)")
    print("2. Low effort")
    print("3. Medium effort - DEFAULT")
    print("4. High effort (highest quality)")
    print("   - Option 0 will run each effort level sequentially for comparison")
    print("   - Takes 3x longer but provides comprehensive analysis")
    
    print("\nEnter your choice (0-4, or press Enter for default medium, or 'q' to quit):")
    
    while True:
        try:
            reasoning_input = input("Reasoning effort > ").strip()
            
            if reasoning_input.lower() == 'q':
                print("Exiting...")
                return
            
            # Default to medium (3) if no input provided
            if reasoning_input == "":
                reasoning_choice = 3
                print("Using default: Medium effort")
                break
            
            reasoning_choice = int(reasoning_input)
            if 0 <= reasoning_choice <= 4:
                break
            else:
                print(f"Error: Invalid choice {reasoning_choice}. Available options: 0-4")
                print("Please enter a valid choice, press Enter for default, or 'q' to quit:")
        except ValueError:
            print("Error: Please enter a valid number, press Enter for default, or 'q' to quit:")
    
    # Define reasoning effort configurations
    reasoning_configs = {
        0: "all",  # Special case for all effort levels
        1: {"effort": "minimal", "summary": "auto"},
        2: {"effort": "low", "summary": "auto"},
        3: {"effort": "medium", "summary": "auto"},
        4: {"effort": "high", "summary": "auto"}
    }
    
    selected_reasoning = reasoning_configs[reasoning_choice]
    
    if selected_reasoning == "all":
        print(f"\nSelected: ALL reasoning effort levels (runs efforts sequentially for comparison)")
        print("This will run each effort level sequentially for comprehensive analysis.")
        reasoning_levels = [
            {"effort": "minimal", "summary": "auto"},
            {"effort": "low", "summary": "auto"},
            {"effort": "medium", "summary": "auto"},
            {"effort": "high", "summary": "auto"}
        ]
    else:
        print(f"\nSelected: {selected_reasoning['effort'].title()} effort")
        reasoning_levels = [selected_reasoning]
    
    # Prompt for text verbosity (single choice applied to all) BEFORE computing combinations
    print("\nTEXT VERBOSITY SELECTION")
    print("0. All verbosities (low, medium, high)")
    print("1. Low verbosity")
    print("2. Medium verbosity - DEFAULT")
    print("3. High verbosity")
    print("Enter your choice (0-3, or press Enter for default medium):")
    while True:
        text_input = input("Text verbosity > ").strip()
        if text_input == "":
            text_choice = 2
            print("Using default: Medium verbosity")
            break
        try:
            text_choice = int(text_input)
            if 0 <= text_choice <= 3:
                break
            else:
                print("Error: Invalid choice. Available options: 0-3")
        except ValueError:
            print("Error: Please enter a valid number or press Enter for default")
    text_map = {1: "low", 2: "medium", 3: "high"}

    # Determine which verbosity levels to run
    if text_choice == 0:
        selected_verbosity_levels = ["low", "medium", "high"]
    else:
        selected_verbosity_levels = [text_map[text_choice]]

    # Process all combinations
    all_results = {}
    total_combinations = (
        len(selected_models)
        * len(selected_base_names)
        * len(reasoning_levels)
        * len(selected_verbosity_levels)
    )
    current_combination = 0
    
    # Start timing the total execution
    total_execution_start_time = time.time()
    
    for model in selected_models:
        for base_name in selected_base_names:
            for reasoning_config in reasoning_levels:
                # Token caps removed: no token config
                
                # Create orchestrator with reasoning configuration
                orchestrator = NetLogoOrchestrator(model_name=model)
                
                # Update reasoning configuration for all agents
                orchestrator.update_reasoning_config(reasoning_config["effort"], reasoning_config["summary"])

                # Run for each selected verbosity level
                for verbosity in selected_verbosity_levels:
                    current_combination += 1
                    print(f"\n{'='*60}")
                    print(f"PROCESSING COMBINATION {current_combination}/{total_combinations}")
                    # Single parameter bundle line including text verbosity
                    print(f"{'='*60}")

                    orchestrator.update_text_config(verbosity)
                    # Print a single parameter bundle line including text verbosity
                    bundle_line = format_parameter_bundle(
                        model=model,
                        base_name=base_name,
                        reasoning_effort=reasoning_config["effort"],
                        reasoning_summary=reasoning_config["summary"],
                        text_verbosity=verbosity,
                        # No max_tokens
                    )
                    print(bundle_line)
                    
                    results = await orchestrator.run(base_name, start_step=start_step)
                    
                    # Create unique key for results including verbosity
                    reasoning_suffix = f"{reasoning_config['effort']}-{reasoning_config['summary']}"
                    result_key = f"{base_name}_{model}_{reasoning_suffix}_{verbosity}"
                    all_results[result_key] = results
    
    # Calculate total execution time
    total_execution_time = time.time() - total_execution_start_time
    
    # Calculate total timing across all orchestrations
    total_orchestration_time = 0
    total_agent_time = 0
    agent_timing_summary = {}
    
    # Calculate overall statistics
    total_files = len(all_results)
    total_agents = 0
    total_successful_agents = 0
    
    agent_keys = [
        "ast", "semantics", "lucim_environment_synthesizer", "lucim_scenario_synthesizer",
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
    
    print(f"\n⏱️  TOTAL EXECUTION TIME:")
    print(f"   Total time: {FormatUtils.format_duration(total_execution_time)}")
    
    print(f"\n{'='*80}")
    print("OVERALL SUMMARY")
    print(f"{'='*80}")
    print(f"Total combinations processed: {len(all_results)}")
    print(f"Total files processed: {total_files}")
    print(f"Total agents: {total_agents}")
    print(f"Successful agents: {total_successful_agents}")
    print(f"Overall success rate: {overall_success_rate:.1f}%")
    
    # Generate comprehensive orchestration summary
    if all_results:
        # Create a temporary orchestrator instance to call the summary method
        temp_orchestrator = NetLogoOrchestrator(model_name=DEFAULT_MODEL)
        temp_orchestrator.logger = setup_orchestration_logger("overall", DEFAULT_MODEL, datetime.datetime.now().strftime("%Y%m%d_%H%M"))
        attach_stdio_to_logger(temp_orchestrator.logger)
        temp_orchestrator._generate_orchestration_summary(all_results)
    


if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 