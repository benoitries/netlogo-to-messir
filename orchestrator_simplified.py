#!/usr/bin/env python3
"""
NetLogo Orchestrator Agent - Simplified Version
Orchestrates the processing of NetLogo files using a simplified 8-stage pipeline.
"""

import os
import asyncio
import json
import datetime
import pathlib
import time
import logging
from typing import Dict, Any, List, Optional

from agent_1_netlogo_abstract_syntax_extractor import NetLogoAbstractSyntaxExtractorAgent
from agent_2a_netlogo_interface_image_analyzer import NetLogoInterfaceImageAnalyzerAgent
from agent_2b_netlogo_behavior_extractor import NetLogoBehaviorExtractorAgent
from agent_3_lucim_environment_synthesizer import NetLogoLucimEnvironmentSynthesizerAgent
from agent_4_lucim_scenario_synthesizer import NetLogoLUCIMScenarioSynthesizerAgent
from agent_5_plantuml_writer import NetLogoPlantUMLWriterAgent
from agent_6_plantuml_auditor import NetLogoPlantUMLLUCIMAuditorAgent
from agent_7_plantuml_corrector import NetLogoPlantUMLLUCIMCorrectorAgent

from utils_config_constants import (
    INPUT_NETLOGO_DIR, OUTPUT_DIR, INPUT_PERSONA_DIR,
    AGENT_CONFIGS, AVAILABLE_MODELS, DEFAULT_MODEL, DEFAULT_PERSONA_SET, ensure_directories,
    validate_agent_response, LUCIM_RULES_FILE, get_persona_file_paths
)
from utils_logging import setup_orchestration_logger, format_parameter_bundle, attach_stdio_to_logger
from utils_path import get_run_base_dir
from utils_orchestrator_logging import OrchestratorLogger
from utils_orchestrator_ui import OrchestratorUI
from utils_orchestrator_fileio import OrchestratorFileIO
from utils_format import FormatUtils

# Ensure all directories exist
ensure_directories()


