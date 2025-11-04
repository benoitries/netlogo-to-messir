#!/usr/bin/env python3
"""
NetLogo Orchestrator Agent - Persona V3 Version
Orchestrates the processing of NetLogo files using the persona-v3-limited-agents pipeline.
This orchestrator uses LUCIM Environment Synthesizer as the first step with NetLogo source code only.
"""

import sys
import os
import asyncio
import json
import datetime
import pathlib
import time
import logging
from typing import Dict, Any, List, Optional

# Fail fast on unsupported Python versions (some dependencies require >= 3.10)
if sys.version_info < (3, 10):
    raise RuntimeError(
        f"Python 3.10+ is required to run this orchestrator. Detected: {sys.version.split()[0]}"
    )

from agent_lucim_operation_generator import LucimOperationModelGeneratorAgent
from agent_lucim_scenario_generator import LUCIMScenarioGeneratorAgent
from agent_lucim_plantuml_diagram_generator import LUCIMPlantUMLDiagramGeneratorAgent
from agent_lucim_plantuml_diagram_auditor import LUCIMPlantUMLDiagramAuditorAgent
 

from utils_config_constants import (
    INPUT_NETLOGO_DIR, OUTPUT_DIR, INPUT_PERSONA_DIR,
    AGENT_CONFIGS, DEFAULT_MODEL, ensure_directories,
    LUCIM_RULES_FILE
)
from utils_logging import setup_orchestration_logger, format_parameter_bundle, attach_stdio_to_logger
from utils_orchestrator_logging import OrchestratorLogger
from utils_orchestrator_ui import OrchestratorUI
from utils_orchestrator_fileio import OrchestratorFileIO
from utils_format import FormatUtils

# Ensure all directories exist
ensure_directories()


