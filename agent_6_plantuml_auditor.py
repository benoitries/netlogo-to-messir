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
from typing import Dict, Any
from google.adk.agents import LlmAgent
from openai import OpenAI
from utils_response_dump import serialize_response_to_dict, verify_exact_keys, write_minimal_artifacts
from utils_openai_client import create_and_wait, get_output_text, get_reasoning_summary
from utils_config_constants import expected_keys_for_agent

from utils_config_constants import (
    PERSONA_PLANTUML_AUDITOR, OUTPUT_DIR, LUCIM_RULES_FILE,
    get_reasoning_config, validate_agent_response, DEFAULT_MODEL, AGENT_TIMEOUTS)

# Configuration
PERSONA_FILE = PERSONA_PLANTUML_AUDITOR
WRITE_FILES = True

# Load persona and LUCIM rules
persona = PERSONA_FILE.read_text(encoding="utf-8")
lucim_rules = ""
try:
    lucim_rules = LUCIM_RULES_FILE.read_text(encoding="utf-8")
except FileNotFoundError:
    raise SystemExit(f"ERROR: Compliance rules file not found: {LUCIM_RULES_FILE}")

# Concatenate persona and rules
combined_persona = f"{persona}\n\n{lucim_rules}"


def sanitize_model_name(model_name: str) -> str:
    """Sanitize model name by replacing hyphens with underscores for valid identifier."""
    return model_name.replace("-", "_")