class NetLogoOrchestratorSimplified:
    """Simplified orchestrator for processing NetLogo files with a clean 8-stage pipeline."""
    
    def __init__(self, model_name: str = DEFAULT_MODEL, persona_set: Optional[str] = None):
        """
        Initialize the NetLogo Orchestrator.
        
        Args:
            model_name: AI model to use for processing
            persona_set: Optional persona set to use (bypasses interactive selection)
        """
        self.model = model_name
        # Do not force a default persona here; let the UI handle interactive selection when None
        self.persona_set = persona_set
        # Format: YYYYMMDD_HHMM for better readability
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        
        # Initialize logger (will be set up properly when processing starts)
        self.logger = None
        self.orchestrator_logger = None
        
        # Initialize utilities
        self.ui = OrchestratorUI()
        self.fileio = OrchestratorFileIO()
        
        # Timing tracking
        self.execution_times = {
            "total_orchestration": 0,
            "netlogo_abstract_syntax_extractor": 0,
            "netlogo_interface_image_analyzer": 0,
            "behavior_extractor": 0,
            "lucim_environment_synthesizer": 0,
            "lucim_scenario_synthesizer": 0,
            "plantuml_writer": 0,
            "plantuml_lucim_auditor": 0,
            "plantuml_lucim_corrector": 0,
            "plantuml_lucim_final_auditor": 0
        }
        
        # Token usage tracking
        self.token_usage = {
            "netlogo_abstract_syntax_extractor": {"used": 0},
            "netlogo_interface_image_analyzer": {"used": 0},
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
            "netlogo_interface_image_analyzer": {"start": 0, "end": 0, "duration": 0},
            "behavior_extractor": {"start": 0, "end": 0, "duration": 0},
            "lucim_environment_synthesizer": {"start": 0, "end": 0, "duration": 0},
            "lucim_scenario_synthesizer": {"start": 0, "end": 0, "duration": 0},
            "plantuml_writer": {"start": 0, "end": 0, "duration": 0},
            "plantuml_lucim_auditor": {"start": 0, "end": 0, "duration": 0},
            "plantuml_lucim_corrector": {"start": 0, "end": 0, "duration": 0},
            "plantuml_lucim_final_auditor": {"start": 0, "end": 0, "duration": 0}
        }
        
        # Store agent configurations for reasoning level updates
        self.selected_persona_set = None
        self.agent_configs = AGENT_CONFIGS.copy()
        
        # Initialize agents
        self.netlogo_abstract_syntax_extractor_agent = NetLogoAbstractSyntaxExtractorAgent(model_name, self.timestamp)
        # Defer IL-SYN path configuration until persona set is selected (post-initialize_persona_set)
        self.netlogo_interface_image_analyzer_agent = NetLogoInterfaceImageAnalyzerAgent(model_name, self.timestamp)
        self.behavior_extractor_agent = NetLogoBehaviorExtractorAgent(model_name, self.timestamp)
        # Defer IL-SEM inputs configuration until persona set is selected
        
        self.lucim_environment_synthesizer_agent = NetLogoLucimEnvironmentSynthesizerAgent(model_name, self.timestamp)
        self.lucim_scenario_synthesizer_agent = NetLogoLUCIMScenarioSynthesizerAgent(model_name, self.timestamp)
        self.plantuml_writer_agent = NetLogoPlantUMLWriterAgent(model_name, self.timestamp)
        self.plantuml_lucim_auditor_agent = NetLogoPlantUMLLUCIMAuditorAgent(model_name, self.timestamp)
        self.plantuml_lucim_corrector_agent = NetLogoPlantUMLLUCIMCorrectorAgent(model_name, self.timestamp)
        self.plantuml_lucim_final_auditor_agent = NetLogoPlantUMLLUCIMAuditorAgent(model_name, self.timestamp)
        
        # Initialize persona set selection after agents are created
        self.initialize_persona_set()

    def initialize_persona_set(self):
        """
        Initialize persona set selection (interactive or pre-selected).
        Updates agent configurations with the selected persona set.
        """
        # Select persona set (interactive or use pre-selected)
        self.selected_persona_set = self.ui.select_persona_set(self.persona_set)
        
        # Update persona file paths for all agents
        self._update_agent_persona_paths()
        
        # Log the selection (will be logged later when logger is available)
        print(f"✅ Initialized persona set: {self.selected_persona_set}")

    def _update_agent_persona_paths(self):
        """
        Update persona file paths for all agents based on selected persona set.
        """
        from utils_config_constants import get_persona_file_paths
        
        persona_paths = get_persona_file_paths(self.selected_persona_set)
        
        # Update syntax parser agent with new persona paths
        if hasattr(self.netlogo_abstract_syntax_extractor_agent, 'update_persona_path'):
            self.netlogo_abstract_syntax_extractor_agent.update_persona_path(str(persona_paths["netlogo_abstract_syntax_extractor"]))
        
        # Update interface image analyzer (2a)
        if hasattr(self.netlogo_interface_image_analyzer_agent, 'update_persona_path'):
            self.netlogo_interface_image_analyzer_agent.update_persona_path(str(persona_paths["netlogo_interface_image_analyzer"]))
        
        # Update behavior extractor agent with new persona paths
        if hasattr(self.behavior_extractor_agent, 'update_persona_path'):
            self.behavior_extractor_agent.update_persona_path(str(persona_paths["behavior_extractor"]))
        
        # Update other agents similarly
        for agent_name, agent in [
            ("lucim_environment_synthesizer", self.lucim_environment_synthesizer_agent),
            ("lucim_scenario_synthesizer", self.lucim_scenario_synthesizer_agent),
            ("plantuml_writer", self.plantuml_writer_agent),
            ("plantuml_auditor", self.plantuml_lucim_auditor_agent),
            ("plantuml_corrector", self.plantuml_lucim_corrector_agent),
            ("plantuml_final_auditor", self.plantuml_lucim_final_auditor_agent)
        ]:
            if hasattr(agent, 'update_persona_path'):
                agent.update_persona_path(str(persona_paths[agent_name]))
        # Update LUCIM rules path for agents that require it
        for agent in [
            self.lucim_environment_synthesizer_agent,
            self.lucim_scenario_synthesizer_agent,
            self.plantuml_writer_agent,
            self.plantuml_lucim_auditor_agent,
            self.plantuml_lucim_corrector_agent,
            self.plantuml_lucim_final_auditor_agent,
        ]:
            if hasattr(agent, 'update_lucim_rules_path'):
                agent.update_lucim_rules_path(str(persona_paths["lucim_rules"]))
        
        # Update IL-SYN and IL-SEM paths for syntax and behavior extractors
        if hasattr(self.netlogo_abstract_syntax_extractor_agent, "update_il_syn_inputs"):
            self.netlogo_abstract_syntax_extractor_agent.update_il_syn_inputs(
                str(persona_paths["dsl_il_syn_mapping"]),
                str(persona_paths["dsl_il_syn_description"])
            )
        
        if hasattr(self.behavior_extractor_agent, "update_il_sem_inputs"):
            self.behavior_extractor_agent.update_il_sem_inputs(
                str(persona_paths["dsl_il_sem_mapping"]),
                str(persona_paths["dsl_il_sem_description"])
            )

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
                        if self.orchestrator_logger:
                            self.orchestrator_logger.log_config_warning(f"apply_config failed on {agent_attr}: {e}; falling back to legacy setters")

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
        
        self.orchestrator_logger.log_agent_start(agent_name)
        
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
                tokens_used = result.get("tokens_used", 0)
                input_tokens = result.get("input_tokens", 0)
                output_tokens = result.get("output_tokens", 0)
                reasoning_tokens = result.get("reasoning_tokens", 0)
                self.token_usage[agent_name]["used"] = tokens_used
                
                self.orchestrator_logger.log_agent_completion(
                    agent_name, duration, tokens_used, input_tokens, output_tokens, reasoning_tokens
                )
            else:
                self.orchestrator_logger.log_agent_completion(agent_name, duration)
            
            return result
            
        except Exception as e:
            # End timing even on error
            end_time = time.time()
            duration = end_time - start_time
            self.detailed_timing[agent_name]["end"] = end_time
            self.detailed_timing[agent_name]["duration"] = duration
            self.execution_times[agent_name] = duration
            
            self.orchestrator_logger.log_agent_error(agent_name, duration, str(e))
            raise

    async def process_netlogo_file_parallel_first_stage(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run Step 1 (syntax) in parallel with Steps 2a+2b (interface analysis + behavior extraction).
        Step 1 runs independently, while Steps 2a and 2b run sequentially (2a → 2b).
        Mirrors the OpenAI Cookbook fan-out/fan-in pattern via asyncio.gather.
        """
        base_name = file_info["base_name"]
        
        # Create run directory
        tv = self.agent_configs["netlogo_abstract_syntax_extractor"].get("text_verbosity", "medium")
        reff = self.agent_configs["netlogo_abstract_syntax_extractor"].get("reasoning_effort", "medium")
        run_dir = self.fileio.create_run_directory(self.timestamp, base_name, self.model, reff, tv, self.selected_persona_set)
        
        total_orchestration_start_time = time.time()
        self.orchestrator_logger.log_agent_start(f"Parallel first stage for {base_name} (syntax + semantics)")

        code_file = file_info["code_file"]
        try:
            code_content = self.fileio.read_netlogo_code(code_file)
        except Exception as e:
            return {"error": f"Error reading code file: {e}", "results": {}}

        async def run_syntax():
            # Create agent output directory for syntax parser
            tv = None
            if isinstance(self.agent_configs, dict) and "netlogo_abstract_syntax_extractor" in self.agent_configs:
                tv = self.agent_configs["netlogo_abstract_syntax_extractor"].get("text_verbosity")
            reff = None
            if isinstance(self.agent_configs, dict) and "netlogo_abstract_syntax_extractor" in self.agent_configs:
                reff = self.agent_configs["netlogo_abstract_syntax_extractor"].get("reasoning_effort")
            run_dir = get_run_base_dir(self.timestamp, base_name, self.model, reff or "medium", tv or "medium", self.selected_persona_set)
            agent_output_dir = run_dir / "01-netlogo_abstract_syntax_extractor"
            agent_output_dir.mkdir(parents=True, exist_ok=True)
            
            return await asyncio.to_thread(
                self._execute_agent_with_tracking,
                "netlogo_abstract_syntax_extractor",
                self.netlogo_abstract_syntax_extractor_agent.parse_netlogo_code,
                code_content,
                f"{base_name}-netlogo-code.md",
                agent_output_dir
            )

        async def run_interface_analysis_and_behavior_extraction():
            """Run 2a (interface analysis) then 2b (behavior extraction) sequentially."""
            # Step 2a: Interface Image Analysis
            tv = None
            if isinstance(self.agent_configs, dict) and "netlogo_abstract_syntax_extractor" in self.agent_configs:
                tv = self.agent_configs["netlogo_abstract_syntax_extractor"].get("text_verbosity")
            reff = None
            if isinstance(self.agent_configs, dict) and "netlogo_abstract_syntax_extractor" in self.agent_configs:
                reff = self.agent_configs["netlogo_abstract_syntax_extractor"].get("reasoning_effort")
            run_dir = get_run_base_dir(self.timestamp, base_name, self.model, reff or "medium", tv or "medium", self.selected_persona_set)
            
            # Create agent output directory for 2a
            agent_2a_output_dir = run_dir / "02a-interface_image_analyzer"
            agent_2a_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Run 2a
            interface_result = await asyncio.to_thread(
                self._execute_agent_with_tracking,
                "netlogo_interface_image_analyzer",
                self.netlogo_interface_image_analyzer_agent.analyze_interface_images,
                file_info["interface_images"],
                base_name,
                str(agent_2a_output_dir)
            )
            
            # Check if 2a succeeded and extract widgets
            if isinstance(interface_result, Exception) or not interface_result.get("widgets"):
                self.logger.error(f"Interface analysis failed: {interface_result}")
                return {
                    "agent_type": "behavior_extractor",
                    "reasoning_summary": "Interface analysis failed, cannot proceed with behavior extraction",
                    "data": None,
                    "errors": ["Interface analysis failed"]
                }
            
            # Step 2b: Behavior Extraction using 2a results
            agent_2b_output_dir = run_dir / "02b-behavior_extractor"
            agent_2b_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Run 2b with interface widgets from 2a
            behavior_result = await asyncio.to_thread(
                self._execute_agent_with_tracking,
                "behavior_extractor",
                self.behavior_extractor_agent.parse_from_ilsem_and_interface_description,
                interface_result["widgets"],
                base_name,
                str(agent_2b_output_dir)
            )
            
            # Return behavior result (2b is the main output for downstream stages)
            return behavior_result

        # Fan-out: run both concurrently with an optional watchdog and heartbeat
        from utils_config_constants import HEARTBEAT_SECONDS
        import utils_config_constants as cfg
        
        async def heartbeat_task():
            try:
                while True:
                    await asyncio.sleep(HEARTBEAT_SECONDS)
                    self.orchestrator_logger.log_heartbeat(base_name)
            except asyncio.CancelledError:
                return

        hb = asyncio.create_task(heartbeat_task())
        try:
            syntax_coro = run_syntax()
            behavior_coro = run_interface_analysis_and_behavior_extraction()
            syntax_task = asyncio.create_task(syntax_coro)
            behavior_task = asyncio.create_task(behavior_coro)
            
            # If orchestrator parallel timeout is configured (not None), wrap with wait_for
            orchestrator_timeout = getattr(cfg, "ORCHESTRATOR_PARALLEL_TIMEOUT", None)
            if orchestrator_timeout is not None:
                await asyncio.wait_for(
                    asyncio.gather(syntax_task, behavior_task, return_exceptions=True),
                    timeout=orchestrator_timeout
                )
            else:
                # No watchdog timeout: wait indefinitely for both tasks
                await asyncio.gather(syntax_task, behavior_task, return_exceptions=True)
            syntax_result = await syntax_task
            behavior_result = await behavior_task
        except asyncio.TimeoutError:
            self.logger.error(f"Parallel first stage timed out after {getattr(cfg, 'ORCHESTRATOR_PARALLEL_TIMEOUT', 'N/A')}s for {base_name}")
            # Cancel any still-running task
            for t in [locals().get('syntax_task'), locals().get('behavior_task')]:
                try:
                    if t and not t.done():
                        t.cancel()
                except Exception:
                    pass
            syntax_result = syntax_result if 'syntax_result' in locals() else RuntimeError("netlogo_abstract_syntax_extractor timed out")
            behavior_result = behavior_result if 'behavior_result' in locals() else RuntimeError("behavior_extractor (2a+2b) timed out")
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
            agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 1, "netlogo_abstract_syntax_extractor")
            self.netlogo_abstract_syntax_extractor_agent.save_results(syntax_result, base_name, self.model, "1", output_dir=agent_output_dir)
            processed_results["ast"] = syntax_result

        # Handle behavior extraction result (2a+2b)
        if isinstance(behavior_result, Exception):
            self.logger.error(f"Behavior extraction (2a+2b) failed in parallel path: {behavior_result}")
            processed_results["semantics"] = {
                "agent_type": "behavior_extractor",
                "reasoning_summary": f"Behavior extraction (2a+2b) failed: {behavior_result}",
                "data": None,
                "errors": [f"Behavior extraction (2a+2b) error: {behavior_result}"]
            }
        else:
            behavior_result["agent_type"] = "behavior_extractor"
            processed_results["semantics"] = behavior_result

        # Total timing
        total_orchestration_time = time.time() - total_orchestration_start_time
        self.execution_times["total_orchestration"] = total_orchestration_time
        self.logger.info(f"Parallel first stage completed in {FormatUtils.format_duration(total_orchestration_time)}")

        # Bookkeeping only (no intermediate detailed summary in single-pass mode)
        processed_results["execution_times"] = self.execution_times.copy()
        processed_results["token_usage"] = self.token_usage.copy()
        processed_results["detailed_timing"] = self.detailed_timing.copy()
        return processed_results

    async def process_netlogo_file_sequential(self, file_info: Dict[str, Any], parallel_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process a single NetLogo file using sequential agent calls (steps 3-8).
        
        Args:
            file_info: Dictionary containing file information
            parallel_results: Results from parallel processing (steps 1-2)
            
        Returns:
            Dictionary containing all processing results
        """
        base_name = file_info["base_name"]
        
        # Create run directory
        tv = self.agent_configs["netlogo_abstract_syntax_extractor"].get("text_verbosity", "medium")
        reff = self.agent_configs["netlogo_abstract_syntax_extractor"].get("reasoning_effort", "medium")
        run_dir = self.fileio.create_run_directory(self.timestamp, base_name, self.model, reff, tv, self.selected_persona_set)
        
        # Start timing the total orchestration
        total_orchestration_start_time = time.time()
        
        self.logger.info(f"Starting sequential processing for {base_name}...")
        
        # Prepare input data
        code_file = file_info["code_file"]
        interface_images = file_info["interface_images"]
        
        # Read code for Step 1 (Syntax Parser) only; Stage 2 does not use raw code
        try:
            code_content = self.fileio.read_netlogo_code(code_file)
        except Exception as e:
            return {
                "error": f"Error reading code file: {e}",
                "results": {}
            }

        # Start with parallel results if provided
        processed_results = parallel_results.copy() if parallel_results else {}
        
        # Load common resources once for all sequential steps (no iCrash)
        try:
            lucim_dsl_content = self.fileio.load_lucim_dsl_content()
        except FileNotFoundError as e:
            self.logger.error(f"MANDATORY INPUT MISSING: {e}")
            return {
                "error": f"MANDATORY INPUT MISSING: {e}",
                "results": {}
            }
        
        # Step 3: LUCIM Environment Synthesizer Agent (using AST and State Machine from previous steps)
        if (processed_results.get("ast", {}).get("data") and 
            processed_results.get("semantics", {}).get("data")):
            
            self.logger.info(f"Step 3: Running LUCIM Environment Synthesizer agent for {base_name}...")
            
            try:
                # Debug logging for LUCIM Environment Synthesizer inputs
                self.logger.info(f"[DEBUG] LUCIM Environment Synthesizer inputs:")
                self.logger.info(f"[DEBUG] - semantics data: {type(processed_results['semantics']['data'])} - {len(str(processed_results['semantics']['data']))} chars")
                self.logger.info(f"[DEBUG] - ast data: {type(processed_results['ast']['data'])} - {len(str(processed_results['ast']['data']))} chars")
                self.logger.info(f"[DEBUG] - lucim_dsl_content: {len(lucim_dsl_content)} chars")
                
                # Create agent output directory before the call
                agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 3, "lucim_environment_synthesizer")
                
                lucim_environment_result = self._execute_agent_with_tracking(
                    "lucim_environment_synthesizer",
                    self.lucim_environment_synthesizer_agent.synthesize_lucim_environment,
                    processed_results["semantics"]["data"],
                    base_name,
                    processed_results["ast"]["data"],  # Step 01 AST data (MANDATORY)
                    lucim_dsl_content,  # LUCIM DSL content (MANDATORY)
                    output_dir=agent_output_dir
                )
                
                # Add agent type identifier
                lucim_environment_result["agent_type"] = "lucim_environment_synthesizer"
                
                # Save results using the LUCIM Environment Synthesizer agent's save method
                self.lucim_environment_synthesizer_agent.save_results(lucim_environment_result, base_name, self.model, "3", output_dir=agent_output_dir)
                
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
        else:
            self.logger.info(f"Skipping Step 3: LUCIM Environment Synthesizer agent for {base_name} (AST or State Machine failed)")
        
        # Step 4: Scenario Writer Agent
        if processed_results.get("lucim_environment_synthesizer", {}).get("data"):
            self.logger.info(f"Step 4: Running Scenario Writer agent for {base_name}...")
            
            try:
                # Create agent output directory before the call
                agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 4, "lucim_scenario_synthesizer")
                
                scenario_result = self._execute_agent_with_tracking(
                    "lucim_scenario_synthesizer",
                    self.lucim_scenario_synthesizer_agent.write_scenarios,
                    processed_results["semantics"]["data"],  # State machine from step 2
                    processed_results["lucim_environment_synthesizer"]["data"],  # LUCIM environment from step 3
                    lucim_dsl_content,  # LUCIM DSL full definition
                    base_name,  # Filename
                    output_dir=agent_output_dir
                )
                
                scenario_result["agent_type"] = "lucim_scenario_synthesizer"
                self.lucim_scenario_synthesizer_agent.save_results(scenario_result, base_name, self.model, "4", output_dir=agent_output_dir)
                processed_results["lucim_scenario_synthesizer"] = scenario_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "lucim_scenario_synthesizer",
                    "reasoning_summary": f"Scenario writing failed: {str(e)}",
                    "data": None,
                    "errors": [f"Scenario writing error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 4: Scenario Writer agent failed for {base_name}: {str(e)}")
                processed_results["lucim_scenario_synthesizer"] = error_result
        else:
            self.logger.info(f"Skipping Step 4: Scenario Writer agent for {base_name} (LUCIM mapping failed)")
        
        # Step 5: PlantUML Writer Agent
        if processed_results.get("lucim_scenario_synthesizer", {}).get("data"):
            self.logger.info(f"Step 5: Running PlantUML Writer agent for {base_name}...")
            
            try:
                # Create agent output directory before the call
                agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 5, "plantuml_writer")
                
                plantuml_result = self._execute_agent_with_tracking(
                    "plantuml_writer",
                    self.plantuml_writer_agent.generate_plantuml_diagrams,
                    processed_results["lucim_scenario_synthesizer"]["data"],  # Scenarios from step 4
                    base_name,
                    lucim_dsl_content,
                    output_dir=agent_output_dir
                )
                
                plantuml_result["agent_type"] = "plantuml_writer"
                self.plantuml_writer_agent.save_results(plantuml_result, base_name, self.model, "5", output_dir=agent_output_dir)
                processed_results["plantuml_writer"] = plantuml_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "plantuml_writer",
                    "reasoning_summary": f"PlantUML generation failed: {str(e)}",
                    "data": None,
                    "errors": [f"PlantUML generation error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 5: PlantUML Writer agent failed for {base_name}: {str(e)}")
                processed_results["plantuml_writer"] = error_result
        else:
            self.logger.info(f"Skipping Step 5: PlantUML Writer agent for {base_name} (Scenario writing failed)")
        
        # Step 6: PlantUML LUCIM Auditor Agent
        if processed_results.get("plantuml_writer", {}).get("data"):
            self.logger.info(f"Step 6: Running PlantUML LUCIM Auditor agent for {base_name}...")
            
            # Get PlantUML file path
            plantuml_file_path = self.fileio.get_plantuml_file_path(
                self.fileio.create_agent_output_directory(run_dir, 5, "plantuml_writer")
            )
            
            if plantuml_file_path and self.fileio.validate_plantuml_file(plantuml_file_path):
                try:
                    # Create agent output directory before the call
                    agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 6, "plantuml_lucim_auditor")
                    
                    audit_result = self._execute_agent_with_tracking(
                        "plantuml_lucim_auditor",
                        self.plantuml_lucim_auditor_agent.audit_plantuml_diagrams,
                        plantuml_file_path,
                        str(LUCIM_RULES_FILE),  # Path to LUCIM DSL file (not content)
                        base_name,
                        output_dir=agent_output_dir
                    )
                    
                    audit_result["agent_type"] = "plantuml_lucim_auditor"
                    self.plantuml_lucim_auditor_agent.save_results(audit_result, base_name, self.model, "6", output_dir=agent_output_dir)
                    processed_results["plantuml_lucim_auditor"] = audit_result
                    
                except Exception as e:
                    error_result = {
                        "agent_type": "plantuml_lucim_auditor",
                        "reasoning_summary": f"PlantUML audit failed: {str(e)}",
                        "data": None,
                        "errors": [f"PlantUML audit error: {str(e)}"]
                    }
                    self.logger.error(f"✗ Step 6: PlantUML LUCIM Auditor agent failed for {base_name}: {str(e)}")
                    processed_results["plantuml_lucim_auditor"] = error_result
            else:
                self.logger.error(f"✗ Step 6: PlantUML file not found or invalid for {base_name}")
                processed_results["plantuml_lucim_auditor"] = {
                    "agent_type": "plantuml_lucim_auditor",
                    "reasoning_summary": "PlantUML file not found or invalid",
                    "data": None,
                    "errors": ["PlantUML file not found or invalid"]
                }
        else:
            self.logger.info(f"Skipping Step 6: PlantUML LUCIM Auditor agent for {base_name} (PlantUML generation failed)")
        
        # Step 7: PlantUML LUCIM Corrector Agent (conditional)
        if (processed_results.get("plantuml_lucim_auditor", {}).get("data") and 
            processed_results["plantuml_lucim_auditor"].get("data", {}).get("verdict") == "non-compliant"):
            
            self.logger.info(f"Step 7: Running PlantUML LUCIM Corrector agent for {base_name}...")
            
            try:
                # Create agent output directory before the call
                agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 7, "plantuml_lucim_corrector")
                
                corrector_result = self._execute_agent_with_tracking(
                    "plantuml_lucim_corrector",
                    self.plantuml_lucim_corrector_agent.correct_plantuml_diagrams,
                    processed_results["plantuml_writer"]["data"],  # Original diagrams
                    processed_results["plantuml_lucim_auditor"]["data"],  # Audit results
                    lucim_dsl_content,
                    base_name,
                    output_dir=agent_output_dir
                )
                
                corrector_result["agent_type"] = "plantuml_lucim_corrector"
                self.plantuml_lucim_corrector_agent.save_results(corrector_result, base_name, self.model, "7", output_dir=agent_output_dir)
                processed_results["plantuml_lucim_corrector"] = corrector_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "plantuml_lucim_corrector",
                    "reasoning_summary": f"PlantUML correction failed: {str(e)}",
                    "data": None,
                    "errors": [f"PlantUML correction error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 7: PlantUML LUCIM Corrector agent failed for {base_name}: {str(e)}")
                processed_results["plantuml_lucim_corrector"] = error_result
        else:
            self.logger.info(f"Skipping Step 7: PlantUML LUCIM Corrector agent for {base_name} (diagrams already compliant)")
        
        # Step 8: PlantUML LUCIM Final Auditor Agent (conditional)
        if processed_results.get("plantuml_lucim_corrector", {}).get("data"):
            self.logger.info(f"Step 8: Running PlantUML LUCIM Final Auditor agent for {base_name}...")
            
            # Get corrected PlantUML file path
            corrector_output_dir = self.fileio.create_agent_output_directory(run_dir, 7, "plantuml_lucim_corrector")
            corrected_plantuml_file_path = self.fileio.get_plantuml_file_path(corrector_output_dir)
            
            if corrected_plantuml_file_path and self.fileio.validate_plantuml_file(corrected_plantuml_file_path):
                try:
                    # Create agent output directory before the call
                    agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 8, "plantuml_lucim_final_auditor")
                    
                    final_audit_result = self._execute_agent_with_tracking(
                        "plantuml_lucim_final_auditor",
                        self.plantuml_lucim_final_auditor_agent.audit_plantuml_diagrams,
                        corrected_plantuml_file_path,
                        str(LUCIM_RULES_FILE),  # Path to LUCIM DSL file (not content)
                        base_name,
                        8,  # step parameter for final audit
                        output_dir=agent_output_dir
                    )
                    
                    final_audit_result["agent_type"] = "plantuml_lucim_final_auditor"
                    self.plantuml_lucim_final_auditor_agent.save_results(final_audit_result, base_name, self.model, "8", output_dir=agent_output_dir)
                    processed_results["plantuml_lucim_final_auditor"] = final_audit_result
                    
                except Exception as e:
                    error_result = {
                        "agent_type": "plantuml_lucim_final_auditor",
                        "reasoning_summary": f"Final audit failed: {str(e)}",
                        "data": None,
                        "errors": [f"Final audit error: {str(e)}"]
                    }
                    self.logger.error(f"✗ Step 8: PlantUML LUCIM Final Auditor agent failed for {base_name}: {str(e)}")
                    processed_results["plantuml_lucim_final_auditor"] = error_result
            else:
                self.logger.error(f"✗ Step 8: Corrected PlantUML file not found or invalid for {base_name}")
                processed_results["plantuml_lucim_final_auditor"] = {
                    "agent_type": "plantuml_lucim_final_auditor",
                    "reasoning_summary": "Corrected PlantUML file not found or invalid",
                    "data": None,
                    "errors": ["Corrected PlantUML file not found or invalid"]
                }
        else:
            self.logger.info(f"Skipping Step 8: PlantUML LUCIM Final Auditor agent for {base_name} (corrector was skipped or not required)")
        
        # Calculate total orchestration time
        total_orchestration_time = time.time() - total_orchestration_start_time
        self.execution_times["total_orchestration"] = total_orchestration_time
        
        self.logger.info(f"Completed processing for {base_name}")
        self.logger.info(f"Total orchestration time: {FormatUtils.format_duration(total_orchestration_time)}")
        
        # Add timing and token usage information to the results
        processed_results["execution_times"] = self.execution_times.copy()
        processed_results["token_usage"] = self.token_usage.copy()
        processed_results["detailed_timing"] = self.detailed_timing.copy()
        
        return processed_results

    def _extract_compliance_from_results(self, processed_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract compliance status from processed results.
        
        Args:
            processed_results: Dictionary containing all agent results
            
        Returns:
            Dictionary with compliance status, source, and details
        """
        # Try to get verdict from final auditor (step 8) first
        final_auditor_result = processed_results.get("plantuml_lucim_final_auditor")
        if final_auditor_result and isinstance(final_auditor_result, dict):
            data = final_auditor_result.get("data")
            if isinstance(data, dict) and "verdict" in data:
                verdict = data.get("verdict")
                if verdict == "compliant":
                    return {
                        "status": "VERIFIED",
                        "source": "final_auditor",
                        "details": {"verdict": verdict, "step": 8}
                    }
                elif verdict == "non-compliant":
                    return {
                        "status": "NON-COMPLIANT", 
                        "source": "final_auditor",
                        "details": {"verdict": verdict, "step": 8}
                    }
            # Check for errors in final auditor - treat as non-compliant
            errors = final_auditor_result.get("errors", [])
            if errors:
                return {
                    "status": "NON-COMPLIANT",
                    "source": "final_auditor",
                    "details": {"reason": "auditor_errors", "errors": errors, "step": 8}
                }
        
        # Fallback to initial auditor (step 6)
        initial_auditor_result = processed_results.get("plantuml_lucim_auditor")
        if initial_auditor_result and isinstance(initial_auditor_result, dict):
            data = initial_auditor_result.get("data")
            if isinstance(data, dict) and "verdict" in data:
                verdict = data.get("verdict")
                if verdict == "compliant":
                    return {
                        "status": "VERIFIED",
                        "source": "initial_auditor", 
                        "details": {"verdict": verdict, "step": 6}
                    }
                elif verdict == "non-compliant":
                    return {
                        "status": "NON-COMPLIANT",
                        "source": "initial_auditor",
                        "details": {"verdict": verdict, "step": 6}
                    }
            # Check for errors in initial auditor - treat as non-compliant
            errors = initial_auditor_result.get("errors", [])
            if errors:
                return {
                    "status": "NON-COMPLIANT",
                    "source": "initial_auditor",
                    "details": {"reason": "auditor_errors", "errors": errors, "step": 6}
                }
        
        # No verdict found and no errors - this should be rare
        return {
            "status": "UNKNOWN",
            "source": "none",
            "details": {"reason": "no_auditor_verdict_found"}
        }

    async def run(self, base_name: str) -> Dict[str, Any]:
        """
        Run the orchestrator for a given base name with simplified processing.
        
        Args:
            base_name: Base name of the NetLogo files to process
            
        Returns:
            Dictionary containing all processing results
        """
        # Set up logging for this orchestration run, including reasoning and text verbosity
        tv = self.agent_configs["netlogo_abstract_syntax_extractor"].get("text_verbosity", "medium")
        reff = self.agent_configs["netlogo_abstract_syntax_extractor"].get("reasoning_effort", "medium")
        rsum = self.agent_configs["netlogo_abstract_syntax_extractor"].get("reasoning_summary", "auto")

        self.logger = setup_orchestration_logger(
            base_name,
            self.model,
            self.timestamp,
            reasoning_effort=reff,
            text_verbosity=tv,
            persona_set=self.selected_persona_set or self.persona_set,
        )
        
        # Initialize orchestrator logger
        self.orchestrator_logger = OrchestratorLogger(self.logger)
        
        # Also mirror stdout/stderr into the orchestrator log file
        attach_stdio_to_logger(self.logger)
        
        # Log persona set selection
        self.logger.info(f"Using persona set: {self.selected_persona_set}")
        
        # Single parameter bundle line including text verbosity (only here)
        bundle_line = format_parameter_bundle(
            model=self.model,
            base_name=base_name,
            reasoning_effort=reff,
            reasoning_summary=rsum,
            text_verbosity=tv
        )
        self.logger.info(bundle_line)
        
        self.logger.info(f"Starting simplified processing for base name: {base_name}")
        
        # Find files matching the base name
        files = self.fileio.find_netlogo_files(base_name)
        
        if not files:
            return {
                "error": f"No files found for base name '{base_name}'",
                "results": {}
            }
        
        results = {}
        
        # Process each file with parallel-first-stage then sequential
        for file_info in files:
            base_name = file_info["base_name"]
            
            # Run parallel first stage (steps 1+2)
            parallel_result = await self.process_netlogo_file_parallel_first_stage(file_info)
            
            # Continue with sequential processing (steps 3-8) using parallel results
            if isinstance(parallel_result, dict):
                # Pass parallel results to sequential processing
                sequential_result = await self.process_netlogo_file_sequential(file_info, parallel_result)
                # Merge results conservatively; keep earlier entries from parallel stage
                for k, v in sequential_result.items():
                    if k not in parallel_result:
                        parallel_result[k] = v
                
                results[base_name] = parallel_result
            else:
                results[base_name] = parallel_result
            
            # Print status using orchestrator logger
            final_result = results[base_name]
            self.orchestrator_logger.log_workflow_status(base_name, final_result)
            self.orchestrator_logger.log_error_details(final_result)
        
        self.logger.info(f"Completed processing for {base_name}")
        
        # Print comprehensive orchestration summary
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"ORCHESTRATION SUMMARY FOR: {base_name}")
        self.logger.info(f"{'='*60}")
        
        # Log execution timing
        self.orchestrator_logger.log_execution_timing(self.execution_times)
        
        # Get final result for summary
        final_result = results.get(base_name, {})
        
        # Log detailed agent status
        self.orchestrator_logger.log_detailed_agent_status(final_result)
        
        # Log output files
        self.orchestrator_logger.log_output_files(base_name, self.timestamp, self.model, final_result)
        
        # Log pipeline completion
        successful_agents = sum(1 for key, value in final_result.items() 
                               if isinstance(value, dict) and value.get("data") is not None)
        total_agents = len([k for k in final_result.keys() if k not in ["execution_times", "token_usage", "detailed_timing"]])
        self.orchestrator_logger.log_pipeline_completion(successful_agents, total_agents)
        
        # Log compliance status
        final_compliance = self._extract_compliance_from_results(final_result)
        self.orchestrator_logger.log_compliance_status(final_compliance)
        
        self.logger.info(f"{'='*60}")
        
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


async def main():
    """Main execution function - simplified version."""
    # Ensure input directories point to experimentation single source of truth when running directly
    try:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        os.environ.setdefault("INPUT_PERSONA_DIR", str(repo_root / "experimentation" / "input" / "input-persona"))
        os.environ.setdefault("INPUT_NETLOGO_DIR", str(repo_root / "experimentation" / "input" / "input-netlogo"))
        os.environ.setdefault("INPUT_VALID_EXAMPLES_DIR", str(repo_root / "experimentation" / "input" / "input-valid-examples"))
    except Exception:
        pass

    # Initialize UI utilities
    ui = OrchestratorUI()
    
    # Validate OpenAI API key
    if not ui.validate_openai_key():
        return
    
    # Get available base names
    base_names = ui.get_available_base_names()
    if not base_names:
        return
    
    # Model selection
    selected_models = ui.select_models()
    if not selected_models:
        return
    
    # Base name selection
    selected_base_names = ui.select_base_names(base_names)
    if not selected_base_names:
        return
    
    # Timeout preset selection
    timeout_seconds, timeout_preset = ui.select_timeout_preset()
    
    # Reasoning effort selection
    reasoning_levels = ui.select_reasoning_effort()
    if not reasoning_levels:
        return
    
    # Text verbosity selection
    selected_verbosity_levels = ui.select_text_verbosity()
    
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
                # Create orchestrator with reasoning configuration
                orchestrator = NetLogoOrchestratorSimplified(model_name=model)
                
                # Update reasoning configuration for all agents
                orchestrator.update_reasoning_config(reasoning_config["effort"], reasoning_config["summary"])

                # Run for each selected verbosity level
                for verbosity in selected_verbosity_levels:
                    current_combination += 1
                    ui.print_combination_header(current_combination, total_combinations)

                    orchestrator.update_text_config(verbosity)
                    # Print a single parameter bundle line including text verbosity
                    ui.print_parameter_bundle(
                        model=model,
                        base_name=base_name,
                        reasoning_effort=reasoning_config["effort"],
                        reasoning_summary=reasoning_config["summary"],
                        text_verbosity=verbosity,
                    )
                    
                    results = await orchestrator.run(base_name)
                    
                    # Create unique key for results including verbosity
                    reasoning_suffix = f"{reasoning_config['effort']}-{reasoning_config['summary']}"
                    result_key = f"{base_name}_{model}_{reasoning_suffix}_{verbosity}"
                    all_results[result_key] = results
    
    # Calculate total execution time
    total_execution_time = time.time() - total_execution_start_time
    
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
    
    # Print final summary with enhanced audit metrics
    ui.print_final_summary(
        total_execution_time, total_files, total_agents, 
        total_successful_agents, overall_success_rate, all_results
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
