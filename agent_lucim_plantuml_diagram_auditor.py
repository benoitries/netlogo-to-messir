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
from utils_response_dump import serialize_response_to_dict, verify_exact_keys, write_minimal_artifacts, write_all_output_files, write_input_instructions_before_api
from utils_openai_client import create_and_wait, get_output_text, get_reasoning_summary, format_prompt_for_responses_api
from utils_config_constants import expected_keys_for_agent
from utils_task_loader import load_task_instruction

from utils_config_constants import (
    PERSONA_PLANTUML_AUDITOR, OUTPUT_DIR, LUCIM_RULES_FILE,
    get_reasoning_config, validate_agent_response, DEFAULT_MODEL, AGENT_TIMEOUTS)

# Configuration
PERSONA_FILE = PERSONA_PLANTUML_AUDITOR
WRITE_FILES = True


def sanitize_model_name(model_name: str) -> str:
    """Sanitize model name by replacing hyphens with underscores for valid identifier."""
    return model_name.replace("-", "_")

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
    lucim_rules_path: str = ""
    lucim_rules_text: str = ""
    
    def __init__(self, model_name: str = DEFAULT_MODEL, external_timestamp: str = None):
        sanitized_name = sanitize_model_name(model_name)
        super().__init__(
            name=f"netlogo_plantuml_auditor_agent_{sanitized_name}",
            description="PlantUML auditor agent for LUCIM UCI compliance checking"
        )
        self.model = model_name
        
        # Use external timestamp if provided, otherwise generate new one
        if external_timestamp:
            self.timestamp = external_timestamp
        else:
            # Format: YYYYMMDD_HHMM for better readability
            self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        
        # Configure OpenAI client (assumes key already validated by orchestrator)
        from utils_config_constants import OPENAI_API_KEY
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        # Initialize persona and rules from defaults; orchestrator can override
        try:
            self.persona_path = str(PERSONA_FILE)
            self.persona_text = pathlib.Path(self.persona_path).read_text(encoding="utf-8")
        except Exception:
            self.persona_text = ""
        try:
            self.lucim_rules_path = str(LUCIM_RULES_FILE)
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
    
    def update_lucim_rules_path(self, rules_path: str) -> None:
        if not rules_path:
            return
        self.lucim_rules_path = rules_path
        try:
            self.lucim_rules_text = pathlib.Path(rules_path).read_text(encoding="utf-8")
        except Exception as e:
            print(f"[WARNING] Failed to load LUCIM rules file: {rules_path} ({e})")
            self.lucim_rules_text = ""
    
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
        
    def audit_plantuml_diagrams(self, plantuml_diagram_file_path: str, lucim_dsl_file_path: str, step: int = 6, output_dir: Optional[pathlib.Path] = None) -> Dict[str, Any]:
        """
        Audit PlantUML sequence diagrams for LUCIM UCI compliance using the PlantUML Auditor persona.

        Args:
            plantuml_diagram_file_path: Path to the standalone .puml file from Step 5 (mandatory)
            lucim_dsl_file_path: Path to the LUCIM DSL full definition file (mandatory)
            step: Step number for task file selection (default: 6)
            output_dir: Optional output directory for results

        Returns:
            Dictionary containing reasoning, non-compliant rules, and any errors
        """
        # Resolve base output directory (use provided output_dir or fall back to OUTPUT_DIR)
        base_output_dir = output_dir if output_dir is not None else OUTPUT_DIR
        
        # Load TASK instruction using utility function
        task_content = load_task_instruction(step, f"PlantUML Auditor (step {step})")

        # Build canonical instructions order: task_content → persona → LUCIM rules (use instance values)
        instructions = f"{task_content}\n\n{self.persona_text}\n\n{self.lucim_rules_text}"

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
        
        # Read LUCIM DSL file content
        try:
            lucim_dsl_content = pathlib.Path(lucim_dsl_file_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            return {
                "reasoning_summary": f"Error: LUCIM DSL file not found at {lucim_dsl_file_path}",
                "data": None,
                "errors": [f"Required LUCIM DSL file not found: {lucim_dsl_file_path}"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        except Exception as e:
            return {
                "reasoning_summary": f"Error reading LUCIM DSL file: {e}",
                "data": None,
                "errors": [f"Failed to read LUCIM DSL file {lucim_dsl_file_path}: {e}"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        
        # Build input text with required tagged sections
        input_text = f"""
<PLANTUML-DIAGRAM>
```plantuml
{puml_content}
```
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
            api_config = get_reasoning_config("plantuml_auditor")
            # Update reasoning configuration with agent's settings
            if "reasoning" in api_config:
                api_config["reasoning"]["effort"] = self.reasoning_effort
                api_config["reasoning"]["summary"] = self.reasoning_summary
            api_config.update({
                "instructions": format_prompt_for_responses_api(system_prompt),
                "input": [{"role": "user", "content": system_prompt}]
            })
            
            # Use unified helper with configured timeout
            timeout = AGENT_TIMEOUTS.get("plantuml_auditor")
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
            
            # Parse JSON response
            try:
                # Debug: Log the raw response for troubleshooting
                # Note: These debug prints are kept as they provide useful debugging information
                print(f"[DEBUG] Raw response length: {len(content)}")
                print(f"[DEBUG] Raw response preview: {content[:500]}...")
                
                # Clean up the content
                content_clean = content.strip()
                if content_clean.startswith("```json"):
                    content_clean = content_clean.replace("```json", "").replace("```", "").strip()
                elif content_clean.startswith("```"):
                    content_clean = content_clean.replace("```", "").strip()
                
                # Parse the response as JSON
                response_data = json.loads(content_clean)
                print(f"[DEBUG] Successfully parsed response as JSON")
                
                # Normalize to persona-defined auditor schema (top-level {data:{...}, errors:[]})
                from utils_auditor_schema import normalize_auditor_like_response
                normalized = normalize_auditor_like_response(response_data)

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
                    "data": normalized.get("data"),
                    "errors": normalized.get("errors", []),
                    "tokens_used": tokens_used,
                    "input_tokens": input_tokens,
                    "visible_output_tokens": visible_output_tokens,
                    "raw_usage": usage_dict,
                    "reasoning_tokens": reasoning_tokens,
                    "total_output_tokens": total_output_tokens,
                    "raw_response": raw_response_serialized
                }
            except json.JSONDecodeError as e:
                return {
                    "reasoning_summary": reasoning_summary,
                    "data": None,
                    "errors": [f"Failed to parse audit results JSON: {e}", f"Raw response: {content[:200]}..."],
                    "tokens_used": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "raw_response": raw_response_serialized
                }
                
        except Exception as e:
            return {
                "reasoning_summary": f"Error during model inference: {e}",
                "data": None,
                "errors": [f"Model inference error: {e}", f"Model used: {self.model}"],
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
            agent_type="plantuml_auditor",
            base_name=base_name,
            model=self.model,
            timestamp=self.timestamp,
            reasoning_effort=self.reasoning_effort,
            step_number=step_number
        )
