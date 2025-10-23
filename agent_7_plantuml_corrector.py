#!/usr/bin/env python3
"""
NetLogo PlantUML Corrector Agent using OpenAI models
Corrects PlantUML sequence diagrams based on audit results using OpenAI models.
"""

import os
import json
import datetime
import pathlib
import tiktoken
from typing import Dict, Any, List
from google.adk.agents import LlmAgent
from openai import OpenAI
from utils_response_dump import serialize_response_to_dict, verify_exact_keys, write_minimal_artifacts
from utils_openai_client import get_usage_tokens, create_and_wait, get_output_text, get_reasoning_summary
from utils_config_constants import expected_keys_for_agent
from utils_plantuml import process_plantuml_file

from utils_config_constants import (
    PERSONA_PLANTUML_CORRECTOR, OUTPUT_DIR, LUCIM_RULES_FILE,
    get_reasoning_config, validate_agent_response, DEFAULT_MODEL, AGENT_TIMEOUTS)

# Configuration
PERSONA_FILE = PERSONA_PLANTUML_CORRECTOR
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

class NetLogoPlantUMLLUCIMCorrectorAgent(LlmAgent):
    model: str = DEFAULT_MODEL
    timestamp: str = ""
    name: str = "NetLogo PlantUML Corrector"
    
    client: OpenAI = None
    reasoning_effort: str = "medium"
    reasoning_summary: str = "auto"
    text_verbosity: str = "medium"
    
    def __init__(self, model_name: str = DEFAULT_MODEL, external_timestamp: str = None):
        sanitized_name = sanitize_model_name(model_name)
        super().__init__(
            name=f"netlogo_plantuml_corrector_agent_{sanitized_name}",
            description="PlantUML corrector agent for fixing LUCIM UCI compliance issues"
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
            # Get the appropriate encoding for the model, fallback if not recognized
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
        
    def correct_plantuml_diagrams(self, plantuml_diagrams: Dict[str, Any],
                                 non_compliant_rules: List[str], lucim_dsl_content: str = None, filename: str = "input") -> Dict[str, Any]:
        """
        Correct PlantUML sequence diagrams based on non-compliant rules using the PlantUML Corrector persona.
        
        Args:
            plantuml_diagrams: PlantUML diagrams to correct
            non_compliant_rules: List of non-compliant rules to fix
            lucim_dsl_content: LUCIM DSL full definition content (MANDATORY)
            filename: Optional filename for reference
            
        Returns:
            Dictionary containing reasoning, corrected diagrams, and any errors
        """
        # Validate mandatory inputs
        if not plantuml_diagrams:
            return {
                "reasoning_summary": "MISSING MANDATORY INPUT: PlantUML diagrams from Step 5 are required",
                "data": None,
                "errors": ["MANDATORY INPUT MISSING: PlantUML diagrams from Step 5 must be provided"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        
        
        if not non_compliant_rules:
            return {
                "reasoning_summary": "MISSING MANDATORY INPUT: Non-compliant rules from Step 6 are required",
                "data": None,
                "errors": ["MANDATORY INPUT MISSING: Non-compliant rules from Step 6 must be provided"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        
        if lucim_dsl_content is None or lucim_dsl_content.strip() == "":
            return {
                "reasoning_summary": "MISSING MANDATORY INPUT: LUCIM DSL content is required",
                "data": None,
                "errors": ["MANDATORY INPUT MISSING: LUCIM DSL content must be provided"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        
        instructions = f"{combined_persona}"
        
        input_text = f"""

Filename: {filename}

Original PlantUML Diagrams:
```json
{json.dumps(plantuml_diagrams, indent=2)}
```

Non-compliant Rules to Fix:
```json
{json.dumps(non_compliant_rules, indent=2)}
```

LUCIM DSL Full Definition:
```
{lucim_dsl_content}
```
"""
        
        # Count input tokens exactly
        exact_input_tokens = self.count_input_tokens(instructions, input_text)
        
        try:
            # Create response using OpenAI Responses API
            api_config = get_reasoning_config("plantuml_corrector")
            # Update reasoning configuration with agent's settings
            if "reasoning" in api_config:
                api_config["reasoning"]["effort"] = self.reasoning_effort
                api_config["reasoning"]["summary"] = self.reasoning_summary
            api_config.update({
                "instructions": instructions,
                "input": input_text
            })
            
            # Use unified helper with configured timeout
            timeout = AGENT_TIMEOUTS.get("plantuml_corrector") if 'AGENT_TIMEOUTS' in globals() or 'AGENT_TIMEOUTS' in locals() else None
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
                corrected_diagrams = {}
                if isinstance(response_data, dict):
                    if "data" in response_data and isinstance(response_data["data"], dict):
                        corrected_diagrams = response_data["data"]
                    else:
                        corrected_diagrams = response_data
                errors = response_data.get("errors", []) if isinstance(response_data, dict) else []

                # Extract token usage from response (centralized helper)
                usage = get_usage_tokens(response, exact_input_tokens=exact_input_tokens)
                tokens_used = usage.get("total_tokens", 0)
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                reasoning_tokens = usage.get("reasoning_tokens", 0)
                visible_output_tokens = max((output_tokens or 0) - (reasoning_tokens or 0), 0)
                total_output_tokens = visible_output_tokens + (reasoning_tokens or 0)
                usage_dict = usage

                return {
                    "reasoning_summary": reasoning_summary,
                    "data": corrected_diagrams,
                    "errors": [],
                    "tokens_used": tokens_used,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "raw_usage": usage_dict,
                    "reasoning_tokens": reasoning_tokens,
                    "total_output_tokens": total_output_tokens,
                    "raw_response": raw_response_serialized
                }
            except json.JSONDecodeError as e:
                return {
                    "reasoning_summary": reasoning_summary,
                    "data": None,
                    "errors": [f"Failed to parse corrected diagrams JSON: {e}", f"Raw response: {content[:200]}..."],
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
        agent_name = "plantuml_corrector"
        # Use the agent's current reasoning level instead of global config
        reasoning_suffix = f"reasoning-{self.reasoning_effort}-{self.reasoning_summary}"
        
        # Resolve base output directory (per-agent if provided)
        base_output_dir = output_dir if output_dir is not None else OUTPUT_DIR
        # Save complete response as single JSON file (simplified)
        json_file = base_output_dir / "output-response.json"
        
        # Create complete response structure
        complete_response = {
            "agent_type": "plantuml_corrector",
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
        validation_errors = validate_agent_response("plantuml_corrector", complete_response)
        if validation_errors:
            print(f"[WARNING] Validation errors in plantuml corrector response: {validation_errors}")
        
        # Verify exact keys before saving
        expected_keys = expected_keys_for_agent("plantuml_corrector")
        ok, missing, extra = verify_exact_keys(complete_response, expected_keys)
        if not ok:
            raise ValueError(f"response.json keys mismatch for plantuml_corrector. Missing: {sorted(missing)} Extra: {sorted(extra)}")

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
 - **Visible Output Tokens:** {results.get("visible_output_tokens", 0):,}
- **Reasoning Tokens:** {results.get("reasoning_tokens", 0):,}
- **Total Output Tokens (reasoning + visible):** {results.get("total_output_tokens", (results.get('visible_output_tokens', 0) or 0) + (results.get('reasoning_tokens', 0) or 0)):,}

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

        # Additionally, write a corrected standalone .puml file containing the diagram text (if available)
        try:
            diagram_text = self._extract_plantuml_text(results.get("data")) if results.get("data") else None
            if diagram_text and "@startuml" in diagram_text and "@enduml" in diagram_text:
                # Enforce canonical filename for Stage 07 corrected diagram
                puml_file = base_output_dir / "diagram.puml"
                puml_file.write_text(diagram_text, encoding="utf-8")
                print(f"OK: {base_name} -> diagram.puml")
                
                # Post-process the corrected PlantUML file to clean escape characters
                try:
                    success = process_plantuml_file(puml_file)
                    if success:
                        print(f"✅ Post-processed corrected PlantUML file: {puml_file.name}")
                    else:
                        print(f"⚠️  Post-processing had issues for corrected: {puml_file.name}")
                except Exception as e:
                    print(f"[WARNING] Post-processing failed for corrected {puml_file.name}: {e}")
                
                results["puml_file"] = str(puml_file)
            else:
                print("WARNING: Could not extract valid PlantUML diagram text to write corrected .puml file")
        except Exception as e:
            print(f"[WARNING] Failed to write corrected .puml file: {e}")

    def _extract_plantuml_text(self, data: Dict[str, Any]) -> str:
        if not isinstance(data, dict):
            return ""
        candidate_nodes = []
        if "typical" in data:
            candidate_nodes.append(data["typical"])
        candidate_nodes.extend(list(data.values()))

        def find_in_obj(obj: Any) -> str:
            if isinstance(obj, str) and "@startuml" in obj:
                return obj
            if isinstance(obj, dict):
                for key in ("plantuml", "diagram", "uml", "content", "text"):
                    val = obj.get(key)
                    if isinstance(val, str) and "@startuml" in val:
                        return val
                for val in obj.values():
                    found = find_in_obj(val)
                    if found:
                        return found
            if isinstance(obj, list):
                for item in obj:
                    found = find_in_obj(item)
                    if found:
                        return found
            return ""

        for node in candidate_nodes:
            found = find_in_obj(node)
            if found:
                return found.strip()
        return find_in_obj(data).strip()
