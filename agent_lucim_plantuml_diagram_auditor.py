#!/usr/bin/env python3
"""
NetLogo PlantUML Auditor Agent using OpenAI models
Audits PlantUML sequence diagrams for LUCIM UCI compliance using OpenAI models.
"""

import os
import json
import datetime
import pathlib
import tiktoken
from typing import Dict, Any, Optional
from google.adk.agents import LlmAgent
from openai import OpenAI
from utils_response_dump import serialize_response_to_dict, write_all_output_files, write_input_instructions_before_api
from utils_openai_client import create_and_wait, get_output_text, get_reasoning_summary, format_prompt_for_responses_api
from utils_audit_core import extract_audit_core

from utils_config_constants import (
    PERSONA_LUCIM_PLANTUML_DIAGRAM_AUDITOR, OUTPUT_DIR,
    get_reasoning_config, DEFAULT_MODEL, AGENT_TIMEOUTS, RULES_LUCIM_PLANTUML_DIAGRAM)
from utils_path import sanitize_agent_name

# Configuration
PERSONA_FILE = PERSONA_LUCIM_PLANTUML_DIAGRAM_AUDITOR
WRITE_FILES = True



class LUCIMPlantUMLDiagramAuditorAgent(LlmAgent):
    model: str = DEFAULT_MODEL
    timestamp: str = ""
    name: str = "NetLogo PlantUML Auditor"
    
    client: OpenAI = None
    reasoning_effort: str = "medium"
    reasoning_summary: str = "auto"
    text_verbosity: str = "medium"
    persona_path: str = ""
    persona_text: str = ""
    rules_path: str = ""
    rules_text: str = ""
    
    def __init__(self, model_name: str = DEFAULT_MODEL, external_timestamp: str = None):
        super().__init__(
            name=f"netlogo_lucim_plantuml_diagram_auditor_agent_{sanitize_agent_name(model_name)}",
            description="PlantUML auditor agent for LUCIM UCI compliance checking"
        )
        self.model = model_name
        
        # Use external timestamp if provided, otherwise generate new one
        if external_timestamp:
            self.timestamp = external_timestamp
        else:
            # Format: YYYYMMDD_HHMM for better readability
            self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        
        # Configure OpenAI client with automatic provider detection based on model
        from utils_openai_client import get_openai_client_for_model
        self.client = get_openai_client_for_model(self.model)
        # Initialize persona and rules from defaults; orchestrator can override
        try:
            self.persona_path = str(PERSONA_FILE)
            self.persona_text = pathlib.Path(self.persona_path).read_text(encoding="utf-8")
        except Exception:
            self.persona_text = ""
        try:
            self.rules_path = str(RULES_LUCIM_PLANTUML_DIAGRAM)
            self.rules_text = pathlib.Path(self.rules_path).read_text(encoding="utf-8")
        except Exception:
            self.rules_text = ""
        
    
    def update_reasoning_config(self, reasoning_effort: str, reasoning_summary: str):
        """
        Update reasoning configuration for this agent.
        
        Args:
            reasoning_effort: "low", "medium", or "high"
            reasoning_summary: "auto" or "manual"
        """
        self.reasoning_effort = reasoning_effort
        self.reasoning_summary = reasoning_summary

    def update_text_config(self, text_verbosity: str):
        """Update text verbosity configuration for this agent."""
        self.text_verbosity = text_verbosity
    
    def apply_config(self, config: Dict[str, Any]) -> None:
        """Apply a unified configuration bundle to this agent.

        Supported keys (optional): "reasoning_effort", "reasoning_summary", "text_verbosity".
        Unknown keys are ignored.
        """
        if not isinstance(config, dict):
            return
        for key in ("reasoning_effort", "reasoning_summary", "text_verbosity"):
            value = config.get(key)
            if value is not None:
                setattr(self, key, value)
    
    def update_persona_path(self, persona_path: str) -> None:
        if not persona_path:
            return
        self.persona_path = persona_path
        try:
            self.persona_text = pathlib.Path(persona_path).read_text(encoding="utf-8")
        except Exception as e:
            print(f"[WARNING] Failed to load persona file: {persona_path} ({e})")
            self.persona_text = ""
    
    
    
    def count_input_tokens(self, instructions: str, input_text: str) -> int:
        """
        Count input tokens exactly using tiktoken for the given model.
        
        Args:
            instructions: The persona/instructions text
            input_text: The actual input text (filename + code)
            
        Returns:
            Exact token count for the input
        """
        try:
            # Get the appropriate encoding for the model
            try:
                encoding = tiktoken.encoding_for_model(self.model)
            except Exception:
                encoding = tiktoken.get_encoding("cl100k_base")
            
            # Combine instructions and input text (this is what gets sent to the model)
            full_input = f"{instructions}\n\n{input_text}"
            
            # Count tokens
            token_count = len(encoding.encode(full_input))
            return token_count
            
        except Exception as e:
            print(f"[WARNING] Failed to count input tokens with tiktoken: {e}")
            # Fallback to character-based estimation
            full_input = f"{instructions}\n\n{input_text}"
            estimated_tokens = len(full_input) // 4  # Rough estimate: 4 chars per token
            return estimated_tokens
        
    def audit_plantuml_diagrams(self, plantuml_diagram_file_path: str, lucim_scenario: Dict[str, Any] | str, output_dir: pathlib.Path | str, step: int = 6) -> Dict[str, Any]:
        """
        Audit PlantUML sequence diagrams for LUCIM UCI compliance using the PlantUML Auditor persona.

        Args:
            plantuml_diagram_file_path: Path to the standalone .puml file from Step 5 (mandatory)
            lucim_scenario: LUCIM scenario data to include in the audit context (mandatory, matches generator context)
            output_dir: Output directory for results (mandatory)
            step: Step number for task file selection (default: 6)

        Returns:
            Dictionary containing reasoning, non-compliant rules, and any errors
        """
        # Resolve base output directory (mandatory parameter)
        if isinstance(output_dir, str):
            base_output_dir = pathlib.Path(output_dir)
        else:
            base_output_dir = output_dir
        
        # Ensure output directory exists before writing files
        try:
            base_output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"[WARNING] Failed to create output directory {base_output_dir}: {e}")
        
        # Build canonical instructions: persona + rules (required for audit)
        instructions = f"{self.persona_text}\n\n{self.rules_text}".strip()

        # Read .puml file content
        try:
            puml_content = pathlib.Path(plantuml_diagram_file_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            return {
                "reasoning_summary": f"Error: .puml file not found at {plantuml_diagram_file_path}",
                "data": None,
                "errors": [f"Required .puml file not found: {plantuml_diagram_file_path}"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        except Exception as e:
            return {
                "reasoning_summary": f"Error reading .puml file: {e}",
                "data": None,
                "errors": [f"Failed to read .puml file {plantuml_diagram_file_path}: {e}"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        
        # Validate mandatory lucim_scenario parameter
        if lucim_scenario is None:
            return {
                "reasoning_summary": "Error: lucim_scenario is mandatory but not provided",
                "data": None,
                "errors": ["lucim_scenario parameter is required for PlantUML diagram audit"],
                "verdict": "non-compliant",
                "non-compliant-rules": [],
                "coverage": {"total_rules_in_dsl": "0", "evaluated": [], "not_applicable": [], "missing_evaluation": []},
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        
        # Build input text matching generator structure: LUCIM-SCENARIO (mandatory) + PLANTUML-DIAGRAM
        # Normalize lucim_scenario (mandatory parameter, same normalization as generator)
        normalized_input = lucim_scenario
        # Unwrap top-level {"data": ...}
        if isinstance(normalized_input, dict) and "data" in normalized_input:
            normalized_input = normalized_input["data"]
        # If list, take the first item (typical scenario)
        first_item = None
        if isinstance(normalized_input, list) and len(normalized_input) > 0:
            first_item = normalized_input[0]
        elif isinstance(normalized_input, dict):
            first_item = normalized_input
        # Derive scenario block
        scenario_block = None
        if isinstance(first_item, dict):
            if isinstance(first_item.get("scenario"), dict):
                scenario_block = first_item.get("scenario")
            elif all(k in first_item for k in ("name", "description", "messages")):
                scenario_block = first_item
        
        # Always include LUCIM-SCENARIO (mandatory, before PLANTUML-DIAGRAM to match generator order)
        # Use raw text copy without json.dumps or markdown fences (same as generator)
        try:
            scenario_data = {"scenario": scenario_block} if scenario_block is not None else normalized_input
            if isinstance(scenario_data, str):
                scenario_text = scenario_data
            else:
                scenario_text = str(scenario_data)
            input_text = f"""
<LUCIM-SCENARIO>
{scenario_text}
</LUCIM-SCENARIO>
"""
        except Exception:
            # Fallback if normalization fails
            input_text = f"""
<LUCIM-SCENARIO>
{str(lucim_scenario)}
</LUCIM-SCENARIO>
"""
        
        # Add PLANTUML-DIAGRAM block (after LUCIM-SCENARIO to match generator order)
        input_text += f"""
<PLANTUML-DIAGRAM>
{puml_content}
</PLANTUML-DIAGRAM>
"""
        
        # Create single system_prompt variable for both API call and file generation
        system_prompt = f"{instructions}\n\n{input_text}"
        
        # Write input-instructions.md BEFORE API call for debugging
        write_input_instructions_before_api(base_output_dir, system_prompt)
        
        # Count input tokens exactly
        exact_input_tokens = self.count_input_tokens(instructions, input_text)
        
        try:
            # Create response using OpenAI Responses API
            api_config = get_reasoning_config("lucim_plantuml_diagram_auditor")
            # Force the run-selected model (overrides DEFAULT_MODEL from configs)
            api_config["model"] = self.model
            # Update reasoning configuration with agent's settings
            if "reasoning" in api_config:
                api_config["reasoning"]["effort"] = self.reasoning_effort
                api_config["reasoning"]["summary"] = self.reasoning_summary
            api_config.update({
                "instructions": format_prompt_for_responses_api(system_prompt),
                "input": [{"role": "user", "content": system_prompt}]
            })
            
            # Use unified helper with configured timeout
            timeout = AGENT_TIMEOUTS.get("lucim_plantuml_diagram_auditor")
            response = create_and_wait(self.client, api_config, timeout_seconds=timeout)
            
            # Extract content and reasoning via helpers
            content = get_output_text(response)
            reasoning_summary = get_reasoning_summary(response)
            raw_response_serialized = serialize_response_to_dict(response)
            
            # Check if response is empty
            if not content or content.strip() == "":
                return {
                    "reasoning_summary": "Received empty response from API",
                    "data": None,
                    "errors": ["Empty response from API - this may indicate a model issue or timeout"],
                    "verdict": "non-compliant",
                    "non-compliant-rules": [],
                    "coverage": {"total_rules_in_dsl": "0", "evaluated": [], "not_applicable": [], "missing_evaluation": []},
                    "tokens_used": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "raw_response": raw_response_serialized
                }
            
            # Store raw LLM response text directly (no JSON parsing)
            # extract_audit_core will handle the raw text content
            core = extract_audit_core(content)

            # Extract token usage from response (centralized helper)
            from utils_openai_client import get_usage_tokens
            usage = get_usage_tokens(response, exact_input_tokens=exact_input_tokens)
            tokens_used = usage.get("total_tokens", 0)
            input_tokens = usage.get("input_tokens", 0)
            api_output_tokens = usage.get("output_tokens", 0)
            reasoning_tokens = usage.get("reasoning_tokens", 0)
            total_output_tokens = api_output_tokens if api_output_tokens is not None else 0
            visible_output_tokens = max((total_output_tokens or 0) - (reasoning_tokens or 0), 0)
            usage_dict = usage

            return {
                "reasoning_summary": reasoning_summary,
                "data": core["data"],
                "verdict": core["verdict"],
                "non-compliant-rules": core["non_compliant_rules"],
                "coverage": core["coverage"],
                "errors": core["errors"],
                "tokens_used": tokens_used,
                "input_tokens": input_tokens,
                "visible_output_tokens": visible_output_tokens,
                "raw_usage": usage_dict,
                "reasoning_tokens": reasoning_tokens,
                "total_output_tokens": total_output_tokens,
                "raw_response": raw_response_serialized
            }
                
        except Exception as e:
            return {
                "reasoning_summary": f"Error during model inference: {e}",
                "data": None,
                "errors": [f"Model inference error: {e}", f"Model used: {self.model}"],
                "verdict": "non-compliant",
                "non-compliant-rules": [],
                "coverage": {"total_rules_in_dsl": "0", "evaluated": [], "not_applicable": [], "missing_evaluation": []},
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
    

    
    def save_results(self, results: Dict[str, Any], base_name: str, model_name: str, step_number = None, output_dir = None):
        """Save parsing results using unified output file generation."""
        if not WRITE_FILES:
            return
            
        # Resolve base output directory (per-agent if provided)
        base_output_dir = output_dir if output_dir is not None else OUTPUT_DIR
        
        # Use unified function to write all output files
        write_all_output_files(
            output_dir=base_output_dir,
            results=results,
            agent_type="lucim_plantuml_diagram_auditor",
            base_name=base_name,
            model=self.model,
            timestamp=self.timestamp,
            reasoning_effort=self.reasoning_effort,
            step_number=step_number
        )