class NetLogoPlantUMLLUCIMAuditorAgent(LlmAgent):
    model: str = DEFAULT_MODEL
    timestamp: str = ""
    name: str = "NetLogo PlantUML Auditor"
    
    client: OpenAI = None
    reasoning_effort: str = "medium"
    reasoning_summary: str = "auto"
    text_verbosity: str = "medium"
    
    def __init__(self, model_name: str = DEFAULT_MODEL, external_timestamp: str = None):
        sanitized_name = sanitize_model_name(model_name)
        super().__init__(
            name=f"netlogo_plantuml_auditor_agent_{sanitized_name}",
            description="PlantUML auditor agent for Messir UCI compliance checking"
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
        
    def audit_plantuml_diagrams(self, puml_file_path: str, mucim_dsl_file_path: str, filename: str = "input") -> Dict[str, Any]:
        """
        Audit PlantUML sequence diagrams for Messir UCI compliance using the PlantUML Auditor persona.

        Args:
            puml_file_path: Path to the standalone .puml file from Step 5 (mandatory)
            mucim_dsl_file_path: Path to the LUCIM DSL full definition file (mandatory)
            filename: Optional filename for reference

        Returns:
            Dictionary containing reasoning, non-compliant rules, and any errors
        """
        instructions = f"{combined_persona}"

        # Read .puml file content
        try:
            puml_content = pathlib.Path(puml_file_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            return {
                "reasoning_summary": f"Error: .puml file not found at {puml_file_path}",
                "data": None,
                "errors": [f"Required .puml file not found: {puml_file_path}"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        except Exception as e:
            return {
                "reasoning_summary": f"Error reading .puml file: {e}",
                "data": None,
                "errors": [f"Failed to read .puml file {puml_file_path}: {e}"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        
        # Read LUCIM DSL file content
        try:
            mucim_dsl_content = pathlib.Path(mucim_dsl_file_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            return {
                "reasoning_summary": f"Error: LUCIM DSL file not found at {mucim_dsl_file_path}",
                "data": None,
                "errors": [f"Required LUCIM DSL file not found: {mucim_dsl_file_path}"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        except Exception as e:
            return {
                "reasoning_summary": f"Error reading LUCIM DSL file: {e}",
                "data": None,
                "errors": [f"Failed to read LUCIM DSL file {mucim_dsl_file_path}: {e}"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        
        input_text = f"""
        
Filename: {filename}

Standalone PlantUML Source Code (.puml file):
```plantuml
{puml_content}
```

LUCIM DSL Full Definition:
```markdown
{mucim_dsl_content}
```
"""
        
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
                "instructions": instructions,
                "input": input_text
            })
            
            # Use unified helper with configured timeout
            timeout = AGENT_TIMEOUTS.get("plantuml_auditor") if 'AGENT_TIMEOUTS' in globals() or 'AGENT_TIMEOUTS' in locals() else None
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
                
                # Extract and normalize fields from JSON response.
                # Always save under 'data': if no 'data' key present, wrap top-level object.
                audit_results = {}
                if isinstance(response_data, dict):
                    if "data" in response_data and isinstance(response_data["data"], dict):
                        audit_results = response_data["data"]
                    else:
                        audit_results = response_data
                errors = response_data.get("errors", []) if isinstance(response_data, dict) else []

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
                    "data": audit_results,
                    "errors": [],
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
        """Save parsing results to a single JSON file."""
        if not WRITE_FILES:
            return
            
        # New format: base-name_timestamp_AI-model_step_agent-name_version_reasoning-suffix_rest
        agent_name = "plantuml_auditor"
        # Use the agent's current reasoning level instead of global config
        reasoning_suffix = f"reasoning-{self.reasoning_effort}-{self.reasoning_summary}"
        
        # Resolve base output directory (per-agent if provided)
        base_output_dir = output_dir if output_dir is not None else OUTPUT_DIR
        # Save complete response as single JSON file (simplified)
        json_file = base_output_dir / "output-response.json"
        
        # Create complete response structure
        complete_response = {
            "agent_type": "plantuml_auditor",
            "model": self.model,
            "timestamp": self.timestamp,
            "base_name": base_name,
            "step_number": step_number,
            "reasoning_summary": results.get("reasoning_summary", "").replace("\\n", "\n"),
            "data": results.get("data", ""),
            "errors": results.get("errors", []),
            "tokens_used": results.get("tokens_used", 0),
            "input_tokens": results.get("input_tokens", 0),
            "visible_output_tokens": results.get("visible_output_tokens", 0),
            "reasoning_tokens": results.get("reasoning_tokens", 0),
            "total_output_tokens": results.get("total_output_tokens", (results.get("visible_output_tokens", 0) or 0) + (results.get("reasoning_tokens", 0) or 0)),
            "raw_response": results.get("raw_response")
        }
        
        # Validate response before saving
        validation_errors = validate_agent_response("plantuml_auditor", complete_response)
        if validation_errors:
            print(f"[WARNING] Validation errors in plantuml auditor response: {validation_errors}")
        
        # Verify exact keys before saving
        expected_keys = expected_keys_for_agent("plantuml_auditor")
        ok, missing, extra = verify_exact_keys(complete_response, expected_keys)
        if not ok:
            raise ValueError(f"response.json keys mismatch for plantuml_auditor. Missing: {sorted(missing)} Extra: {sorted(extra)}")

        # Save complete response as JSON file
        json_file.write_text(json.dumps(complete_response, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"OK: {base_name} -> output-response.json")
        
        # Save reasoning summary as markdown file
        reasoning_file = base_output_dir / "output-reasoning.md"
        reasoning_content = f"""# Reasoning Summary - {agent_name.title().replace('_', ' ')}

**Base Name:** {base_name}
**Model:** {self.model}
**Timestamp:** {self.timestamp}
**Step Number:** {step_number if step_number else 'N/A'}
**Reasoning Level:** {self.reasoning_effort}
**Reasoning Summary:** {results.get("reasoning_summary") or "No explicit reasoning summary available."}

## Token Usage

- **Total Tokens:** {results.get("tokens_used", 0):,}
- **Input Tokens:** {results.get("input_tokens", 0):,}
- **Visible Output Tokens:** {results.get("output_tokens", 0):,}
- **Reasoning Tokens:** {results.get("reasoning_tokens", 0):,}
- **Total Output Tokens (reasoning + visible):** {(results.get('output_tokens', 0) or 0) + (results.get('reasoning_tokens', 0) or 0):,}

## Reasoning Summary

{results.get("reasoning_summary") or "No explicit reasoning summary available."}

## Errors

{chr(10).join(f"- {error}" for error in results.get("errors", [])) if results.get("errors") else "No errors"}
"""
        reasoning_file.write_text(reasoning_content, encoding="utf-8")
        print(f"OK: {base_name} -> output-reasoning.md")
        
        # Save data field as separate file
        data_file = base_output_dir / "output-data.json"
        if results.get("data"):
            data_file.write_text(json.dumps(results["data"], indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"OK: {base_name} -> output-data.json")
        else:
            print(f"WARNING: No data to save for {base_name}")
        
        # Write minimal artifacts (non-breaking additions)
        write_minimal_artifacts(base_output_dir, results.get("raw_response"))
