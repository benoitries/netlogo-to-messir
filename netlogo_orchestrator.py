#!/usr/bin/env python3
"""
NetLogo Orchestrator Agent
Orchestrates the processing of NetLogo files using both AST and Semantic agents in parallel using Google ADK inspired ParallelAgent.
"""

import os
import json
import datetime
import pathlib
import time
import logging
from typing import Dict, Any, List

def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string with seconds and human-readable format if > 60 seconds
    """
    if seconds < 60:
        return f"{seconds:.2f}s"
    else:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        
        if minutes == 1:
            if remaining_seconds == 0:
                return f"{seconds:.2f}s (1 minute)"
            else:
                return f"{seconds:.2f}s (1 minute and {remaining_seconds:.0f} seconds)"
        else:
            if remaining_seconds == 0:
                return f"{seconds:.2f}s ({minutes} minutes)"
            else:
                return f"{seconds:.2f}s ({minutes} minutes and {remaining_seconds:.0f} seconds)"
from netlogo_syntax_parser_agent import NetLogoSyntaxParserAgent
from netlogo_semantics_parser_agent import NetLogoSemanticsParserAgent
from netlogo_messir_mapper_agent import NetLogoMessirMapperAgent
from netlogo_scenario_writer_agent import NetLogoScenarioWriterAgent
from netlogo_plantuml_writer_agent import NetLogoPlantUMLWriterAgent
from netlogo_plantuml_auditor_agent import NetLogoPlantUMLMessirAuditorAgent
from netlogo_plantuml_messir_corrector_agent import NetLogoPlantUMLMessirCorrectorAgent
from netlogo_plantuml_auditor_agent import NetLogoPlantUMLMessirAuditorAgent

from config import (
    INPUT_NETLOGO_DIR, INPUT_ICRASH_DIR, OUTPUT_DIR, 
    AGENT_CONFIGS, AVAILABLE_MODELS, ensure_directories,
    validate_agent_response
)
from logging_utils import setup_orchestration_logger

# Ensure all directories exist
ensure_directories()

class NetLogoOrchestrator:
    """Orchestrator for processing NetLogo files using both AST and Semantic agents in parallel."""
    
    def __init__(self, model_name: str = "gpt-5", 
                 max_tokens_config: Dict[str, int] = None):
        """
        Initialize the NetLogo Orchestrator.
        
        Args:
            model_name: AI model to use for processing
            max_tokens_config: Dictionary mapping agent names to max token values
                              Default values will be used if not provided
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
            "syntax_parser": 0,
            "semantics_parser": 0,
            "messir_mapper": 0,
            "scenario_writer": 0,
            "plantuml_writer": 0,
            "plantuml_messir_auditor": 0,
            "plantuml_messir_corrector": 0,
            "plantuml_messir_final_auditor": 0
        }
        
        # Enhanced token usage tracking
        self.token_usage = {
            "syntax_parser": {"used": 0, "max": 0},
            "semantics_parser": {"used": 0, "max": 0},
            "messir_mapper": {"used": 0, "max": 0},
            "scenario_writer": {"used": 0, "max": 0},
            "plantuml_writer": {"used": 0, "max": 0},
            "plantuml_messir_auditor": {"used": 0, "max": 0},
            "plantuml_messir_corrector": {"used": 0, "max": 0},
            "plantuml_messir_final_auditor": {"used": 0, "max": 0}
        }
        
        # Detailed timing tracking with start/end timestamps
        self.detailed_timing = {
            "syntax_parser": {"start": 0, "end": 0, "duration": 0},
            "semantics_parser": {"start": 0, "end": 0, "duration": 0},
            "messir_mapper": {"start": 0, "end": 0, "duration": 0},
            "scenario_writer": {"start": 0, "end": 0, "duration": 0},
            "plantuml_writer": {"start": 0, "end": 0, "duration": 0},
            "plantuml_messir_auditor": {"start": 0, "end": 0, "duration": 0},
            "plantuml_messir_corrector": {"start": 0, "end": 0, "duration": 0},
            "plantuml_messir_final_auditor": {"start": 0, "end": 0, "duration": 0}
        }
        
        # Use provided config or defaults
        if max_tokens_config:
            self.max_tokens_config = max_tokens_config
        else:
            # Extract max_completion_tokens from agent configs
            self.max_tokens_config = {
                agent: config["max_completion_tokens"] 
                for agent, config in AGENT_CONFIGS.items()
            }
        
        # Store agent configurations for reasoning level updates
        self.agent_configs = AGENT_CONFIGS.copy()
        
        # Initialize max tokens in token usage tracking
        for agent_name in self.token_usage:
            self.token_usage[agent_name]["max"] = self.max_tokens_config.get(agent_name, 0)
        
        # Initialize agents with token configuration
        self.syntax_parser_agent = NetLogoSyntaxParserAgent(model_name, self.timestamp, max_tokens=self.max_tokens_config["syntax_parser"])
        self.semantics_parser_agent = NetLogoSemanticsParserAgent(model_name, self.timestamp, max_tokens=self.max_tokens_config["semantics_parser"])
        self.messir_mapper_agent = NetLogoMessirMapperAgent(model_name, self.timestamp, max_tokens=self.max_tokens_config["messir_mapper"])
        self.scenario_writer_agent = NetLogoScenarioWriterAgent(model_name, self.timestamp, max_tokens=self.max_tokens_config["scenario_writer"])
        self.plantuml_writer_agent = NetLogoPlantUMLWriterAgent(model_name, self.timestamp, max_tokens=self.max_tokens_config["plantuml_writer"])
        self.plantuml_messir_auditor_agent = NetLogoPlantUMLMessirAuditorAgent(model_name, self.timestamp, max_tokens=self.max_tokens_config["plantuml_auditor"])
        self.plantuml_messir_corrector_agent = NetLogoPlantUMLMessirCorrectorAgent(model_name, self.timestamp, max_tokens=self.max_tokens_config["plantuml_corrector"])
        self.plantuml_messir_final_auditor_agent = NetLogoPlantUMLMessirAuditorAgent(model_name, self.timestamp, max_tokens=self.max_tokens_config["plantuml_auditor"])
        
    def update_reasoning_config(self, reasoning_effort: str, reasoning_summary: str):
        """
        Update reasoning configuration for all agents.
        
        Args:
            reasoning_effort: "low", "medium", or "high"
            reasoning_summary: "auto" or "manual"
        """
        # Update agent configurations
        for agent_name in self.agent_configs:
            self.agent_configs[agent_name]["reasoning_effort"] = reasoning_effort
            self.agent_configs[agent_name]["reasoning_summary"] = reasoning_summary
        
        # Update individual agents
        self.syntax_parser_agent.update_reasoning_config(reasoning_effort, reasoning_summary)
        self.semantics_parser_agent.update_reasoning_config(reasoning_effort, reasoning_summary)
        self.messir_mapper_agent.update_reasoning_config(reasoning_effort, reasoning_summary)
        self.scenario_writer_agent.update_reasoning_config(reasoning_effort, reasoning_summary)
        self.plantuml_writer_agent.update_reasoning_config(reasoning_effort, reasoning_summary)
        self.plantuml_messir_auditor_agent.update_reasoning_config(reasoning_effort, reasoning_summary)
        self.plantuml_messir_corrector_agent.update_reasoning_config(reasoning_effort, reasoning_summary)
        self.plantuml_messir_final_auditor_agent.update_reasoning_config(reasoning_effort, reasoning_summary)
    
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
    
    def find_icrash_files(self) -> List[pathlib.Path]:
        """
        Find icrash files in the input-icrash directory.
        
        Returns:
            List of icrash file paths
        """
        icrash_files = []
        
        if INPUT_ICRASH_DIR.exists():
            for icrash_file in INPUT_ICRASH_DIR.glob("*.pdf"):
                icrash_files.append(icrash_file)
        
        if not icrash_files:
            if self.logger:
                self.logger.warning(f"Warning: No icrash files found in {INPUT_ICRASH_DIR}")
        
        return icrash_files
    
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
        self.logger.info(f"   Max tokens configured: {self.token_usage[agent_name]['max']:,}")
        
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
                self.token_usage[agent_name]["used"] = tokens_used
                
                self.logger.info(f"✅ {agent_name} completed in {format_duration(duration)}")
                self.logger.info(f"   Tokens used: {tokens_used:,} / {self.token_usage[agent_name]['max']:,}")
                self.logger.info(f"   Input tokens: {input_tokens:,}, Output tokens: {output_tokens:,}")
                if self.token_usage[agent_name]['max'] > 0:
                    efficiency = (tokens_used/self.token_usage[agent_name]['max']*100)
                    self.logger.info(f"   Token efficiency: {efficiency:.1f}%")
            else:
                self.logger.info(f"✅ {agent_name} completed in {format_duration(duration)}")
                self.logger.info(f"   Token usage: Not available")
            
            return result
            
        except Exception as e:
            # End timing even on error
            end_time = time.time()
            duration = end_time - start_time
            self.detailed_timing[agent_name]["end"] = end_time
            self.detailed_timing[agent_name]["duration"] = duration
            self.execution_times[agent_name] = duration
            
            self.logger.error(f"❌ {agent_name} failed after {format_duration(duration)}: {str(e)}")
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
            "syntax_parser", "semantics_parser", "messir_mapper", "scenario_writer",
            "plantuml_writer", "plantuml_messir_auditor", "plantuml_messir_corrector", "plantuml_messir_final_auditor"
        ]
        
        # Calculate totals
        total_time = sum(self.detailed_timing[agent]["duration"] for agent in self.detailed_timing)
        total_tokens_used = sum(self.token_usage[agent]["used"] for agent in self.token_usage)
        total_tokens_max = sum(self.token_usage[agent]["max"] for agent in self.token_usage)
        
        # Calculate input/output token totals from processed results
        agent_to_result_key = {
            "syntax_parser": "ast",
            "semantics_parser": "semantics",
            "messir_mapper": "messir_mapper",
            "scenario_writer": "scenario_writer",
            "plantuml_writer": "plantuml_writer",
            "plantuml_messir_auditor": "plantuml_messir_auditor",
            "plantuml_messir_corrector": "plantuml_messir_corrector",
            "plantuml_messir_final_auditor": "plantuml_messir_final_auditor",
        }
        total_input_tokens = 0
        total_output_tokens = 0
        for agent in agent_names:
            result_key = agent_to_result_key.get(agent, agent)
            if processed_results.get(result_key, {}).get("data"):
                total_input_tokens += processed_results[result_key].get("input_tokens", 0)
                total_output_tokens += processed_results[result_key].get("output_tokens", 0)
        
        # Agent execution summary table
        self.logger.info(f"\n📊 AGENT EXECUTION DETAILS:")
        self.logger.info(f"{'Agent':<25} {'Status':<10} {'Time':<15} {'Total Tokens':<15} {'Input':<10} {'Output':<10} {'Max':<10} {'Efficiency':<12}")
        self.logger.info(f"{'-'*100}")
        
        for agent in agent_names:
            duration = self.detailed_timing[agent]["duration"]
            tokens_used = self.token_usage[agent]["used"]
            max_tokens = self.token_usage[agent]["max"]
            result_key = agent_to_result_key.get(agent, agent)
            input_tokens = processed_results.get(result_key, {}).get("input_tokens", 0)
            output_tokens = processed_results.get(result_key, {}).get("output_tokens", 0)
            
            # Determine status using mapped result key
            if duration > 0:
                if processed_results.get(result_key, {}).get("data"):
                    status = "✓ SUCCESS"
                else:
                    status = "✗ FAILED"
            else:
                status = "⏭️ SKIPPED"
                duration = 0
                tokens_used = 0
                input_tokens = 0
                output_tokens = 0
            
            # Calculate efficiency
            if max_tokens > 0:
                efficiency = f"{(tokens_used/max_tokens*100):.1f}%"
            else:
                efficiency = "N/A"
            
            self.logger.info(f"{agent:<25} {status:<10} {format_duration(duration):<15} {tokens_used:<15,} {input_tokens:<10,} {output_tokens:<10,} {max_tokens:<10,} {efficiency:<12}")
        
        # Overall summary
        self.logger.info(f"\n📈 OVERALL SUMMARY:")
        self.logger.info(f"   Total Execution Time: {format_duration(total_time)}")
        self.logger.info(f"   Total Tokens Used: {total_tokens_used:,}")
        self.logger.info(f"   Total Input Tokens: {total_input_tokens:,}")
        self.logger.info(f"   Total Output Tokens: {total_output_tokens:,}")
        self.logger.info(f"   Total Max Tokens: {total_tokens_max:,}")
        if total_tokens_max > 0:
            self.logger.info(f"   Overall Token Efficiency: {(total_tokens_used/total_tokens_max*100):.1f}%")
        
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
                    "ast", "semantics", "messir_mapper", "scenario_writer",
                    "plantuml_writer", "plantuml_messir_auditor", "plantuml_messir_corrector", "plantuml_messir_final_auditor"
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
                    for agent in ["syntax_parser", "semantics_parser", "messir_mapper", "scenario_writer", 
                                 "plantuml_writer", "plantuml_messir_auditor", "plantuml_messir_corrector", "plantuml_messir_final_auditor"]
                )

            # Calculate success rate based on inner agent results of this orchestration
            inner_results = None
            if isinstance(result.get("results"), dict) and result["results"]:
                # There is typically one base_name key; take its dict
                inner_results = next(iter(result["results"].values()))

            agent_keys = [
                "ast", "semantics", "messir_mapper", "scenario_writer",
                "plantuml_writer", "plantuml_messir_auditor", "plantuml_messir_corrector", "plantuml_messir_final_auditor"
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

            self.logger.info(f"{orchestration_key:<30} {status:<10} {format_duration(total_time):<20} {total_tokens:<15,} {success_rate:<12.1f}%")
        
        # Overall statistics
        # Aggregate tokens used across all orchestrations from their inner results
        total_tokens_used = 0
        for result in all_results.values():
            inner_results = None
            if isinstance(result.get("results"), dict) and result["results"]:
                inner_results = next(iter(result["results"].values()))
            if isinstance(inner_results, dict):
                total_tokens_used += sum(
                    inner_results.get("token_usage", {}).get(agent, {}).get("used", 0)
                    for agent in ["syntax_parser", "semantics_parser", "messir_mapper", "scenario_writer", 
                                 "plantuml_writer", "plantuml_messir_auditor", "plantuml_messir_corrector", "plantuml_messir_final_auditor"]
                )
        
        self.logger.info(f"\n📊 OVERALL STATISTICS:")
        self.logger.info(f"   Total Orchestrations: {total_orchestrations}")
        self.logger.info(f"   Total Execution Time: {format_duration(total_execution_time)}")
        self.logger.info(f"   Total Tokens Used: {total_tokens_used:,}")
        self.logger.info(f"   Average Time per Orchestration: {format_duration(total_execution_time/total_orchestrations)}")
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
        
        # Define step patterns - updated to match actual file naming convention
        step_patterns = {
            1: f"{base_name}_*_{model}_1_syntax_parser_*_response.json",
            2: f"{base_name}_*_{model}_2_semantics_parser_*_response.json",
            3: f"{base_name}_*_{model}_3_messir_mapper_*_response.json",
            4: f"{base_name}_*_{model}_4_scenario_writer_*_response.json",
            5: f"{base_name}_*_{model}_5_plantuml_writer_*_response.json",
            6: f"{base_name}_*_{model}_6_plantuml_messir_auditor_*_response.json",
            7: f"{base_name}_*_{model}_7_plantuml_messir_corrector_*_response.json",
            8: f"{base_name}_*_{model}_8_plantuml_messir_final_auditor_*_response.json"
        }
        
        if step not in step_patterns:
            return None
        
        pattern = step_patterns[step]
        files = glob.glob(str(OUTPUT_DIR / pattern))
        
        if not files:
            return None
        
        # Get the most recent file
        latest_file = max(files, key=lambda x: pathlib.Path(x).stat().st_mtime)
        
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
                self.logger.info(f"Loaded existing results for step {step} from {pathlib.Path(latest_file).name}")
                
                # Update token usage tracking from loaded results
                if result and isinstance(result, dict):
                    tokens_used = result.get("tokens_used", 0)
                    input_tokens = result.get("input_tokens", 0)
                    output_tokens = result.get("output_tokens", 0)
                    
                    # Map step number to agent name
                    step_to_agent = {
                        1: "syntax_parser",
                        2: "semantics_parser", 
                        3: "messir_mapper",
                        4: "scenario_writer",
                        5: "plantuml_writer",
                        6: "plantuml_messir_auditor",
                        7: "plantuml_messir_corrector",
                        8: "plantuml_messir_final_auditor"
                    }
                    
                    agent_name = step_to_agent.get(step)
                    if agent_name and agent_name in self.token_usage:
                        self.token_usage[agent_name]["used"] = tokens_used
                        # Store input/output tokens in the result for later use
                        result["input_tokens"] = input_tokens
                        result["output_tokens"] = output_tokens
                        
                        # Update timing tracking (we don't have actual timing, so we'll set it to 0)
                        # This ensures the agent shows as executed but with 0 time
                        self.detailed_timing[agent_name]["duration"] = 0
                        self.execution_times[agent_name] = 0
                
                # The response files contain the data directly in fields like 'messir_concepts', 'ast', etc.
                # We need to return them in the expected format for the orchestrator
                return result
        except Exception as e:
            self.logger.warning(f"Warning: Could not load existing results for step {step}: {e}")
            return None
    
    def _process_with_syntax_parser_agent(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
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
                "agent_type": "syntax_parser",
                "reasoning_summary": f"Error reading code file: {e}",
                "data": None,
                "errors": [f"File reading error: {e}"]
            }
        
        # Use the AST agent to parse the code
        result = self.syntax_parser_agent.parse_netlogo_code(
            code_content, 
            f"{base_name}-netlogo-code.md"
        )
        
        # Add agent type identifier
        result["agent_type"] = "syntax_parser"
        
        # Save results using the AST agent's save method
        self.syntax_parser_agent.save_results(result, base_name, self.model, self.step_counter)
        self.step_counter += 1
        
        return result
    
    def _process_with_semantics_parser_agent(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
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
        
        # Read the NetLogo code
        try:
            code_content = code_file.read_text(encoding="utf-8")
        except Exception as e:
            return {
                "agent_type": "semantics_parser",
                "reasoning_summary": f"Error reading code file: {e}",
                "data": None,
                "errors": [f"File reading error: {e}"]
            }
        
        # Use the Semantic agent to parse the AST and interfaces
        # Note: This method is used for standalone processing, not in the sequential flow
        # For sequential flow, AST should be passed from Step 1
        result = self.semantics_parser_agent.parse_ast_to_state_machine(
            code_content,  # This should be AST data in sequential flow
            f"{base_name}-netlogo-code.md"
        )
        
        # Add agent type identifier
        result["agent_type"] = "semantics_parser"
        
        # Save results using the Semantics Parser agent's save method
        self.semantics_parser_agent.save_results(result, base_name, self.model, self.step_counter)
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
        
        # Start timing the total orchestration
        total_orchestration_start_time = time.time()
        
        self.logger.info(f"Starting sequential processing for {base_name}...")
        self.logger.info(f"Resume mode: Starting from step {start_step}")
        
        # Prepare input data
        code_file = file_info["code_file"]
        interface_images = file_info["interface_images"]
        
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
                messir_result = self.load_existing_results(base_name, self.model, 3)
                if messir_result:
                    processed_results["messir_mapper"] = messir_result
                    self.logger.info(f"✓ Loaded Messir Mapper results from step 3")
                else:
                    self.logger.warning(f"⚠️  No existing Messir Mapper results found for step 3")
            
            # Load Scenario Writer results (Step 4)
            if start_step > 4:
                scenario_result = self.load_existing_results(base_name, self.model, 4)
                if scenario_result:
                    processed_results["scenario_writer"] = scenario_result
                    self.logger.info(f"✓ Loaded Scenario Writer results from step 4")
                else:
                    self.logger.warning(f"⚠️  No existing Scenario Writer results found for step 4")
            
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
                    processed_results["plantuml_messir_auditor"] = audit_result
                    self.logger.info(f"✓ Loaded PlantUML Messir Auditor results from step 6")
                else:
                    self.logger.warning(f"⚠️  No existing PlantUML Messir Auditor results found for step 6")
            
            # Load PlantUML Messir Corrector results (Step 7)
            if start_step > 7:
                corrector_result = self.load_existing_results(base_name, self.model, 7)
                if corrector_result:
                    processed_results["plantuml_messir_corrector"] = corrector_result
                    self.logger.info(f"✓ Loaded PlantUML Messir Corrector results from step 7")
                else:
                    self.logger.warning(f"⚠️  No existing PlantUML Messir Corrector results found for step 7")
            
            self.logger.info(f"Resume preparation completed. Starting execution from step {start_step}")
        
        # Step 1: Syntax Parser Agent
        if start_step <= 1:
            self.logger.info(f"Step 1: Running Syntax Parser agent for {base_name}...")
            
            try:
                syntax_parser_result = self._execute_agent_with_tracking(
                    "syntax_parser",
                    self.syntax_parser_agent.parse_netlogo_code,
                    code_content, 
                    f"{base_name}-netlogo-code.md"
                )
                
                # Add agent type identifier
                syntax_parser_result["agent_type"] = "syntax_parser"
                
                # Save results using the Syntax Parser agent's save method
                self.syntax_parser_agent.save_results(syntax_parser_result, base_name, self.model, "1")  # Step 1 for Syntax Parser
                self.step_counter = 2  # Set step counter for next sequential agent
                
                processed_results["ast"] = syntax_parser_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "syntax_parser",
                    "reasoning_summary": f"Syntax Parser agent failed: {str(e)}",
                    "data": None,
                    "errors": [f"Syntax Parser agent error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 1: Syntax Parser agent failed for {base_name}: {str(e)}")
                processed_results["ast"] = error_result
        else:
            self.logger.info(f"Step 1: Skipping Syntax Parser agent for {base_name} (resume from step {start_step})")
        
        # Step 2: Semantics Parser Agent (using AST output from Step 1)
        if start_step <= 2 and processed_results.get("ast", {}).get("data"):
            self.logger.info(f"Step 2: Running Semantics Parser agent for {base_name}...")
            
            try:
                # Get AST data from Step 1 result
                ast_data = processed_results.get("ast", {}).get("data", "No AST available")
                
                # Convert AST data to JSON string if it's a dict/object
                if isinstance(ast_data, dict):
                    import json
                    ast_data = json.dumps(ast_data, indent=2, ensure_ascii=False)
                
                semantics_parser_result = self._execute_agent_with_tracking(
                    "semantics_parser",
                    self.semantics_parser_agent.parse_ast_to_state_machine,
                    ast_data,
                    f"{base_name}-netlogo-code.md"
                )
                
                # Add agent type identifier
                semantics_parser_result["agent_type"] = "semantics_parser"
                
                # Save results using the Semantics Parser agent's save method
                self.semantics_parser_agent.save_results(semantics_parser_result, base_name, self.model, "2")  # Step 2 for Semantics Parser
                self.step_counter = 3  # Set step counter for next sequential agent
                
                processed_results["semantics"] = semantics_parser_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "semantics_parser",
                    "reasoning_summary": f"Semantics Parser agent failed: {str(e)}",
                    "data": None,
                    "errors": [f"Semantics Parser agent error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 2: Semantics Parser agent failed for {base_name}: {str(e)}")
                processed_results["semantics"] = error_result
        elif start_step > 2:
            self.logger.info(f"Step 2: Skipping Semantics Parser agent for {base_name} (resume from step {start_step})")
        else:
            self.logger.info(f"Skipping Step 2: Semantics Parser agent for {base_name} (Syntax Parser failed)")
        
        # Step 3: Messir Mapper Agent (using AST and State Machine from previous steps)
        if start_step <= 3 and (processed_results.get("ast", {}).get("data") and 
            processed_results.get("semantics", {}).get("data")):
            
            self.logger.info(f"Step 3: Running Messir Mapper agent for {base_name}...")
            
            # Find and read icrash files
            icrash_files = self.find_icrash_files()
            icrash_contents = []
            
            for icrash_file in icrash_files:
                icrash_content = self.read_icrash_file_content(icrash_file)
                icrash_contents.append(icrash_content)
                self.logger.info(f"Found icrash file: {icrash_file.name}")
            
            try:
                messir_result = self._execute_agent_with_tracking(
                    "messir_mapper",
                    self.messir_mapper_agent.map_to_messir_concepts,
                    processed_results["semantics"]["data"],
                    base_name,
                    icrash_contents
                )
                
                # Add agent type identifier
                messir_result["agent_type"] = "messir_mapper"
                
                # Save results using the Messir mapper agent's save method
                self.messir_mapper_agent.save_results(messir_result, base_name, self.model, "3")  # Step 3 for Messir Mapper
                self.step_counter = 4  # Set step counter for next sequential agent
                
                processed_results["messir_mapper"] = messir_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "messir_mapper",
                    "reasoning_summary": f"Messir mapping failed: {str(e)}",
                    "data": None,
                    "errors": [f"Messir mapping error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 3: Messir Mapper agent failed for {base_name}: {str(e)}")
                processed_results["messir_mapper"] = error_result
        elif start_step > 3:
            self.logger.info(f"Step 3: Skipping Messir Mapper agent for {base_name} (resume from step {start_step})")
        else:
            self.logger.info(f"Skipping Step 3: Messir Mapper agent for {base_name} (AST or State Machine failed)")
        
        # Step 4: Scenario Writer Agent (using AST, Messir Concepts, and State Machine from previous steps)
        if start_step <= 4 and (processed_results.get("ast", {}).get("data") and 
            processed_results.get("messir_mapper", {}).get("data") and
            processed_results.get("semantics", {}).get("data")):
            
            self.logger.info(f"Step 4: Running Scenario Writer agent for {base_name}...")
            
            try:
                scenario_result = self._execute_agent_with_tracking(
                    "scenario_writer",
                    self.scenario_writer_agent.write_scenarios,
                    processed_results["messir_mapper"]["data"],
                    base_name
                )
                
                # Add agent type identifier
                scenario_result["agent_type"] = "scenario_writer"
                
                # Save results using the Scenario writer agent's save method
                self.scenario_writer_agent.save_results(scenario_result, base_name, self.model, "4")  # Step 4 for Scenario Writer
                self.step_counter = 5  # Set step counter for next sequential agent
                
                processed_results["scenario_writer"] = scenario_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "scenario_writer",
                    "reasoning_summary": f"Scenario writing failed: {str(e)}",
                    "data": None,
                    "errors": [f"Scenario writing error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 4: Scenario Writer agent failed for {base_name}: {str(e)}")
                processed_results["scenario_writer"] = error_result
        elif start_step > 4:
            self.logger.info(f"Step 4: Skipping Scenario Writer agent for {base_name} (resume from step {start_step})")
        else:
            self.logger.info(f"Skipping Step 4: Scenario Writer agent for {base_name} (AST, MessirConcepts, or State Machine failed)")
        
        # Step 5: PlantUML Writer Agent (using scenarios from previous step)
        if start_step <= 5 and processed_results.get("scenario_writer", {}).get("data"):
            
            self.logger.info(f"Step 5: Running PlantUML Writer agent for {base_name}...")
            
            try:
                plantuml_writer_result = self._execute_agent_with_tracking(
                    "plantuml_writer",
                    self.plantuml_writer_agent.generate_plantuml_diagrams,
                    processed_results["scenario_writer"]["data"],
                    base_name
                )
                
                # Add agent type identifier
                plantuml_writer_result["agent_type"] = "plantuml_writer"
                
                # Save results using the PlantUML writer agent's save method
                self.plantuml_writer_agent.save_results(plantuml_writer_result, base_name, self.model, "5")  # Step 5 for PlantUML Writer
                self.step_counter = 6  # Set step counter for next sequential agent
                
                processed_results["plantuml_writer"] = plantuml_writer_result
                
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
            self.logger.info(f"Step 5: Skipping PlantUML Writer agent for {base_name} (resume from step {start_step})")
        else:
            self.logger.info(f"Skipping Step 5: PlantUML Writer agent for {base_name} (Scenarios failed)")
        
        # Step 6: PlantUML Messir Auditor Agent (using PlantUML diagrams from previous step)
        if start_step <= 6 and processed_results.get("plantuml_writer", {}).get("data"):
            
            self.logger.info(f"Step 6: Running PlantUML Messir Auditor agent for {base_name}...")
            
            try:
                # Get scenarios data for context
                scenarios_data = processed_results.get("scenario_writer", {}).get("data", {})
                
                plantuml_messir_auditor_result = self._execute_agent_with_tracking(
                    "plantuml_messir_auditor",
                    self.plantuml_messir_auditor_agent.audit_plantuml_diagrams,
                    processed_results["plantuml_writer"]["data"],
                    scenarios_data,
                    base_name
                )
                
                # Add agent type identifier
                plantuml_messir_auditor_result["agent_type"] = "plantuml_messir_auditor"
                
                # Save results using the PlantUML Messir auditor agent's save method
                self.plantuml_messir_auditor_agent.save_results(plantuml_messir_auditor_result, base_name, self.model, "6")  # Step 6 for PlantUML Messir Auditor
                self.step_counter = 7  # Set step counter for next sequential agent
                
                processed_results["plantuml_messir_auditor"] = plantuml_messir_auditor_result
                
                # Early exit: if compliant after Step 6, end flow gracefully (skip steps 7 and 8)
                try:
                    audit_data = plantuml_messir_auditor_result.get("data", {}) if isinstance(plantuml_messir_auditor_result, dict) else {}
                    if audit_data and audit_data.get("verdict") == "compliant":
                        self.logger.info("Step 6 verdict is compliant. Ending flow gracefully. Skipping steps 7 and 8.")
                        # Calculate total orchestration time
                        total_orchestration_time = time.time() - total_orchestration_start_time
                        self.execution_times["total_orchestration"] = total_orchestration_time
                        self.logger.info(f"Total orchestration time: {format_duration(total_orchestration_time)}")
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
                    "agent_type": "plantuml_messir_auditor",
                    "reasoning_summary": f"PlantUML Messir auditing failed: {str(e)}",
                    "data": None,
                    "errors": [f"PlantUML Messir auditing error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 6: PlantUML Messir Auditor agent failed for {base_name}: {str(e)}")
                processed_results["plantuml_messir_auditor"] = error_result
        elif start_step > 6:
            self.logger.info(f"Step 6: Skipping PlantUML Messir Auditor agent for {base_name} (resume from step {start_step})")
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
            audit_data = processed_results.get("plantuml_messir_auditor", {}).get("data")
            audit_has_errors = bool(processed_results.get("plantuml_messir_auditor", {}).get("errors", []))
            
            # Extract non-compliant rules from audit data
            non_compliant_rules = audit_data.get("non-compliant-rules", []) if audit_data else []
            
            # Run corrector ONLY if we have non-compliant rules to fix
            if plantuml_data and audit_data and non_compliant_rules:
                self.logger.info(f"Step 7: Running PlantUML Messir Corrector agent for {base_name}...")
                
                try:
                    # Get scenarios data for context
                    scenarios_data = processed_results.get("scenario_writer", {}).get("data", {})
                    
                    plantuml_messir_corrector_result = self._execute_agent_with_tracking(
                        "plantuml_messir_corrector",
                        self.plantuml_messir_corrector_agent.correct_plantuml_diagrams,
                        plantuml_data,
                        scenarios_data,
                        non_compliant_rules,
                        base_name
                    )
                    
                    # Add agent type identifier
                    plantuml_messir_corrector_result["agent_type"] = "plantuml_messir_corrector"
                    
                    # Save results using the PlantUML Messir corrector agent's save method
                    self.plantuml_messir_corrector_agent.save_results(plantuml_messir_corrector_result, base_name, self.model, "7")  # Step 7 for PlantUML Messir Corrector
                    self.step_counter = 8  # Set step counter for next sequential agent
                    
                    processed_results["plantuml_messir_corrector"] = plantuml_messir_corrector_result
                    plantuml_messir_corrector_executed = True
                    plantuml_messir_corrector_success = True
                    
                except Exception as e:
                    error_result = {
                        "agent_type": "plantuml_messir_corrector",
                        "reasoning_summary": f"PlantUML Messir correction failed: {str(e)}",
                        "data": None,
                        "errors": [f"PlantUML Messir correction error: {str(e)}"]
                    }
                    self.logger.error(f"✗ Step 7: PlantUML Messir Corrector agent failed for {base_name}: {str(e)}")
                    processed_results["plantuml_messir_corrector"] = error_result
                    plantuml_messir_corrector_executed = True
                    plantuml_messir_corrector_success = False
                    
            elif plantuml_data and audit_data and not audit_has_errors:
                # Skip corrector if there are no non-compliant rules to fix
                self.logger.info(f"Step 7: Skipping PlantUML Messir Corrector agent for {base_name} (no non-compliant rules to fix)")
                processed_results["plantuml_messir_corrector"] = {
                    "agent_type": "plantuml_messir_corrector",
                    "reasoning_summary": "Corrector skipped - no non-compliant rules to fix",
                    "data": plantuml_data,  # Pass through original data
                    "errors": [],
                    "skipped": True
                }
                plantuml_messir_corrector_executed = False
                plantuml_messir_corrector_success = True
                
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
                    "agent_type": "plantuml_messir_corrector",
                    "reasoning_summary": f"Corrector skipped - Step 6 (auditor) failed or missing prerequisites: {', '.join(missing_prereq)}",
                    "data": None,
                    "errors": [f"Missing prerequisites: {', '.join(missing_prereq)}"]
                }
                self.logger.info(f"Step 7: Skipping PlantUML Messir Corrector agent for {base_name} (Step 6 failed or missing prerequisites)")
                processed_results["plantuml_messir_corrector"] = error_result
                plantuml_messir_corrector_executed = False
                plantuml_messir_corrector_success = False
        else:
            self.logger.info(f"Step 7: Skipping PlantUML Messir Corrector agent for {base_name} (resume from step {start_step})")
            # Add a placeholder entry to indicate the corrector was skipped due to resume
            processed_results["plantuml_messir_corrector"] = {
                "agent_type": "plantuml_messir_corrector",
                "reasoning_summary": f"Corrector skipped - resume from step {start_step}",
                "data": None,
                "errors": [],
                "skipped": True
            }
            plantuml_messir_corrector_executed = False
            plantuml_messir_corrector_success = True
        
        # Step 8: Final PlantUML Messir Auditor (always run)
        if start_step <= 8:
            self.logger.info(f"Step 8: Running PlantUML Messir Final Auditor agent for {base_name}...")
            
            try:
                # Determine what to audit based on corrector status
                corrector_has_data = processed_results.get("plantuml_messir_corrector", {}).get("data") is not None
                corrector_has_errors = bool(processed_results.get("plantuml_messir_corrector", {}).get("errors", []))
                
                if corrector_has_data and not corrector_has_errors:
                    # Audit the corrected PlantUML diagram from the corrector
                    plantuml_data_to_audit = processed_results["plantuml_messir_corrector"]["data"]
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
                scenarios_data = processed_results.get("scenario_writer", {}).get("data", {})
                
                plantuml_messir_final_auditor_result = self._execute_agent_with_tracking(
                    "plantuml_messir_final_auditor",
                    self.plantuml_messir_final_auditor_agent.audit_plantuml_diagrams,
                    plantuml_data_to_audit,
                    scenarios_data,
                    base_name
                )
                
                # Add agent type identifier
                plantuml_messir_final_auditor_result["agent_type"] = "plantuml_messir_final_auditor"
                
                # Save results using the PlantUML Messir auditor agent's save method
                self.plantuml_messir_final_auditor_agent.save_results(plantuml_messir_final_auditor_result, base_name, self.model, "8")  # Step 8 for Final Auditor
                self.step_counter = 9  # Set step counter for next sequential agent
                
                processed_results["plantuml_messir_final_auditor"] = plantuml_messir_final_auditor_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "plantuml_messir_final_auditor",
                    "reasoning_summary": f"PlantUML Messir final audit failed: {str(e)}",
                    "data": None,
                    "errors": [f"PlantUML Messir final audit error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 8: PlantUML Messir Final Auditor agent failed for {base_name}: {str(e)}")
                processed_results["plantuml_messir_final_auditor"] = error_result
        else:
            self.logger.info(f"Step 8: Skipping PlantUML Messir Final Auditor agent for {base_name} (resume from step {start_step})")
            # Add a placeholder entry to indicate the final auditor was skipped due to resume
            processed_results["plantuml_messir_final_auditor"] = {
                "agent_type": "plantuml_messir_final_auditor",
                "reasoning_summary": f"Final auditor skipped - resume from step {start_step}",
                "data": None,
                "errors": [],
                "skipped": True
            }
        
        # Calculate total orchestration time
        total_orchestration_time = time.time() - total_orchestration_start_time
        self.execution_times["total_orchestration"] = total_orchestration_time
        
        self.logger.info(f"Completed processing for {base_name}")
        self.logger.info(f"Total orchestration time: {format_duration(total_orchestration_time)}")
        
        # Generate enhanced detailed summary with timing and token usage
        self._generate_detailed_summary(base_name, processed_results)
        
        # Add timing and token usage information to the results
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
        # Set up logging for this orchestration run
        self.logger = setup_orchestration_logger(base_name, self.model, self.timestamp)
        
        # Log token configuration
        self.logger.info("Token configuration:")
        for agent, tokens in self.max_tokens_config.items():
            self.logger.info(f"  - {agent}: {tokens:,} tokens")
        
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
        
        # Process each file with sequential agent calls
        for file_info in files:
            base_name = file_info["base_name"]
            result = await self.process_netlogo_file_sequential(file_info, start_step)
            results[base_name] = result
            
                    # Print status
            syntax_parser_success = result.get("ast", {}).get("data") is not None
            semantics_parser_success = result.get("semantics", {}).get("data") is not None
            messir_success = result.get("messir_mapper", {}).get("data") is not None
            scenario_success = result.get("scenario_writer", {}).get("data") is not None
            plantuml_writer_success = result.get("plantuml_writer", {}).get("data") is not None
            plantuml_messir_auditor_success = result.get("plantuml_messir_auditor", {}).get("data") is not None
            plantuml_messir_corrector_success = result.get("plantuml_messir_corrector", {}).get("data") is not None
            plantuml_messir_final_auditor_success = result.get("plantuml_messir_final_auditor", {}).get("data") is not None
            
            # Check if PlantUML Messir Corrector was executed (only if diagrams were non-compliant)
            plantuml_messir_corrector_executed = "plantuml_messir_corrector" in result
            plantuml_messir_final_auditor_executed = "plantuml_messir_final_auditor" in result
            
            # Determine if agents were skipped (not present in result) vs failed (present but failed)
            # A step is skipped if it's not in the result at all, not if it failed
            semantics_skipped = "semantics" not in result
            messir_skipped = "messir_mapper" not in result
            scenario_skipped = "scenario_writer" not in result
            plantuml_writer_skipped = "plantuml_writer" not in result
            plantuml_messir_auditor_skipped = "plantuml_messir_auditor" not in result
            
            self.logger.info(f"{base_name} results:")
            self.logger.info(f"  Step 1 - Syntax Parser: {'✓' if syntax_parser_success else '✗'}")
            self.logger.info(f"  Step 2 - Semantics Parser: {'✓' if semantics_parser_success else '✗'}")
            self.logger.info(f"  Step 3 - Messir Mapper: {'✓' if messir_success else '✗'}")
            self.logger.info(f"  Step 4 - Scenario Writer: {'✓' if scenario_success else '✗'}")
            self.logger.info(f"  Step 5 - PlantUML Writer: {'✓' if plantuml_writer_success else '✗'}")
            self.logger.info(f"  Step 6 - PlantUML Messir Auditor: {'✓' if plantuml_messir_auditor_success else '✗'}")
            if plantuml_messir_corrector_executed:
                self.logger.info(f"  Step 7 - PlantUML Messir Corrector: {'✓' if plantuml_messir_corrector_success else '✗'}")
            if plantuml_messir_final_auditor_executed:
                self.logger.info(f"  Step 8 - PlantUML Messir Final Auditor: {'✓' if plantuml_messir_final_auditor_success else '✗'}")
            else:
                self.logger.info(f"  Step 7 - PlantUML Messir Corrector: SKIPPED (diagrams already compliant)")
            
            if not syntax_parser_success and result.get("ast", {}).get("errors"):
                self.logger.warning(f"    Step 1 - Syntax Parser errors: {len(result['ast']['errors'])} found")
            if not semantics_parser_success and result.get("semantics", {}).get("errors"):
                self.logger.warning(f"    Step 2 - Semantics Parser errors: {len(result['semantics']['errors'])} found")
            if not messir_success and result.get("messir_mapper", {}).get("errors"):
                self.logger.warning(f"    Step 3 - Messir mapping errors: {len(result['messir_mapper']['errors'])} found")
            if not scenario_success and result.get("scenario_writer", {}).get("errors"):
                self.logger.warning(f"    Step 4 - Scenario writing errors: {len(result['scenario_writer']['errors'])} found")
            if not plantuml_writer_success and result.get("plantuml_writer", {}).get("errors"):
                self.logger.warning(f"    Step 5 - PlantUML writing errors: {len(result['plantuml_writer']['errors'])} found")
            if not plantuml_messir_auditor_success and result.get("plantuml_messir_auditor", {}).get("errors"):
                self.logger.warning(f"    Step 6 - PlantUML Messir auditing errors: {len(result['plantuml_messir_auditor']['errors'])} found")
            
            if plantuml_messir_corrector_executed and not plantuml_messir_corrector_success and result.get("plantuml_messir_corrector", {}).get("errors"):
                self.logger.warning(f"    Step 7 - PlantUML Messir correction errors: {len(result['plantuml_messir_corrector']['errors'])} found")
        
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
        if syntax_parser_success: successful_agents += 1
        else: failed_agents += 1
        
        if semantics_parser_success: successful_agents += 1
        else: failed_agents += 1
        
        if messir_success: successful_agents += 1
        else: failed_agents += 1
        
        if scenario_success: successful_agents += 1
        else: failed_agents += 1
        
        if plantuml_writer_success: successful_agents += 1
        else: failed_agents += 1
        
        if plantuml_messir_auditor_success: successful_agents += 1
        else: failed_agents += 1
        
        # Add PlantUML Messir Corrector only if it was executed
        if plantuml_messir_corrector_executed:
            total_agents += 1
            if plantuml_messir_corrector_success: successful_agents += 1
            else: failed_agents += 1
        
        # Add PlantUML Messir Final Auditor only if it was executed
        if plantuml_messir_final_auditor_executed:
            total_agents += 1
            if plantuml_messir_final_auditor_success: successful_agents += 1
            else: failed_agents += 1
        
        self.logger.info(f"📊 OVERALL STATUS:")
        self.logger.info(f"   Total Agents: {total_agents}")
        self.logger.info(f"   Successful: {successful_agents} ✓")
        self.logger.info(f"   Failed: {failed_agents} ✗")
        self.logger.info(f"   Success Rate: {(successful_agents/total_agents)*100:.1f}%")
        
        print(f"\n⏱️  EXECUTION TIMING:")
        self.logger.info(f"   Total Orchestration Time: {format_duration(self.execution_times['total_orchestration'])}")
        
        # Calculate and display individual agent times
        total_agent_time = 0
        agent_times = []
        
        if self.execution_times["syntax_parser"] > 0:
            agent_times.append(("Step 1 - Syntax Parser", self.execution_times["syntax_parser"]))
            total_agent_time += self.execution_times["syntax_parser"]
        
        if self.execution_times["semantics_parser"] > 0:
            agent_times.append(("Step 2 - Semantics Parser", self.execution_times["semantics_parser"]))
            total_agent_time += self.execution_times["semantics_parser"]
        
        if self.execution_times["messir_mapper"] > 0:
            agent_times.append(("Step 3 - Messir Mapper", self.execution_times["messir_mapper"]))
            total_agent_time += self.execution_times["messir_mapper"]
        
        if self.execution_times["scenario_writer"] > 0:
            agent_times.append(("Step 4 - Scenario Writer", self.execution_times["scenario_writer"]))
            total_agent_time += self.execution_times["scenario_writer"]
        
        if self.execution_times["plantuml_writer"] > 0:
            agent_times.append(("Step 5 - PlantUML Writer", self.execution_times["plantuml_writer"]))
            total_agent_time += self.execution_times["plantuml_writer"]
        
        if self.execution_times["plantuml_messir_auditor"] > 0:
            agent_times.append(("Step 6 - PlantUML Messir Auditor", self.execution_times["plantuml_messir_auditor"]))
            total_agent_time += self.execution_times["plantuml_messir_auditor"]
        
        if self.execution_times["plantuml_messir_corrector"] > 0:
            agent_times.append(("Step 7 - PlantUML Messir Corrector", self.execution_times["plantuml_messir_corrector"]))
            total_agent_time += self.execution_times["plantuml_messir_corrector"]
        
        if self.execution_times["plantuml_messir_final_auditor"] > 0:
            agent_times.append(("Step 8 - PlantUML Messir Final Auditor", self.execution_times["plantuml_messir_final_auditor"]))
            total_agent_time += self.execution_times["plantuml_messir_final_auditor"]
        
        # Sort agents by execution time (descending)
        agent_times.sort(key=lambda x: x[1], reverse=True)
        
        self.logger.info(f"   Total Agent Execution Time: {format_duration(total_agent_time)}")
        self.logger.info(f"   Overhead Time: {format_duration(self.execution_times['total_orchestration'] - total_agent_time)}")
        
        if agent_times:
            self.logger.info(f"   \n   📈 AGENT TIMING BREAKDOWN:")
            for agent_name, agent_time in agent_times:
                percentage = (agent_time / total_agent_time * 100) if total_agent_time > 0 else 0
                self.logger.info(f"      {agent_name}: {format_duration(agent_time)} ({percentage:.1f}%)")
        
        print(f"\n🔍 DETAILED AGENT STATUS:")
        self.logger.info(f"   Step 1 - Syntax Parser Agent: {'✓ SUCCESS' if syntax_parser_success else '✗ FAILED'}")
        
        # Step 2 - Semantics Parser
        if semantics_skipped:
            self.logger.info(f"   Step 2 - Semantics Parser Agent: ⏭️  SKIPPED (Syntax Parser failed)")
        else:
            self.logger.info(f"   Step 2 - Semantics Parser Agent: {'✓ SUCCESS' if semantics_parser_success else '✗ FAILED'}")
        
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
        if plantuml_messir_auditor_skipped:
            self.logger.info(f"   Step 6 - PlantUML Messir Auditor Agent: ⏭️  SKIPPED (PlantUML diagrams failed)")
        else:
            self.logger.info(f"   Step 6 - PlantUML Messir Auditor Agent: {'✓ SUCCESS' if plantuml_messir_auditor_success else '✗ FAILED'}")
        
        # Step 7 - PlantUML Messir Corrector
        if not plantuml_messir_corrector_executed:
            self.logger.info(f"   Step 7 - PlantUML Messir Corrector Agent: ⏭️  SKIPPED (diagrams already compliant)")
        else:
            self.logger.info(f"   Step 7 - PlantUML Messir Corrector Agent: {'✓ SUCCESS' if plantuml_messir_corrector_success else '✗ FAILED'}")
        
        # Step 8 - PlantUML Messir Final Auditor
        if not plantuml_messir_final_auditor_executed:
            self.logger.info(f"   Step 8 - PlantUML Messir Final Auditor Agent: ⏭️  SKIPPED (corrector was skipped or not required)")
        else:
            self.logger.info(f"   Step 8 - PlantUML Messir Final Auditor Agent: {'✓ SUCCESS' if plantuml_messir_final_auditor_success else '✗ FAILED'}")
        
        self.logger.info(f"\n📁 OUTPUT FILES GENERATED:")
        for result_key, result_data in result.items():
            if result_data and isinstance(result_data, dict):
                agent_type = result_data.get("agent_type", "unknown")
                if agent_type == "syntax_parser":
                    self.logger.info(f"   • Syntax Parser: {base_name}_{self.timestamp}_{self.model}_1a_syntax_parser_v1_*.md")
                elif agent_type == "semantics_parser":
                    self.logger.info(f"   • Semantics Parser: {base_name}_{self.timestamp}_{self.model}_1b_semantics_parser_v1_*.json/md")
                elif agent_type == "messir_mapper":
                    self.logger.info(f"   • Messir Mapper: {base_name}_{self.timestamp}_{self.model}_2_messir_v1_*.json/md")
                elif agent_type == "scenario_writer":
                    self.logger.info(f"   • Scenarios: {base_name}_{self.timestamp}_{self.model}_3_scenario_v1_*.md")
                elif agent_type == "plantuml_writer":
                    self.logger.info(f"   • PlantUML Diagrams: {base_name}_{self.timestamp}_{self.model}_4_plantuml_*.json/md/.puml")
                elif agent_type == "plantuml_messir_auditor":
                    self.logger.info(f"   • PlantUML Messir Audit: {base_name}_{self.timestamp}_{self.model}_5_messir_audit_*.json/md/.puml")
                elif agent_type == "plantuml_messir_corrector":
                    self.logger.info(f"   • PlantUML Messir Corrector: {base_name}_{self.timestamp}_{self.model}_7_messir_corrector_*.json/md/.puml")
                elif agent_type == "plantuml_messir_final_auditor":
                    self.logger.info(f"   • PlantUML Messir Final Auditor: {base_name}_{self.timestamp}_{self.model}_8_messir_final_auditor_*.json/md/.puml")
                elif agent_type == "plantuml_messir_auditor" and not plantuml_messir_corrector_executed:
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
        
        # Add compliance status information
        self.logger.info(f"\n🔍 COMPLIANCE STATUS:")
        if plantuml_messir_final_auditor_success:
            self.logger.info(f"   ✅ FINAL COMPLIANCE: VERIFIED")
            self.logger.info(f"   🎯 Result: Final audit confirms Messir compliance")
        elif plantuml_messir_corrector_success:
            self.logger.info(f"   ⚠️  COMPLIANCE STATUS: CORRECTED")
            self.logger.info(f"   📊 Result: Diagrams corrected, final verification pending")
        elif plantuml_messir_auditor_success and not plantuml_messir_corrector_executed:
            self.logger.info(f"   ✅ FINAL COMPLIANCE: ACHIEVED")
            self.logger.info(f"   🎯 Result: All PlantUML diagrams were already Messir-compliant")
        elif plantuml_messir_auditor_success:
            self.logger.info(f"   ⚠️  COMPLIANCE STATUS: AUDITED")
            self.logger.info(f"   📊 Result: Diagrams audited, correction may be needed")
        else:
            self.logger.info(f"   ❓ COMPLIANCE STATUS: UNKNOWN")
            self.logger.info(f"   ⚠️  Result: PlantUML Messir Auditor failed - no compliance data available")
        
        self.logger.info(f"{'='*60}")
        
        return {
            "base_name": base_name,
            "files_processed": len(files),
            "total_agents": total_agents,
            "successful_agents": successful_agents,
            "failed_agents": failed_agents,
            "success_rate": (successful_agents/total_agents)*100 if total_agents > 0 else 0,
            "results": results
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
    
    print("\nEnter the number of the AI model to use (or press Enter for default model 1, or 'q' to quit):")
    
    while True:
        try:
            model_input = input("Model > ").strip()
            
            if model_input.lower() == 'q':
                print("Exiting...")
                return
            
            # Default to model 1 if no input provided
            if model_input == "":
                model_number = 1
                selected_models = [available_models[0]]
                print(f"Using default: {available_models[0]}")
                break
            
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
    print("0. All models")
    for i, base_name in enumerate(base_names, 1):
        print(f"{i:2d}. {base_name}")
    
    print("\nEnter the number of the NetLogo model to process (or press Enter for default model 1, or 'q' to quit):")
    
    while True:
        try:
            user_input = input("NetLogo Model > ").strip()
            
            if user_input.lower() == 'q':
                print("Exiting...")
                return
            
            # Default to model 1 if no input provided
            if user_input == "":
                number = 1
                selected_base_names = [base_names[0]]
                print(f"Using default: {base_names[0]}")
                break
            
            number = int(user_input)
            if number == 0:
                selected_base_names = base_names
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
    print("Note: Starting from step N will skip steps 1 to N-1 and use existing results if available.")
    
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
    
    # Use default token configuration
    token_config = {
        agent: config["max_completion_tokens"] 
        for agent, config in AGENT_CONFIGS.items()
    }
    
    print(f"\nToken configuration:")
    for agent, tokens in token_config.items():
        print(f"  - {agent}: {tokens:,} tokens")
    
    # Reasoning effort selection
    print(f"\n{'='*60}")
    print("REASONING EFFORT SELECTION")
    print(f"{'='*60}")
    print("Available reasoning effort levels:")
    print("0. ALL effort levels (sequential execution)")
    print("1. Low effort (fastest)")
    print("2. Medium effort (balanced) - DEFAULT")
    print("3. High effort (highest quality)")
    print("   - Option 0 will run each effort level sequentially for comparison")
    print("   - Takes 3x longer but provides comprehensive analysis")
    
    print("\nEnter your choice (0-3, or press Enter for default medium, or 'q' to quit):")
    
    while True:
        try:
            reasoning_input = input("Reasoning effort > ").strip()
            
            if reasoning_input.lower() == 'q':
                print("Exiting...")
                return
            
            # Default to medium (2) if no input provided
            if reasoning_input == "":
                reasoning_choice = 2
                print("Using default: Medium effort")
                break
            
            reasoning_choice = int(reasoning_input)
            if 0 <= reasoning_choice <= 3:
                break
            else:
                print(f"Error: Invalid choice {reasoning_choice}. Available options: 0-3")
                print("Please enter a valid choice, press Enter for default, or 'q' to quit:")
        except ValueError:
            print("Error: Please enter a valid number, press Enter for default, or 'q' to quit:")
    
    # Define reasoning effort configurations
    reasoning_configs = {
        0: "all",  # Special case for all effort levels
        1: {"effort": "low", "summary": "auto"},
        2: {"effort": "medium", "summary": "auto"},
        3: {"effort": "high", "summary": "auto"}
    }
    
    selected_reasoning = reasoning_configs[reasoning_choice]
    
    if selected_reasoning == "all":
        print(f"\nSelected: ALL reasoning effort levels (sequential execution)")
        print("This will run each effort level sequentially for comprehensive analysis.")
        reasoning_levels = [
            {"effort": "low", "summary": "auto"},
            {"effort": "medium", "summary": "auto"},
            {"effort": "high", "summary": "auto"}
        ]
    else:
        print(f"\nSelected: {selected_reasoning['effort'].title()} effort")
        reasoning_levels = [selected_reasoning]
    
    # Process all combinations
    all_results = {}
    total_combinations = len(selected_models) * len(selected_base_names) * len(reasoning_levels)
    current_combination = 0
    
    # Start timing the total execution
    total_execution_start_time = time.time()
    
    for model in selected_models:
        for base_name in selected_base_names:
            for reasoning_config in reasoning_levels:
                current_combination += 1
                print(f"\n{'='*60}")
                print(f"PROCESSING COMBINATION {current_combination}/{total_combinations}")
                print(f"Model: {base_name} with AI model: {model}")
                print(f"Reasoning effort: {reasoning_config['effort'].title()}")
                print(f"{'='*60}")
                
                # Create token config with reasoning settings
                reasoning_token_config = token_config.copy()
                
                # Create orchestrator with reasoning configuration
                orchestrator = NetLogoOrchestrator(model_name=model, max_tokens_config=reasoning_token_config)
                
                # Update reasoning configuration for all agents
                orchestrator.update_reasoning_config(reasoning_config["effort"], reasoning_config["summary"])
                
                results = await orchestrator.run(base_name, start_step=start_step)
                
                # Create unique key for results
                reasoning_suffix = f"{reasoning_config['effort']}-{reasoning_config['summary']}"
                result_key = f"{base_name}_{model}_{reasoning_suffix}"
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
        "ast", "semantics", "messir_mapper", "scenario_writer",
        "plantuml_writer", "plantuml_messir_auditor", "plantuml_messir_corrector", "plantuml_messir_final_auditor"
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
    print(f"   Total time: {format_duration(total_execution_time)}")
    
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
        temp_orchestrator = NetLogoOrchestrator(model_name="gpt-5")
        temp_orchestrator.logger = setup_orchestration_logger("overall", "gpt-5", datetime.datetime.now().strftime("%Y%m%d_%H%M"))
        temp_orchestrator._generate_orchestration_summary(all_results)
    


if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 