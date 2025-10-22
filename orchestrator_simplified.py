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
from typing import Dict, Any, List

from agent_1_syntax_parser import NetLogoSyntaxParserAgent
from agent_2_semantics_parser import NetLogoSemanticsParserAgent
from agent_3_messir_concepts_mapper import NetLogoMessirMapperAgent
from agent_4_scenario_writer import NetLogoScenarioWriterAgent
from agent_5_plantuml_writer import NetLogoPlantUMLWriterAgent
from agent_6_plantuml_auditor import NetLogoPlantUMLMessirAuditorAgent
from agent_7_plantuml_corrector import NetLogoPlantUMLMessirCorrectorAgent

from utils_config_constants import (
    INPUT_NETLOGO_DIR, INPUT_ICRASH_DIR, OUTPUT_DIR, INPUT_PERSONA_DIR,
    AGENT_CONFIGS, AVAILABLE_MODELS, DEFAULT_MODEL, ensure_directories,
    validate_agent_response, MESSIR_RULES_FILE
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
    
    def __init__(self, model_name: str = DEFAULT_MODEL, persona_set: str = None):
        """
        Initialize the NetLogo Orchestrator.
        
        Args:
            model_name: AI model to use for processing
            persona_set: Optional persona set to use (bypasses interactive selection)
        """
        self.model = model_name
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
            "syntax_parser": 0,
            "semantics_parser": 0,
            "messir_mapper": 0,
            "scenario_writer": 0,
            "plantuml_writer": 0,
            "plantuml_messir_auditor": 0,
            "plantuml_messir_corrector": 0,
            "plantuml_messir_final_auditor": 0
        }
        
        # Token usage tracking
        self.token_usage = {
            "syntax_parser": {"used": 0},
            "semantics_parser": {"used": 0},
            "messir_mapper": {"used": 0},
            "scenario_writer": {"used": 0},
            "plantuml_writer": {"used": 0},
            "plantuml_messir_auditor": {"used": 0},
            "plantuml_messir_corrector": {"used": 0},
            "plantuml_messir_final_auditor": {"used": 0}
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
        
        # Store agent configurations for reasoning level updates
        self.selected_persona_set = None
        self.agent_configs = AGENT_CONFIGS.copy()
        
        # Initialize agents
        self.syntax_parser_agent = NetLogoSyntaxParserAgent(model_name, self.timestamp)
        # Pass IL-SYN file absolute paths to syntax parser agent
        try:
            base_dir = pathlib.Path(__file__).resolve().parent
            ilsyn_mapping_path = (base_dir / "input-persona" / "persona-v1" / "DSL_IL_SYN-mapping.md").resolve()
            ilsyn_description_path = (base_dir / "input-persona" / "persona-v1" / "DSL_IL_SYN-description.md").resolve()
            if hasattr(self.syntax_parser_agent, "update_il_syn_inputs"):
                self.syntax_parser_agent.update_il_syn_inputs(str(ilsyn_mapping_path), str(ilsyn_description_path))
            else:
                # Backward compatibility: set attributes directly if method unavailable
                self.syntax_parser_agent.il_syn_mapping_path = str(ilsyn_mapping_path)
                self.syntax_parser_agent.il_syn_description_path = str(ilsyn_description_path)
            if self.orchestrator_logger:
                self.orchestrator_logger.log_config_success("Configured IL-SYN reference paths for syntax parser")
        except Exception as e:
            if self.orchestrator_logger:
                self.orchestrator_logger.log_config_warning(f"Unable to set IL-SYN paths for syntax parser: {e}")
        
        self.semantics_parser_agent = NetLogoSemanticsParserAgent(model_name, self.timestamp)
        # Configure IL-SEM inputs for semantics agent (absolute paths)
        il_sem_mapping = INPUT_PERSONA_DIR / "persona-v1" / "DSL_IL_SEM-mapping.md"
        il_sem_description = INPUT_PERSONA_DIR / "persona-v1" / "DSL_IL_SEM-description.md"
        if hasattr(self.semantics_parser_agent, "update_il_sem_inputs"):
            self.semantics_parser_agent.update_il_sem_inputs(str(il_sem_mapping), str(il_sem_description))
        
        self.messir_mapper_agent = NetLogoMessirMapperAgent(model_name, self.timestamp)
        self.scenario_writer_agent = NetLogoScenarioWriterAgent(model_name, self.timestamp)
        self.plantuml_writer_agent = NetLogoPlantUMLWriterAgent(model_name, self.timestamp)
        self.plantuml_messir_auditor_agent = NetLogoPlantUMLMessirAuditorAgent(model_name, self.timestamp)
        self.plantuml_messir_corrector_agent = NetLogoPlantUMLMessirCorrectorAgent(model_name, self.timestamp)
        self.plantuml_messir_final_auditor_agent = NetLogoPlantUMLMessirAuditorAgent(model_name, self.timestamp)
        
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
        if hasattr(self.syntax_parser_agent, 'update_persona_path'):
            self.syntax_parser_agent.update_persona_path(str(persona_paths["syntax_parser"]))
        
        # Update semantics parser agent with new persona paths
        if hasattr(self.semantics_parser_agent, 'update_persona_path'):
            self.semantics_parser_agent.update_persona_path(str(persona_paths["semantics_parser"]))
        
        # Update other agents similarly
        for agent_name, agent in [
            ("messir_mapper", self.messir_mapper_agent),
            ("scenario_writer", self.scenario_writer_agent),
            ("plantuml_writer", self.plantuml_writer_agent),
            ("plantuml_auditor", self.plantuml_messir_auditor_agent),
            ("plantuml_corrector", self.plantuml_messir_corrector_agent),
            ("plantuml_final_auditor", self.plantuml_messir_final_auditor_agent)
        ]:
            if hasattr(agent, 'update_persona_path'):
                agent.update_persona_path(str(persona_paths[agent_name]))
        
        # Update IL-SYN and IL-SEM paths for syntax and semantics parsers
        if hasattr(self.syntax_parser_agent, "update_il_syn_inputs"):
            self.syntax_parser_agent.update_il_syn_inputs(
                str(persona_paths["dsl_il_syn_mapping"]),
                str(persona_paths["dsl_il_syn_description"])
            )
        
        if hasattr(self.semantics_parser_agent, "update_il_sem_inputs"):
            self.semantics_parser_agent.update_il_sem_inputs(
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
            ("syntax_parser_agent", True),
            ("semantics_parser_agent", True),
            ("messir_mapper_agent", True),
            ("scenario_writer_agent", True),
            ("plantuml_writer_agent", True),
            ("plantuml_messir_auditor_agent", True),
            ("plantuml_messir_corrector_agent", True),
            ("plantuml_messir_final_auditor_agent", True),
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
        Run Step 1 (syntax) and an independent semantics derivation in parallel.
        (No AST-based re-run; Stage 2 uses only IL-SEM + UI images.)
        Mirrors the OpenAI Cookbook fan-out/fan-in pattern via asyncio.gather.
        """
        base_name = file_info["base_name"]
        
        # Create run directory
        tv = self.agent_configs["syntax_parser"].get("text_verbosity", "medium")
        reff = self.agent_configs["syntax_parser"].get("reasoning_effort", "medium")
        run_dir = self.fileio.create_run_directory(self.timestamp, base_name, self.model, reff, tv)
        
        total_orchestration_start_time = time.time()
        self.orchestrator_logger.log_agent_start(f"Parallel first stage for {base_name} (syntax + semantics)")

        code_file = file_info["code_file"]
        try:
            code_content = self.fileio.read_netlogo_code(code_file)
        except Exception as e:
            return {"error": f"Error reading code file: {e}", "results": {}}

        async def run_syntax():
            return await asyncio.to_thread(
                self._execute_agent_with_tracking,
                "syntax_parser",
                self.syntax_parser_agent.parse_netlogo_code,
                code_content,
                f"{base_name}-netlogo-code.md"
            )

        async def run_semantics_direct():
            return await asyncio.to_thread(
                self._execute_agent_with_tracking,
                "semantics_parser",
                self.semantics_parser_agent.parse_from_ilsem_and_ui,
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
                    self.orchestrator_logger.log_heartbeat(base_name)
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
            syntax_result = syntax_result if 'syntax_result' in locals() else RuntimeError("syntax_parser timed out")
            semantics_result_direct = semantics_result_direct if 'semantics_result_direct' in locals() else RuntimeError("semantics_parser (direct) timed out")
        finally:
            hb.cancel()

        processed_results: Dict[str, Any] = {}

        # Handle syntax result
        if isinstance(syntax_result, Exception):
            self.logger.error(f"Syntax Parser failed in parallel path: {syntax_result}")
            processed_results["ast"] = {
                "agent_type": "syntax_parser",
                "reasoning_summary": f"Syntax Parser agent failed: {syntax_result}",
                "data": None,
                "errors": [f"Syntax Parser agent error: {syntax_result}"]
            }
        else:
            syntax_result["agent_type"] = "syntax_parser"
            agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 1, "syntax_parser")
            self.syntax_parser_agent.save_results(syntax_result, base_name, self.model, "1", output_dir=agent_output_dir)
            processed_results["ast"] = syntax_result

        # Handle semantics direct result
        if isinstance(semantics_result_direct, Exception):
            self.logger.error(f"Semantics Parser (direct) failed in parallel path: {semantics_result_direct}")
            processed_results["semantics"] = {
                "agent_type": "semantics_parser",
                "reasoning_summary": f"Semantics Parser direct failed: {semantics_result_direct}",
                "data": None,
                "errors": [f"Semantics Parser direct error: {semantics_result_direct}"]
            }
        else:
            semantics_result = semantics_result_direct
            semantics_result["agent_type"] = "semantics_parser"
            agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 2, "semantics_parser")
            self.semantics_parser_agent.save_results(semantics_result, base_name, self.model, "2", output_dir=agent_output_dir)
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
        tv = self.agent_configs["syntax_parser"].get("text_verbosity", "medium")
        reff = self.agent_configs["syntax_parser"].get("reasoning_effort", "medium")
        run_dir = self.fileio.create_run_directory(self.timestamp, base_name, self.model, reff, tv)
        
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
        
        # Load common resources once for all sequential steps
        icrash_contents_list = self.fileio.load_icrash_contents()
        # Convert iCrash list to string for scenario writer
        icrash_contents = "\n\n".join([f"File: {item.get('filename', 'unknown')}\n{item.get('content', '')}" for item in icrash_contents_list])
        try:
            messir_dsl_content = self.fileio.load_messir_dsl_content()
        except FileNotFoundError as e:
            self.logger.error(f"MANDATORY INPUT MISSING: {e}")
            return {
                "error": f"MANDATORY INPUT MISSING: {e}",
                "results": {}
            }
        
        # Step 3: Messir Mapper Agent (using AST and State Machine from previous steps)
        if (processed_results.get("ast", {}).get("data") and 
            processed_results.get("semantics", {}).get("data")):
            
            self.logger.info(f"Step 3: Running Messir Mapper agent for {base_name}...")
            
            try:
                messir_result = self._execute_agent_with_tracking(
                    "messir_mapper",
                    self.messir_mapper_agent.map_to_messir_concepts,
                    processed_results["semantics"]["data"],
                    base_name,
                    processed_results["ast"]["data"],  # Step 01 AST data (MANDATORY)
                    messir_dsl_content,  # MUCIM DSL content (MANDATORY)
                    icrash_contents_list  # iCrash contents as list (for messir_mapper)
                )
                
                # Add agent type identifier
                messir_result["agent_type"] = "messir_mapper"
                
                # Save results using the Messir mapper agent's save method
                agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 3, "messir_mapper")
                self.messir_mapper_agent.save_results(messir_result, base_name, self.model, "3", output_dir=agent_output_dir)
                
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
        else:
            self.logger.info(f"Skipping Step 3: Messir Mapper agent for {base_name} (AST or State Machine failed)")
        
        # Step 4: Scenario Writer Agent
        if processed_results.get("messir_mapper", {}).get("data"):
            self.logger.info(f"Step 4: Running Scenario Writer agent for {base_name}...")
            
            try:
                scenario_result = self._execute_agent_with_tracking(
                    "scenario_writer",
                    self.scenario_writer_agent.write_scenarios,
                    processed_results["semantics"]["data"],  # State machine from step 2
                    processed_results["messir_mapper"]["data"],  # Messir concepts from step 3
                    messir_dsl_content,  # MUCIM DSL full definition
                    icrash_contents,  # iCrash references
                    base_name  # Filename
                )
                
                scenario_result["agent_type"] = "scenario_writer"
                agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 4, "scenario_writer")
                self.scenario_writer_agent.save_results(scenario_result, base_name, self.model, "4", output_dir=agent_output_dir)
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
        else:
            self.logger.info(f"Skipping Step 4: Scenario Writer agent for {base_name} (Messir mapping failed)")
        
        # Step 5: PlantUML Writer Agent
        if processed_results.get("scenario_writer", {}).get("data"):
            self.logger.info(f"Step 5: Running PlantUML Writer agent for {base_name}...")
            
            try:
                plantuml_result = self._execute_agent_with_tracking(
                    "plantuml_writer",
                    self.plantuml_writer_agent.generate_plantuml_diagrams,
                    processed_results["scenario_writer"]["data"],  # Scenarios from step 4
                    base_name,
                    messir_dsl_content
                )
                
                plantuml_result["agent_type"] = "plantuml_writer"
                agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 5, "plantuml_writer")
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
        
        # Step 6: PlantUML Messir Auditor Agent
        if processed_results.get("plantuml_writer", {}).get("data"):
            self.logger.info(f"Step 6: Running PlantUML Messir Auditor agent for {base_name}...")
            
            # Get PlantUML file path
            plantuml_file_path = self.fileio.get_plantuml_file_path(
                self.fileio.create_agent_output_directory(run_dir, 5, "plantuml_writer")
            )
            
            if plantuml_file_path and self.fileio.validate_plantuml_file(plantuml_file_path):
                try:
                    audit_result = self._execute_agent_with_tracking(
                        "plantuml_messir_auditor",
                        self.plantuml_messir_auditor_agent.audit_plantuml_diagrams,
                        plantuml_file_path,
                        str(MESSIR_RULES_FILE),  # Path to MUCIM DSL file (not content)
                        base_name
                    )
                    
                    audit_result["agent_type"] = "plantuml_messir_auditor"
                    agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 6, "plantuml_messir_auditor")
                    self.plantuml_messir_auditor_agent.save_results(audit_result, base_name, self.model, "6", output_dir=agent_output_dir)
                    processed_results["plantuml_messir_auditor"] = audit_result
                    
                except Exception as e:
                    error_result = {
                        "agent_type": "plantuml_messir_auditor",
                        "reasoning_summary": f"PlantUML audit failed: {str(e)}",
                        "data": None,
                        "errors": [f"PlantUML audit error: {str(e)}"]
                    }
                    self.logger.error(f"✗ Step 6: PlantUML Messir Auditor agent failed for {base_name}: {str(e)}")
                    processed_results["plantuml_messir_auditor"] = error_result
            else:
                self.logger.error(f"✗ Step 6: PlantUML file not found or invalid for {base_name}")
                processed_results["plantuml_messir_auditor"] = {
                    "agent_type": "plantuml_messir_auditor",
                    "reasoning_summary": "PlantUML file not found or invalid",
                    "data": None,
                    "errors": ["PlantUML file not found or invalid"]
                }
        else:
            self.logger.info(f"Skipping Step 6: PlantUML Messir Auditor agent for {base_name} (PlantUML generation failed)")
        
        # Step 7: PlantUML Messir Corrector Agent (conditional)
        if (processed_results.get("plantuml_messir_auditor", {}).get("data") and 
            processed_results["plantuml_messir_auditor"].get("data", {}).get("verdict") == "non-compliant"):
            
            self.logger.info(f"Step 7: Running PlantUML Messir Corrector agent for {base_name}...")
            
            try:
                corrector_result = self._execute_agent_with_tracking(
                    "plantuml_messir_corrector",
                    self.plantuml_messir_corrector_agent.correct_plantuml_diagrams,
                    processed_results["plantuml_writer"]["data"],  # Original diagrams
                    processed_results["plantuml_messir_auditor"]["data"],  # Audit results
                    messir_dsl_content,
                    base_name
                )
                
                corrector_result["agent_type"] = "plantuml_messir_corrector"
                agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 7, "plantuml_messir_corrector")
                self.plantuml_messir_corrector_agent.save_results(corrector_result, base_name, self.model, "7", output_dir=agent_output_dir)
                processed_results["plantuml_messir_corrector"] = corrector_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "plantuml_messir_corrector",
                    "reasoning_summary": f"PlantUML correction failed: {str(e)}",
                    "data": None,
                    "errors": [f"PlantUML correction error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 7: PlantUML Messir Corrector agent failed for {base_name}: {str(e)}")
                processed_results["plantuml_messir_corrector"] = error_result
        else:
            self.logger.info(f"Skipping Step 7: PlantUML Messir Corrector agent for {base_name} (diagrams already compliant)")
        
        # Step 8: PlantUML Messir Final Auditor Agent (conditional)
        if processed_results.get("plantuml_messir_corrector", {}).get("data"):
            self.logger.info(f"Step 8: Running PlantUML Messir Final Auditor agent for {base_name}...")
            
            # Get corrected PlantUML file path
            corrector_output_dir = self.fileio.create_agent_output_directory(run_dir, 7, "plantuml_messir_corrector")
            corrected_plantuml_file_path = self.fileio.get_plantuml_file_path(corrector_output_dir)
            
            if corrected_plantuml_file_path and self.fileio.validate_plantuml_file(corrected_plantuml_file_path):
                try:
                    final_audit_result = self._execute_agent_with_tracking(
                        "plantuml_messir_final_auditor",
                        self.plantuml_messir_final_auditor_agent.audit_plantuml_diagrams,
                        corrected_plantuml_file_path,
                        str(MESSIR_RULES_FILE),  # Path to MUCIM DSL file (not content)
                        base_name
                    )
                    
                    final_audit_result["agent_type"] = "plantuml_messir_final_auditor"
                    agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 8, "plantuml_messir_final_auditor")
                    self.plantuml_messir_final_auditor_agent.save_results(final_audit_result, base_name, self.model, "8", output_dir=agent_output_dir)
                    processed_results["plantuml_messir_final_auditor"] = final_audit_result
                    
                except Exception as e:
                    error_result = {
                        "agent_type": "plantuml_messir_final_auditor",
                        "reasoning_summary": f"Final audit failed: {str(e)}",
                        "data": None,
                        "errors": [f"Final audit error: {str(e)}"]
                    }
                    self.logger.error(f"✗ Step 8: PlantUML Messir Final Auditor agent failed for {base_name}: {str(e)}")
                    processed_results["plantuml_messir_final_auditor"] = error_result
            else:
                self.logger.error(f"✗ Step 8: Corrected PlantUML file not found or invalid for {base_name}")
                processed_results["plantuml_messir_final_auditor"] = {
                    "agent_type": "plantuml_messir_final_auditor",
                    "reasoning_summary": "Corrected PlantUML file not found or invalid",
                    "data": None,
                    "errors": ["Corrected PlantUML file not found or invalid"]
                }
        else:
            self.logger.info(f"Skipping Step 8: PlantUML Messir Final Auditor agent for {base_name} (corrector was skipped or not required)")
        
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

    async def run(self, base_name: str) -> Dict[str, Any]:
        """
        Run the orchestrator for a given base name with simplified processing.
        
        Args:
            base_name: Base name of the NetLogo files to process
            
        Returns:
            Dictionary containing all processing results
        """
        # Set up logging for this orchestration run, including reasoning and text verbosity
        tv = self.agent_configs["syntax_parser"].get("text_verbosity", "medium")
        reff = self.agent_configs["syntax_parser"].get("reasoning_effort", "medium")
        rsum = self.agent_configs["syntax_parser"].get("reasoning_summary", "auto")

        self.logger = setup_orchestration_logger(
            base_name,
            self.model,
            self.timestamp,
            reasoning_effort=reff,
            text_verbosity=tv,
            persona_set=self.selected_persona_set or "persona-v1",
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
        final_compliance = {
            "status": "UNKNOWN",
            "source": "none",
            "details": {}
        }
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
    
    # Print final summary with enhanced audit metrics
    ui.print_final_summary(
        total_execution_time, total_files, total_agents, 
        total_successful_agents, overall_success_rate, all_results
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