class NetLogoOrchestratorPersonaV3:
    """Persona V3 orchestrator for processing NetLogo files using persona-v3-limited-agents pipeline.
    
    This orchestrator uses LUCIM Environment Synthesizer as the first step, receiving only NetLogo
    source code (no AST or behavior data). It follows a 6-stage pipeline: LUCIM Env Synth → 
    LUCIM Scenario Synth → PlantUML Writer → PlantUML Auditor → PlantUML Corrector (if needed) → 
    PlantUML Final Auditor (if needed).
    """
    
    def __init__(self, model_name: str = DEFAULT_MODEL):
        """
        Initialize the NetLogo Orchestrator for Persona V3.
        
        Args:
            model_name: AI model to use for processing
        """
        self.model = model_name
        # Hardcode persona-v3-limited-agents - no selection needed
        self.persona_set = "persona-v3-limited-agents"
        # Format: YYYYMMDD_HHMM for better readability
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        
        # Initialize logger (will be set up properly when processing starts)
        self.logger = None
        self.orchestrator_logger = None
        
        # Initialize utilities
        self.ui = OrchestratorUI()
        self.fileio = OrchestratorFileIO()
        
        # Timing tracking (only for agents used in v3 pipeline)
        self.execution_times = {
            "total_orchestration": 0,
            "lucim_environment_synthesizer": 0,
            "lucim_scenario_synthesizer": 0,
            "plantuml_writer": 0,
            "plantuml_lucim_auditor": 0,
            "plantuml_lucim_final_auditor": 0
        }
        
        # Token usage tracking (only for agents used in v3 pipeline)
        self.token_usage = {
            "lucim_environment_synthesizer": {"used": 0},
            "lucim_scenario_synthesizer": {"used": 0},
            "plantuml_writer": {"used": 0},
            "plantuml_lucim_auditor": {"used": 0},
            "plantuml_lucim_final_auditor": {"used": 0}
        }
        
        # Detailed timing tracking with start/end timestamps (only for agents used in v3 pipeline)
        self.detailed_timing = {
            "lucim_environment_synthesizer": {"start": 0, "end": 0, "duration": 0},
            "lucim_scenario_synthesizer": {"start": 0, "end": 0, "duration": 0},
            "plantuml_writer": {"start": 0, "end": 0, "duration": 0},
            "plantuml_lucim_auditor": {"start": 0, "end": 0, "duration": 0},
            "plantuml_lucim_final_auditor": {"start": 0, "end": 0, "duration": 0}
        }
        
        # Store agent configurations for reasoning level updates
        self.selected_persona_set = "persona-v3-limited-agents"
        self.agent_configs = AGENT_CONFIGS.copy()
        
        # Initialize only agents used in v3 pipeline (agents 1, 2a, 2b are not used)
        self.lucim_operation_model_generator_agent = LucimOperationModelGeneratorAgent(model_name, self.timestamp)
        self.lucim_scenario_generator_agent = LUCIMScenarioGeneratorAgent(model_name, self.timestamp)
        self.plantuml_writer_agent = LUCIMPlantUMLDiagramGeneratorAgent(model_name, self.timestamp)
        self.plantuml_lucim_auditor_agent = LUCIMPlantUMLDiagramAuditorAgent(model_name, self.timestamp)
        self.plantuml_lucim_final_auditor_agent = LUCIMPlantUMLDiagramAuditorAgent(model_name, self.timestamp)
        
        # Initialize persona set selection after agents are created
        self.initialize_persona_set()

    def initialize_persona_set(self):
        """
        Initialize persona set for v3 - hardcoded to persona-v3-limited-agents.
        Updates agent configurations with the persona set.
        """
        # Hardcoded persona set - no UI selection needed
        self.selected_persona_set = "persona-v3-limited-agents"
        
        # Update persona file paths for all agents
        self._update_agent_persona_paths()
        
        # Log the selection (will be logged later when logger is available)
        print(f"✅ Initialized persona set: {self.selected_persona_set}")

    def _update_agent_persona_paths(self):
        """
        Update persona file paths for all agents based on persona-v3-limited-agents set.
        Uses v3-specific persona file naming conventions.
        """
        from utils_config_constants import INPUT_PERSONA_DIR
        
        persona_dir = INPUT_PERSONA_DIR / self.selected_persona_set
        
        # Define v3-specific persona file paths (different naming from standard personas)
        v3_persona_paths = {
            "lucim_operation_model_generator": persona_dir / "PSN_LUCIM_Operation_Model_Generator.md",
            "lucim_scenario_generator": persona_dir / "PSN_LUCIM_Scenario_Generator.md",
            "plantuml_diagram_generator": persona_dir / "PSN_LUCIM_PlantUML_Diagram_Generator.md",
            "plantuml_diagram_auditor": persona_dir / "PSN_LUCIM_PlantUML_Diagram_Auditor.md",
            "plantuml_corrector": persona_dir / "PSN_PlantUML_LUCIM_Corrector.md",
            "lucim_rules": persona_dir / "DSL_Target_LUCIM-full-definition-for-compliance.md",
            "netlogo_lucim_mapping": persona_dir / "RULES_MAPPING_NETLOGO_TO_OPERATION_MODEL.md",
        }
        
        # Store mapping file path for later use
        self.netlogo_lucim_mapping_path = v3_persona_paths["netlogo_lucim_mapping"]
        
        # Update persona paths for agents used in v3
        if hasattr(self.lucim_operation_model_generator_agent, 'update_persona_path'):
            self.lucim_operation_model_generator_agent.update_persona_path(str(v3_persona_paths["lucim_environment_synthesizer"]))
        
        if hasattr(self.lucim_scenario_generator_agent, 'update_persona_path'):
            self.lucim_scenario_generator_agent.update_persona_path(str(v3_persona_paths["lucim_scenario_synthesizer"]))
        
        if hasattr(self.plantuml_writer_agent, 'update_persona_path'):
            self.plantuml_writer_agent.update_persona_path(str(v3_persona_paths["plantuml_writer"]))
        
        if hasattr(self.plantuml_lucim_auditor_agent, 'update_persona_path'):
            self.plantuml_lucim_auditor_agent.update_persona_path(str(v3_persona_paths["plantuml_auditor"]))
        
        if hasattr(self.plantuml_lucim_final_auditor_agent, 'update_persona_path'):
            self.plantuml_lucim_final_auditor_agent.update_persona_path(str(v3_persona_paths["plantuml_final_auditor"]))
        
        # Update LUCIM rules path for agents that require it
        for agent in [
            self.lucim_operation_model_generator_agent,
            self.lucim_scenario_generator_agent,
            self.plantuml_writer_agent,
            self.plantuml_lucim_auditor_agent,
            self.plantuml_lucim_final_auditor_agent,
        ]:
            if hasattr(agent, 'update_lucim_rules_path'):
                agent.update_lucim_rules_path(str(v3_persona_paths["lucim_rules"]))
    
    def _load_netlogo_lucim_mapping(self) -> str:
        """
        Load NetLogo to LUCIM mapping file content from persona-v3-limited-agents.
        
        Returns:
            Content of DSL_NetLogo_LUCIM_Operation_Model_Mapping.md as string
        
        Raises:
            FileNotFoundError: If the mapping file does not exist
        """
        if not hasattr(self, 'netlogo_lucim_mapping_path'):
            from utils_config_constants import INPUT_PERSONA_DIR
            persona_dir = INPUT_PERSONA_DIR / self.selected_persona_set
            self.netlogo_lucim_mapping_path = persona_dir / "RULES_MAPPING_NETLOGO_TO_OPERATION_MODEL.md"
        
        if not self.netlogo_lucim_mapping_path.exists():
            raise FileNotFoundError(
                f"MANDATORY INPUT MISSING: NetLogo to LUCIM mapping file not found: {self.netlogo_lucim_mapping_path}"
            )
        
        return self.netlogo_lucim_mapping_path.read_text(encoding="utf-8")

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

        # List of (agent attr, text_support_flag) - only agents used in v3 pipeline
        agent_list = [
            ("lucim_operation_model_generator_agent", True),
            ("lucim_scenario_generator_agent", True),
            ("plantuml_writer_agent", True),
            ("plantuml_lucim_auditor_agent", True),

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

    async def process_netlogo_file_v3(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single NetLogo file using the v3 pipeline (steps 1-6).
        Step 1: LUCIM Environment Synthesizer (from NetLogo source code only)
        Step 2: LUCIM Scenario Synthesizer
        Step 3: PlantUML Writer
        Step 4: PlantUML Auditor
        Step 5: PlantUML Corrector (conditional)
        Step 6: PlantUML Final Auditor (conditional)
        
        Args:
            file_info: Dictionary containing file information
            
        Returns:
            Dictionary containing all processing results
        """
        base_name = file_info["base_name"]
        
        # Create run directory
        tv = self.agent_configs["lucim_environment_synthesizer"].get("text_verbosity", "medium")
        reff = self.agent_configs["lucim_environment_synthesizer"].get("reasoning_effort", "medium")
        run_dir = self.fileio.create_run_directory(self.timestamp, base_name, self.model, reff, tv, self.selected_persona_set, version="v3-no-adk")
        
        # Start timing the total orchestration
        total_orchestration_start_time = time.time()
        
        self.logger.info(f"Starting v3 pipeline processing for {base_name}...")
        
        # Prepare input data
        code_file = file_info["code_file"]
        
        # Read NetLogo source code
        try:
            code_content = self.fileio.read_netlogo_code(code_file)
        except Exception as e:
            return {
                "error": f"Error reading code file: {e}",
                "results": {}
            }

        processed_results: Dict[str, Any] = {}
        
        # Load common resources once for all steps
        try:
            lucim_dsl_content = self.fileio.load_lucim_dsl_content()
        except FileNotFoundError as e:
            self.logger.error(f"MANDATORY INPUT MISSING: {e}")
            return {
                "error": f"MANDATORY INPUT MISSING: {e}",
                "results": {}
            }
        
        try:
            netlogo_lucim_mapping_content = self._load_netlogo_lucim_mapping()
        except FileNotFoundError as e:
            self.logger.error(f"MANDATORY INPUT MISSING: {e}")
            return {
                "error": f"MANDATORY INPUT MISSING: {e}",
                "results": {}
            }
        
        # Step 1: LUCIM Environment Synthesizer Agent (from NetLogo source code only)
        self.logger.info(f"Step 1: Running LUCIM Environment Synthesizer agent for {base_name}...")
        
        try:
            # Debug logging for LUCIM Environment Synthesizer inputs
            self.logger.info(f"[DEBUG] LUCIM Environment Synthesizer inputs:")
            self.logger.info(f"[DEBUG] - netlogo_source_code: {len(code_content)} chars")
            self.logger.info(f"[DEBUG] - lucim_dsl_content: {len(lucim_dsl_content)} chars")
            self.logger.info(f"[DEBUG] - netlogo_lucim_mapping_content: {len(netlogo_lucim_mapping_content)} chars")
            
            # Create agent output directory before the call
            agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 1, "lucim_operation_model_generator")
            
            lucim_operation_model_result = self._execute_agent_with_tracking(
                "lucim_operation_model_generator",
                self.lucim_operation_model_generator_agent.synthesize_lucim_operation_from_source_code,
                code_content,  # NetLogo source code (MANDATORY)
                lucim_dsl_content,  # LUCIM DSL content (MANDATORY)
                netlogo_lucim_mapping_content,  # NetLogo to LUCIM mapping (MANDATORY)
                output_dir=agent_output_dir
            )
            
            # Add agent type identifier
            lucim_operation_model_result["agent_type"] = "lucim_operation_model_generator"
            
            # Save results using the LUCIM Environment Synthesizer agent's save method
            self.lucim_operation_model_generator_agent.save_results(lucim_operation_model_result, base_name, self.model, "1", output_dir=agent_output_dir)
            
            processed_results["lucim_operation_model_generator"] = lucim_operation_model_result
            
        except Exception as e:
            error_result = {
                "agent_type": "lucim_environment_synthesizer",
                "reasoning_summary": f"LUCIM Environment synthesis failed: {str(e)}",
                "data": None,
                "errors": [f"LUCIM Environment synthesis error: {str(e)}"]
            }
            self.logger.error(f"✗ Step 1: LUCIM Environment Synthesizer agent failed for {base_name}: {str(e)}")
            processed_results["lucim_environment_synthesizer"] = error_result
        
        # Step 2: LUCIM Scenario Synthesizer Agent
        if processed_results.get("lucim_environment_synthesizer", {}).get("data"):
            self.logger.info(f"Step 2: Running LUCIM Scenario Synthesizer agent for {base_name}...")
            
            try:
                # Create agent output directory before the call
                agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 2, "lucim_scenario_synthesizer")
                
                scenario_result = self._execute_agent_with_tracking(
                    "lucim_scenario_synthesizer",
                    self.lucim_scenario_generator_agent.write_scenarios,
                    processed_results["lucim_environment_synthesizer"]["data"],  # LUCIM environment from step 1
                    lucim_dsl_content,  # LUCIM DSL full definition
                    output_dir=agent_output_dir
                )
                
                scenario_result["agent_type"] = "lucim_scenario_synthesizer"
                self.lucim_scenario_generator_agent.save_results(scenario_result, base_name, self.model, "2", output_dir=agent_output_dir)
                processed_results["lucim_scenario_synthesizer"] = scenario_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "lucim_scenario_synthesizer",
                    "reasoning_summary": f"Scenario writing failed: {str(e)}",
                    "data": None,
                    "errors": [f"Scenario writing error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 2: LUCIM Scenario Synthesizer agent failed for {base_name}: {str(e)}")
                processed_results["lucim_scenario_synthesizer"] = error_result
        else:
            self.logger.info(f"Skipping Step 2: LUCIM Scenario Synthesizer agent for {base_name} (LUCIM Environment synthesis failed)")
        
        # Step 3: PlantUML Writer Agent
        if processed_results.get("lucim_scenario_synthesizer", {}).get("data"):
            self.logger.info(f"Step 3: Running PlantUML Writer agent for {base_name}...")
            
            try:
                # Create agent output directory before the call
                agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 3, "plantuml_writer")
                
                plantuml_result = self._execute_agent_with_tracking(
                    "plantuml_writer",
                    self.plantuml_writer_agent.generate_plantuml_diagrams,
                    processed_results["lucim_scenario_synthesizer"]["data"],  # Scenarios from step 2
                    output_dir=agent_output_dir
                )
                
                plantuml_result["agent_type"] = "plantuml_writer"
                self.plantuml_writer_agent.save_results(plantuml_result, base_name, self.model, "3", output_dir=agent_output_dir)
                processed_results["plantuml_writer"] = plantuml_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "plantuml_writer",
                    "reasoning_summary": f"PlantUML generation failed: {str(e)}",
                    "data": None,
                    "errors": [f"PlantUML generation error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 3: PlantUML Writer agent failed for {base_name}: {str(e)}")
                processed_results["plantuml_writer"] = error_result
        else:
            self.logger.info(f"Skipping Step 3: PlantUML Writer agent for {base_name} (Scenario writing failed)")
        
        # Step 4: PlantUML LUCIM Auditor Agent
        if processed_results.get("plantuml_writer", {}).get("data"):
            self.logger.info(f"Step 4: Running PlantUML LUCIM Auditor agent for {base_name}...")
            
            # Get PlantUML file path
            plantuml_file_path = self.fileio.get_plantuml_file_path(
                self.fileio.create_agent_output_directory(run_dir, 3, "plantuml_writer")
            )
            
            if plantuml_file_path and self.fileio.validate_plantuml_file(plantuml_file_path):
                try:
                    # Create agent output directory before the call
                    agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 4, "plantuml_lucim_auditor")
                    
                    audit_result = self._execute_agent_with_tracking(
                        "plantuml_lucim_auditor",
                        self.plantuml_lucim_auditor_agent.audit_plantuml_diagrams,
                        plantuml_file_path,
                        str(LUCIM_RULES_FILE),  # Path to LUCIM DSL file (not content)
                        output_dir=agent_output_dir
                    )
                    
                    audit_result["agent_type"] = "plantuml_lucim_auditor"
                    self.plantuml_lucim_auditor_agent.save_results(audit_result, base_name, self.model, "4", output_dir=agent_output_dir)
                    processed_results["plantuml_lucim_auditor"] = audit_result
                    
                except Exception as e:
                    error_result = {
                        "agent_type": "plantuml_lucim_auditor",
                        "reasoning_summary": f"PlantUML audit failed: {str(e)}",
                        "data": None,
                        "errors": [f"PlantUML audit error: {str(e)}"]
                    }
                    self.logger.error(f"✗ Step 4: PlantUML LUCIM Auditor agent failed for {base_name}: {str(e)}")
                    processed_results["plantuml_lucim_auditor"] = error_result
            else:
                self.logger.error(f"✗ Step 4: PlantUML file not found or invalid for {base_name}")
                processed_results["plantuml_lucim_auditor"] = {
                    "agent_type": "plantuml_lucim_auditor",
                    "reasoning_summary": "PlantUML file not found or invalid",
                    "data": None,
                    "errors": ["PlantUML file not found or invalid"]
                }
        else:
            self.logger.info(f"Skipping Step 4: PlantUML LUCIM Auditor agent for {base_name} (PlantUML generation failed)")
        
        # Step 5: PlantUML LUCIM Corrector Agent (conditional)
        if (processed_results.get("plantuml_lucim_auditor", {}).get("data") and 
            processed_results["plantuml_lucim_auditor"].get("data", {}).get("verdict") == "non-compliant"):
            
            self.logger.info(f"Step 5: Running PlantUML LUCIM Corrector agent for {base_name}...")
            
            try:
                # Create agent output directory before the call
                agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 5, "plantuml_lucim_corrector")
                
                corrector_result = self._execute_agent_with_tracking(
                    "plantuml_lucim_corrector",
                    self.plantuml_lucim_corrector_agent.correct_plantuml_diagrams,
                    processed_results["plantuml_writer"]["data"],  # Original diagrams
                    processed_results["plantuml_lucim_auditor"]["data"],  # Audit results
                    lucim_dsl_content,
                    output_dir=agent_output_dir
                )
                
                corrector_result["agent_type"] = "plantuml_lucim_corrector"
                self.plantuml_lucim_corrector_agent.save_results(corrector_result, base_name, self.model, "5", output_dir=agent_output_dir)
                processed_results["plantuml_lucim_corrector"] = corrector_result
                
            except Exception as e:
                error_result = {
                    "agent_type": "plantuml_lucim_corrector",
                    "reasoning_summary": f"PlantUML correction failed: {str(e)}",
                    "data": None,
                    "errors": [f"PlantUML correction error: {str(e)}"]
                }
                self.logger.error(f"✗ Step 5: PlantUML LUCIM Corrector agent failed for {base_name}: {str(e)}")
                processed_results["plantuml_lucim_corrector"] = error_result
        else:
            self.logger.info(f"Skipping Step 5: PlantUML LUCIM Corrector agent for {base_name} (diagrams already compliant)")
        
        # Step 6: PlantUML LUCIM Final Auditor Agent (conditional)
        # Check if corrector was executed (even if it failed, we may have a corrected diagram file)
        if "plantuml_lucim_corrector" in processed_results:
            # Get corrected PlantUML file path
            corrector_output_dir = self.fileio.create_agent_output_directory(run_dir, 5, "plantuml_lucim_corrector")
            corrected_plantuml_file_path = self.fileio.get_plantuml_file_path(corrector_output_dir)
            
            if corrected_plantuml_file_path and self.fileio.validate_plantuml_file(corrected_plantuml_file_path):
                self.logger.info(f"Step 6: Running PlantUML LUCIM Final Auditor agent for {base_name}...")
                try:
                    # Create agent output directory before the call
                    agent_output_dir = self.fileio.create_agent_output_directory(run_dir, 6, "plantuml_lucim_final_auditor")
                    
                    final_audit_result = self._execute_agent_with_tracking(
                        "plantuml_lucim_final_auditor",
                        self.plantuml_lucim_final_auditor_agent.audit_plantuml_diagrams,
                        corrected_plantuml_file_path,
                        str(LUCIM_RULES_FILE),  # Path to LUCIM DSL file (not content)
                        6,  # step parameter for final audit
                        output_dir=agent_output_dir
                    )
                    
                    final_audit_result["agent_type"] = "plantuml_lucim_final_auditor"
                    self.plantuml_lucim_final_auditor_agent.save_results(final_audit_result, base_name, self.model, "6", output_dir=agent_output_dir)
                    processed_results["plantuml_lucim_final_auditor"] = final_audit_result
                    
                except Exception as e:
                    error_result = {
                        "agent_type": "plantuml_lucim_final_auditor",
                        "reasoning_summary": f"Final audit failed: {str(e)}",
                        "data": None,
                        "errors": [f"Final audit error: {str(e)}"]
                    }
                    self.logger.error(f"✗ Step 6: PlantUML LUCIM Final Auditor agent failed for {base_name}: {str(e)}")
                    processed_results["plantuml_lucim_final_auditor"] = error_result
            else:
                # Corrector was executed but no valid corrected PlantUML file was generated
                corrector_has_data = processed_results.get("plantuml_lucim_corrector", {}).get("data") is not None
                if corrector_has_data:
                    self.logger.error(f"✗ Step 6: Corrected PlantUML file not found or invalid for {base_name} (corrector executed but file missing)")
                    processed_results["plantuml_lucim_final_auditor"] = {
                        "agent_type": "plantuml_lucim_final_auditor",
                        "reasoning_summary": "Corrected PlantUML file not found or invalid (corrector executed but file missing)",
                        "data": None,
                        "errors": ["Corrected PlantUML file not found or invalid"]
                    }
                else:
                    self.logger.info(f"Skipping Step 6: PlantUML LUCIM Final Auditor agent for {base_name} (corrector failed and no corrected diagram available)")
        else:
            self.logger.info(f"Skipping Step 6: PlantUML LUCIM Final Auditor agent for {base_name} (corrector was skipped or not required)")
        
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
        # Try to get verdict from final auditor (step 6) first
        final_auditor_result = processed_results.get("plantuml_lucim_final_auditor")
        if final_auditor_result and isinstance(final_auditor_result, dict):
            data = final_auditor_result.get("data")
            if isinstance(data, dict) and "verdict" in data:
                verdict = data.get("verdict")
                if verdict == "compliant":
                    return {
                        "status": "VERIFIED",
                        "source": "final_auditor",
                        "details": {"verdict": verdict, "step": 6}
                    }
                elif verdict == "non-compliant":
                    return {
                        "status": "NON-COMPLIANT", 
                        "source": "final_auditor",
                        "details": {"verdict": verdict, "step": 6}
                    }
            # Check for errors in final auditor - treat as non-compliant
            errors = final_auditor_result.get("errors", [])
            if errors:
                return {
                    "status": "NON-COMPLIANT",
                    "source": "final_auditor",
                    "details": {"reason": "auditor_errors", "errors": errors, "step": 6}
                }
        
        # Fallback to initial auditor (step 4)
        initial_auditor_result = processed_results.get("plantuml_lucim_auditor")
        if initial_auditor_result and isinstance(initial_auditor_result, dict):
            data = initial_auditor_result.get("data")
            if isinstance(data, dict) and "verdict" in data:
                verdict = data.get("verdict")
                if verdict == "compliant":
                    return {
                        "status": "VERIFIED",
                        "source": "initial_auditor", 
                        "details": {"verdict": verdict, "step": 4}
                    }
                elif verdict == "non-compliant":
                    return {
                        "status": "NON-COMPLIANT",
                        "source": "initial_auditor",
                        "details": {"verdict": verdict, "step": 4}
                    }
            # Check for errors in initial auditor - treat as non-compliant
            errors = initial_auditor_result.get("errors", [])
            if errors:
                return {
                    "status": "NON-COMPLIANT",
                    "source": "initial_auditor",
                    "details": {"reason": "auditor_errors", "errors": errors, "step": 4}
                }
        
        # No verdict found and no errors - this should be rare
        return {
            "status": "UNKNOWN",
            "source": "none",
            "details": {"reason": "no_auditor_verdict_found"}
        }

    def _log_workflow_status_v3(self, base_name: str, results: Dict[str, Any]) -> None:
        """Log workflow status for v3 pipeline (steps 1-6 only)."""
        # Determine success status for each step in v3 pipeline
        lucim_environment_success = results.get("lucim_environment_synthesizer", {}).get("data") is not None
        lucim_scenario_synthesizer_success = results.get("lucim_scenario_synthesizer", {}).get("data") is not None
        plantuml_writer_success = results.get("plantuml_writer", {}).get("data") is not None
        plantuml_lucim_auditor_success = results.get("plantuml_lucim_auditor", {}).get("data") is not None
        plantuml_lucim_corrector_success = results.get("plantuml_lucim_corrector", {}).get("data") is not None
        plantuml_lucim_final_auditor_success = results.get("plantuml_lucim_final_auditor", {}).get("data") is not None
        
        # Check if optional steps were executed
        plantuml_lucim_corrector_executed = "plantuml_lucim_corrector" in results
        plantuml_lucim_final_auditor_executed = "plantuml_lucim_final_auditor" in results
        
        self.logger.info(f"{base_name} results:")
        self.logger.info(f"  Step 1 - LUCIM Environment Synthesizer: {'✓' if lucim_environment_success else '✗'}")
        self.logger.info(f"  Step 2 - LUCIM Scenario Synthesizer: {'✓' if lucim_scenario_synthesizer_success else '✗'}")
        self.logger.info(f"  Step 3 - PlantUML Writer: {'✓' if plantuml_writer_success else '✗'}")
        self.logger.info(f"  Step 4 - PlantUML LUCIM Auditor: {'✓' if plantuml_lucim_auditor_success else '✗'}")
        
        if plantuml_lucim_corrector_executed:
            self.logger.info(f"  Step 5 - PlantUML LUCIM Corrector: {'✓' if plantuml_lucim_corrector_success else '✗'}")
        else:
            self.logger.info(f"  Step 5 - PlantUML LUCIM Corrector: SKIPPED (diagrams already compliant)")
        
        if plantuml_lucim_final_auditor_executed:
            self.logger.info(f"  Step 6 - PlantUML LUCIM Final Auditor: {'✓' if plantuml_lucim_final_auditor_success else '✗'}")
        else:
            self.logger.info(f"  Step 6 - PlantUML LUCIM Final Auditor: SKIPPED (corrector was skipped or not required)")

    def _log_detailed_agent_status_v3(self, results: Dict[str, Any]) -> None:
        """Log detailed agent status for v3 pipeline (steps 1-6 only)."""
        self.logger.info(f"\n🔍 DETAILED AGENT STATUS:")
        
        # Determine status for each agent in v3 pipeline
        lucim_environment_success = results.get("lucim_environment_synthesizer", {}).get("data") is not None
        lucim_scenario_synthesizer_success = results.get("lucim_scenario_synthesizer", {}).get("data") is not None
        plantuml_writer_success = results.get("plantuml_writer", {}).get("data") is not None
        plantuml_lucim_auditor_success = results.get("plantuml_lucim_auditor", {}).get("data") is not None
        plantuml_lucim_corrector_success = results.get("plantuml_lucim_corrector", {}).get("data") is not None
        plantuml_lucim_final_auditor_success = results.get("plantuml_lucim_final_auditor", {}).get("data") is not None
        
        # Check if optional steps were executed
        plantuml_lucim_corrector_executed = "plantuml_lucim_corrector" in results
        plantuml_lucim_final_auditor_executed = "plantuml_lucim_final_auditor" in results
        
        self.logger.info(f"   Step 1 - LUCIM Environment Synthesizer Agent: {'✓ SUCCESS' if lucim_environment_success else '✗ FAILED'}")
        self.logger.info(f"   Step 2 - LUCIM Scenario Synthesizer Agent: {'✓ SUCCESS' if lucim_scenario_synthesizer_success else '✗ FAILED'}")
        self.logger.info(f"   Step 3 - PlantUML Writer Agent: {'✓ SUCCESS' if plantuml_writer_success else '✗ FAILED'}")
        self.logger.info(f"   Step 4 - PlantUML LUCIM Auditor Agent: {'✓ SUCCESS' if plantuml_lucim_auditor_success else '✗ FAILED'}")
        
        if not plantuml_lucim_corrector_executed:
            self.logger.info(f"   Step 5 - PlantUML LUCIM Corrector Agent: ⏭️  SKIPPED (diagrams already compliant)")
        else:
            self.logger.info(f"   Step 5 - PlantUML LUCIM Corrector Agent: {'✓ SUCCESS' if plantuml_lucim_corrector_success else '✗ FAILED'}")
        
        if not plantuml_lucim_final_auditor_executed:
            self.logger.info(f"   Step 6 - PlantUML LUCIM Final Auditor Agent: ⏭️  SKIPPED (corrector was skipped or not required)")
        else:
            self.logger.info(f"   Step 6 - PlantUML LUCIM Final Auditor Agent: {'✓ SUCCESS' if plantuml_lucim_final_auditor_success else '✗ FAILED'}")

    async def run(self, base_name: str) -> Dict[str, Any]:
        """
        Run the orchestrator for a given base name with v3 pipeline processing.
        
        Args:
            base_name: Base name of the NetLogo files to process
            
        Returns:
            Dictionary containing all processing results
        """
        # Set up logging for this orchestration run, including reasoning and text verbosity
        tv = self.agent_configs["lucim_environment_synthesizer"].get("text_verbosity", "medium")
        reff = self.agent_configs["lucim_environment_synthesizer"].get("reasoning_effort", "medium")
        rsum = self.agent_configs["lucim_environment_synthesizer"].get("reasoning_summary", "auto")

        self.logger = setup_orchestration_logger(
            base_name,
            self.model,
            self.timestamp,
            reasoning_effort=reff,
            text_verbosity=tv,
            persona_set=self.selected_persona_set or self.persona_set,
            version="v3-no-adk"
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
        
        self.logger.info(f"Starting v3 pipeline processing for base name: {base_name}")
        
        # Find files matching the base name
        files = self.fileio.find_netlogo_files(base_name)
        
        if not files:
            return {
                "error": f"No files found for base name '{base_name}'",
                "results": {}
            }
        
        results = {}
        
        # Process each file with v3 pipeline (sequential steps 1-6)
        for file_info in files:
            base_name = file_info["base_name"]
            
            # Run v3 pipeline (steps 1-6)
            v3_result = await self.process_netlogo_file_v3(file_info)
            results[base_name] = v3_result
            
            # Print status using orchestrator logger (v3 pipeline specific)
            final_result = results[base_name]
            self._log_workflow_status_v3(base_name, final_result)
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
        
        # Log detailed agent status (v3 pipeline specific)
        self._log_detailed_agent_status_v3(final_result)
        
        # Log output files
        self.orchestrator_logger.log_output_files(base_name, self.timestamp, self.model, final_result)
        
        # Log pipeline completion
        successful_agents = sum(1 for key, value in final_result.items() 
                               if isinstance(value, dict) and value.get("data") is not None)
        total_agents = len([k for k in final_result.keys() if k not in ["execution_times", "token_usage", "detailed_timing"]])
        
        # Extract compliance status before logging pipeline completion
        final_compliance = self._extract_compliance_from_results(final_result)
        self.orchestrator_logger.log_pipeline_completion(successful_agents, total_agents, final_compliance)
        
        # Log compliance status
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
    """Main execution function - persona v3 version."""
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
                orchestrator = NetLogoOrchestratorPersonaV3(model_name=model)
                
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
        "lucim_environment_synthesizer", "lucim_scenario_synthesizer",
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
