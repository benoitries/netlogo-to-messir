#!/usr/bin/env python3
"""
NetLogo LUCIM Scenario Generator Agent using OpenAI models
Generates LUCIM scenarios from NetLogo source using OpenAI models.
"""

import json
import datetime
import pathlib
import tiktoken
from typing import Dict, Any
from google.adk.agents import LlmAgent
from openai import OpenAI
from utils_openai_client import create_and_wait, get_output_text, get_reasoning_summary, get_usage_tokens, format_prompt_for_responses_api
from utils_response_dump import serialize_response_to_dict,write_all_output_files, write_input_instructions_before_api
from utils_schema_loader import get_template_for_agent, validate_data_against_template

from utils_config_constants import (
    PERSONA_LUCIM_SCENARIO_GENERATOR, OUTPUT_DIR,
    get_reasoning_config, DEFAULT_MODEL, RULES_LUCIM_SCENARIO)
from utils_path import sanitize_agent_name

# Configuration
PERSONA_FILE = PERSONA_LUCIM_SCENARIO_GENERATOR
WRITE_FILES = True

# Load persona and LUCIM rules (instance-level will be set in __init__)



class LUCIMScenarioGeneratorAgent(LlmAgent):
    model: str = DEFAULT_MODEL
    timestamp: str = ""
    name: str = "NetLogo LUCIM Scenario Generator"
    
    client: OpenAI = None
    reasoning_effort: str = "medium"
    reasoning_summary: str = "auto"  # Add client field
    text_verbosity: str = "medium"
    persona_path: str = ""
    persona_text: str = ""
    lucim_rules_path: str = ""
    lucim_rules_text: str = ""
    
    def __init__(self, model_name: str = DEFAULT_MODEL, external_timestamp: str = None):
        super().__init__(
            name=f"netlogo_lucim_scenario_generator_agent_{sanitize_agent_name(model_name)}",
            description="LUCIM scenario generator agent"
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
        # Initialize persona from default; orchestrator may override
        try:
            self.persona_path = str(PERSONA_FILE)
            self.persona_text = pathlib.Path(self.persona_path).read_text(encoding="utf-8")
        except Exception:
            self.persona_text = ""
        # Load scenario rules from centralized constant (fallback used if caller does not pass them)
        try:
            self.lucim_rules_path = str(RULES_LUCIM_SCENARIO)
            self.lucim_rules_text = pathlib.Path(self.lucim_rules_path).read_text(encoding="utf-8")
        except Exception:
            self.lucim_rules_text = ""
    
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
    
    def update_persona_path(self, persona_path: str) -> None:
        if not persona_path:
            return
        self.persona_path = persona_path
        try:
            self.persona_text = pathlib.Path(persona_path).read_text(encoding="utf-8")
        except Exception as e:
            print(f"[WARNING] Failed to load persona file: {persona_path} ({e})")
            self.persona_text = ""
    
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
        
    def generate_scenarios(self, lucim_operation_model: Dict[str, Any], scenario_rules_text: str, scenario_auditor_feedback: Dict[str, Any], previous_scenario: Dict[str, Any] | list | None, output_dir: str = None) -> Dict[str, Any]:
        """
        Generate LUCIM scenarios from mandatory inputs using the LUCIM Scenario Generator persona.
        
        Args:
            lucim_operation_model: Step 03 LUCIM operation model (required)
            scenario_rules_text: Scenario rules content (RULES_LUCIM_Scenario.md). If empty, agent uses its internal fallback copy.
            scenario_auditor_feedback: Audit report from Scenario Auditor (required parameter but may be empty on first run)
            previous_scenario: Last LUCIM Scenario produced by Scenario Generator (required parameter but may be empty on first run)
            
        Returns:
            Dictionary containing reasoning, scenarios, and any errors
        """
        # Resolve base output directory (per-agent if provided)
        base_output_dir = output_dir if output_dir is not None else OUTPUT_DIR
        
        # Validate mandatory inputs and build system_prompt for debugging (even on error)
        # Prefer provided rules text; fallback to internally loaded rules content
        effective_rules = scenario_rules_text if (isinstance(scenario_rules_text, str) and scenario_rules_text.strip()) else self.lucim_rules_text
        
        # Build canonical instructions: persona + explicit scenario rules
        # Note: No <LUCIM-DSL-DESCRIPTION> is required or injected anywhere.
        instructions = f"{self.persona_text}\n\n{effective_rules}".strip() if (self.persona_text and self.persona_text.strip()) else ""

        # Build input blocks with required tagged sections (without repeating instructions)
        # LUCIM-OPERATION-MODEL should be taken exactly as-is from the output-data.json file
        # of the OpModel Generator agent. Do not normalize JSON. Just parse and insert as raw text.
        input_text = ""
        operation_model_text = ""
        
        # Try to read the operation model directly from the output-data.json file
        # Look for the file in the parent directory structure: 1_lucim_operation_model/iter-*/1-generator/output-data.json
        # Structure: {case}-{model}/2_lucim_scenario/iter-{N}/1-generator/ -> go up 3 levels to {case}-{model}/
        if output_dir:
            try:
                output_path = pathlib.Path(output_dir)
                if not output_path.is_absolute():
                    # Resolve relative paths
                    output_path = output_path.resolve()
                
                # Navigate to the run root directory (go up from 2_lucim_scenario/iter-*/1-generator/)
                # output_path = 2_lucim_scenario/iter-*/1-generator/
                # output_path.parent = iter-*/
                # output_path.parent.parent = 2_lucim_scenario/
                # output_path.parent.parent.parent = {case}-{model}/ (run root)
                run_root = output_path.parent.parent.parent
                
                # Find the latest iteration of operation model
                op_model_root = run_root / "1_lucim_operation_model"
                if op_model_root.exists() and op_model_root.is_dir():
                    # Find the latest iteration directory
                    iter_dirs = sorted(
                        [d for d in op_model_root.glob("iter-*") if d.is_dir()],
                        key=lambda x: int(x.name.split("-")[1]) if len(x.name.split("-")) > 1 and x.name.split("-")[1].isdigit() else 0
                    )
                    if iter_dirs:
                        latest_iter = iter_dirs[-1]
                        op_model_data_file = latest_iter / "1-generator" / "output-data.json"
                        if op_model_data_file.exists() and op_model_data_file.is_file():
                            # Read the file content exactly as-is (raw text, no JSON parsing)
                            operation_model_text = op_model_data_file.read_text(encoding="utf-8")
            except Exception:
                # Fallback to parameter if file reading fails (silent failure)
                pass
        
        # If file reading failed or output_dir not provided, use the parameter
        # But only if it's a string (raw text); never use str() on dict as it would normalize JSON
        if not operation_model_text and lucim_operation_model:
            if isinstance(lucim_operation_model, str):
                operation_model_text = lucim_operation_model
            # If it's not a string (e.g., dict), don't convert it - it would normalize the JSON
            # The file reading above should have worked, so this is a fallback only
        
        # Build the input text block
        if operation_model_text:
            input_text = f"""
<LUCIM-OPERATION-MODEL>
{operation_model_text}
</LUCIM-OPERATION-MODEL>

"""
        else:
            input_text = """
<LUCIM-OPERATION-MODEL>
</LUCIM-OPERATION-MODEL>

"""
        
        # Always include auditor report and previous scenarios blocks (empty on first call)
        # Use raw text copy without json.dumps or markdown fences
        try:
            if scenario_auditor_feedback:
                if isinstance(scenario_auditor_feedback, str):
                    auditor_text = scenario_auditor_feedback
                else:
                    auditor_text = str(scenario_auditor_feedback)
            else:
                auditor_text = ""
        except Exception:
            auditor_text = ""
        input_text += f"\n<AUDIT-REPORT>\n{auditor_text}\n</AUDIT-REPORT>\n"

        try:
            if previous_scenario is not None:
                if isinstance(previous_scenario, str):
                    prev_scenario_text = previous_scenario
                else:
                    prev_scenario_text = str(previous_scenario)
            else:
                prev_scenario_text = ""
        except Exception:
            prev_scenario_text = ""
        input_text += f"\n<PREVIOUS-LUCIM-SCENARIOS>\n{prev_scenario_text}\n</PREVIOUS-LUCIM-SCENARIOS>\n"

        # Build system_prompt with required tagged blocks and inputs
        system_prompt = f"{instructions}\n\n{input_text}" if instructions else input_text
        
        # Write input-instructions.md BEFORE API call for debugging (even if validation fails)
        write_input_instructions_before_api(base_output_dir, system_prompt)
        
        # Now validate mandatory inputs and return early if missing
        if not lucim_operation_model:
            return {
                "reasoning_summary": "Missing mandatory input: LUCIM operation model",
                "data": None,
                "errors": ["LUCIM operation model is required but not provided"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        if not self.persona_text or self.persona_text.strip() == "":
            return {
                "reasoning_summary": "Missing mandatory input: Persona for Scenario Generator",
                "data": None,
                "errors": ["Persona PSN_LUCIM_Scenario_Generator.md is required but not provided"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        
        # Count input tokens exactly
        exact_input_tokens = self.count_input_tokens(instructions, input_text)
        
        try:
            # Create response using OpenAI Responses API
            api_config = get_reasoning_config("lucim_scenario_generator")
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
            
            from utils_config_constants import AGENT_TIMEOUTS
            timeout = AGENT_TIMEOUTS.get("lucim_scenario_generator")
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
                    "tokens_used": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "raw_response": raw_response_serialized
                }
            
            # Store raw text content directly (no JSON parsing)
            # The raw text will be written to output-data.json and passed to the auditor
            scenario_raw_text = content

            # Extract token usage from response (centralized helper)
            usage = get_usage_tokens(response, exact_input_tokens=exact_input_tokens)
            tokens_used = usage.get("total_tokens", 0)
            input_tokens = usage.get("input_tokens", 0)
            api_output_tokens = usage.get("output_tokens", 0)
            reasoning_tokens = usage.get("reasoning_tokens", 0)
            total_output_tokens = api_output_tokens if api_output_tokens is not None else max((tokens_used or 0) - (input_tokens or 0), 0)
            visible_output_tokens = max((total_output_tokens or 0) - (reasoning_tokens or 0), 0)
            usage_dict = usage

            return {
                "reasoning_summary": reasoning_summary,
                "data": scenario_raw_text,  # Store raw text content (no JSON parsing)
                "errors": None,
                "tokens_used": tokens_used,
                "input_tokens": input_tokens,
                "visible_output_tokens": visible_output_tokens,
                "raw_usage": usage_dict,
                "reasoning_tokens": reasoning_tokens,
                "total_output_tokens": total_output_tokens,
                "raw_response": raw_response_serialized
            }
                
        except Exception as e:
            from utils_openai_client import build_error_raw_payload
            return {
                "reasoning_summary": f"Error during model inference: {e}",
                "data": None,
                "errors": [f"Model inference error: {e}", f"Model used: {self.model}"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "raw_response": build_error_raw_payload(e)
            }
    

    
    def save_results(self, results: Dict[str, Any], base_name: str, model_name: str, step_number = None, output_dir = None):
        """Save parsing results using unified output file generation."""
        if not WRITE_FILES:
            return
            
        # Resolve base output directory (per-agent if provided)
        base_output_dir = output_dir if output_dir is not None else OUTPUT_DIR
        
        # Optional: Validate data against persona template (shallow)
        try:
            template = get_template_for_agent("lucim_scenario_generator")
            if template is not None:
                report = validate_data_against_template(results.get("data"), template)
                if report.get("missing_keys"):
                    print(f"[WARNING] Data is missing keys from persona template: {report['missing_keys']}")
        except Exception as e:
            print(f"[WARNING] Persona template validation failed (lucim_scenario_generator): {e}")
        
        # Use unified function to write all output files
        write_all_output_files(
            output_dir=base_output_dir,
            results=results,
            agent_type="lucim_scenario_generator",
            base_name=base_name,
            model=self.model,
            timestamp=self.timestamp,
            reasoning_effort=self.reasoning_effort,
            step_number=step_number
        )

