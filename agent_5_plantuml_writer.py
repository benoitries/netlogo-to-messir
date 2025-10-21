#!/usr/bin/env python3
"""
NetLogo PlantUML Writer Agent using OpenAI models
Generates PlantUML sequence diagrams from scenario JSON files using OpenAI models.
"""

import os
import json
import datetime
import pathlib
import tiktoken
from typing import Dict, Any
from utils_config_constants import (
    PERSONA_PLANTUML_WRITER, OUTPUT_DIR, MESSIR_RULES_FILE,
    AGENT_VERSION_PLANTUML_WRITER, get_reasoning_config,
    validate_agent_response, DEFAULT_MODEL)

from google.adk.agents import LlmAgent
from openai import OpenAI
from utils_openai_client import create_and_wait, get_output_text, get_reasoning_summary, get_usage_tokens
from utils_response_dump import serialize_response_to_dict, verify_exact_keys, write_minimal_artifacts
from utils_schema_loader import get_template_for_agent, validate_data_against_template
from utils_config_constants import expected_keys_for_agent
from utils_logging import write_reasoning_md_from_payload
from utils_plantuml import process_plantuml_file

# Configuration
PERSONA_FILE = PERSONA_PLANTUML_WRITER

WRITE_FILES = True

# Ensure output directory exists


# Load persona and Messir rules
persona = PERSONA_FILE.read_text(encoding="utf-8")
messir_rules = ""
try:
    messir_rules = MESSIR_RULES_FILE.read_text(encoding="utf-8")
except FileNotFoundError:
    raise SystemExit(f"ERROR: Compliance rules file not found: {MESSIR_RULES_FILE}")

# Concatenate persona and rules
combined_persona = f"{persona}\n\n{messir_rules}"

AGENT_VERSION = AGENT_VERSION_PLANTUML_WRITER

def sanitize_model_name(model_name: str) -> str:
    """Sanitize model name by replacing hyphens with underscores for valid identifier."""
    return model_name.replace("-", "_")

class NetLogoPlantUMLWriterAgent(LlmAgent):
    model: str = DEFAULT_MODEL
    timestamp: str = ""
    name: str = "NetLogo PlantUML Writer"
    
    client: OpenAI = None
    reasoning_effort: str = "medium"
    reasoning_summary: str = "auto"  # Add client field
    text_verbosity: str = "medium"
    
    def __init__(self, model_name: str = DEFAULT_MODEL, external_timestamp: str = None):
        sanitized_name = sanitize_model_name(model_name)
        super().__init__(
            name=f"netlogo_plantuml_writer_agent_{sanitized_name}",
            description="PlantUML writer agent for generating sequence diagrams from scenarios"
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
        
    def generate_plantuml_diagrams(self, scenarios_data: Dict[str, Any], filename: str = "input", non_compliant_rules: list = None) -> Dict[str, Any]:
        """
        Generate PlantUML sequence diagrams from scenario JSON data using the PlantUML Writer persona.
        
        Args:
            scenarios_data: Scenarios JSON data containing one typical scenario
            filename: Optional filename for reference
            non_compliant_rules: Optional list of non-compliant rules from previous audit
            
        Returns:
            Dictionary containing reasoning, PlantUML diagrams, and any errors
        """
        instructions = combined_persona
        
        # Build input text with optional non-compliant rules
        input_text = f"""
Please generate PlantUML sequence diagrams from the following scenario data:

Filename: {filename}
Scenarios Data:
```json
{json.dumps(scenarios_data, indent=2)}
```
"""
        
        # Add non-compliant rules if provided
        if non_compliant_rules:
            input_text += f"\n\nNon-compliant rules from previous audit:\n{json.dumps(non_compliant_rules, indent=2)}"
        
        # Count input tokens exactly
        exact_input_tokens = self.count_input_tokens(instructions, input_text)
        
        try:
            # Create response using OpenAI Responses API
            api_config = get_reasoning_config("plantuml_writer")
            # Update reasoning configuration with agent's settings
            if "reasoning" in api_config:
                api_config["reasoning"]["effort"] = self.reasoning_effort
                api_config["reasoning"]["summary"] = self.reasoning_summary
            api_config.update({
                "instructions": instructions,
                "input": input_text
            })
            
            from utils_config_constants import AGENT_TIMEOUTS
            timeout = AGENT_TIMEOUTS.get("plantuml_writer")
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

                def _parse_best_effort_json(s: str) -> Any:
                    """Best-effort JSON extraction when prose wraps a JSON object.
                    Tries direct loads; if it fails, extracts the first top-level JSON object substring.
                    """
                    try:
                        return json.loads(s)
                    except Exception:
                        pass
                    start = s.find("{")
                    end = s.rfind("}")
                    if start != -1 and end != -1 and end > start:
                        candidate = s[start:end+1].strip()
                        try:
                            return json.loads(candidate)
                        except Exception:
                            anchor = s.find('{"data"')
                            if anchor != -1:
                                end2 = s.find("\n\n", anchor)
                                end2 = end if end2 == -1 else end2
                                candidate2 = s[anchor:end2].strip()
                                try:
                                    return json.loads(candidate2)
                                except Exception:
                                    pass
                    raise json.JSONDecodeError("Unable to parse JSON from response", s, 0)

                # Parse the response as JSON (best-effort)
                response_data = _parse_best_effort_json(content_clean)
                print(f"[DEBUG] Successfully parsed response as JSON")
                
                # Extract and normalize fields from JSON response.
                # Always save under 'data': if no 'data' key present, wrap top-level object.
                plantuml_diagrams = {}
                if isinstance(response_data, dict):
                    if "data" in response_data and isinstance(response_data["data"], dict):
                        plantuml_diagrams = response_data["data"]
                    else:
                        plantuml_diagrams = response_data
                errors = response_data.get("errors", []) if isinstance(response_data, dict) else []

                # If JSON data is empty or missing PlantUML, attempt to extract raw @startuml...@enduml from content
                if (not plantuml_diagrams) or (
                    isinstance(plantuml_diagrams, dict) and not self._extract_plantuml_text(plantuml_diagrams)
                ):
                    import re
                    m = re.search(r"@startuml[\s\S]*?@enduml", content)
                    if m:
                        uml_text = m.group(0)
                        plantuml_diagrams = {
                            "typical": {
                                "name": plantuml_diagrams.get("typical", {}).get("name", "typical") if isinstance(plantuml_diagrams, dict) else "typical",
                                "plantuml": uml_text
                            }
                        }

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
                    "data": plantuml_diagrams,
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
                    "errors": [f"Failed to parse PlantUML diagrams JSON: {e}", f"Raw response: {content[:200]}..."],
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
        agent_name = "plantuml_writer"
        # Use the agent's current reasoning level instead of global config
        reasoning_suffix = f"reasoning-{self.reasoning_effort}-{self.reasoning_summary}"
        
        # Resolve base output directory (per-agent if provided)
        base_output_dir = output_dir if output_dir is not None else OUTPUT_DIR
        # Save complete response as single JSON file (simplified)
        json_file = base_output_dir / "output-response.json"
        
        # Create complete response structure
        complete_response = {
            "agent_type": "plantuml_writer",
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
        validation_errors = validate_agent_response("plantuml_writer", complete_response)
        if validation_errors:
            print(f"[WARNING] Validation errors in plantuml writer response: {validation_errors}")
        
        # Verify exact keys before saving
        expected_keys = expected_keys_for_agent("plantuml_writer")
        ok, missing, extra = verify_exact_keys(complete_response, expected_keys)
        if not ok:
            raise ValueError(f"response.json keys mismatch for plantuml_writer. Missing: {sorted(missing)} Extra: {sorted(extra)}")

        # Save complete response as JSON file
        json_file.write_text(json.dumps(complete_response, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"OK: {base_name} -> output-response.json")
        
        # Save reasoning payload as markdown file (centralized writer)
        payload = {
            "reasoning": results.get("reasoning"),
            "reasoning_summary": results.get("reasoning_summary"),
            "tokens_used": results.get("tokens_used"),
            "input_tokens": results.get("input_tokens"),
            "visible_output_tokens": results.get("visible_output_tokens"),
            "total_output_tokens": results.get("total_output_tokens"),
            "reasoning_tokens": results.get("reasoning_tokens"),
            "usage": results.get("raw_usage"),
            "errors": results.get("errors"),
        }
        write_reasoning_md_from_payload(
            output_dir=base_output_dir,
            agent_name=agent_name,
            base_name=base_name,
            model=self.model,
            timestamp=self.timestamp,
            reasoning_effort=self.reasoning_effort,
            step_number=step_number,
            payload=payload,
        )
        print(f"OK: {base_name} -> output-reasoning.md")
        
        # Optional: Validate data against persona template (shallow)
        try:
            template = get_template_for_agent("plantuml_writer")
            if template is not None:
                report = validate_data_against_template(complete_response.get("data"), template)
                if report.get("missing_keys"):
                    print(f"[WARNING] Data is missing keys from persona template: {report['missing_keys']}")
        except Exception as e:
            print(f"[WARNING] Persona template validation failed (plantuml_writer): {e}")

        # Save data field as separate file
        data_file = base_output_dir / "output-data.json"
        if results.get("data"):
            data_file.write_text(json.dumps(results["data"], indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"OK: {base_name} -> output-data.json")
        else:
            print(f"WARNING: No data to save for {base_name}")

        # Write minimal artifacts (non-breaking additions)
        write_minimal_artifacts(base_output_dir, results.get("raw_response"))

        # Additionally, write a standalone .puml file containing the diagram text
        try:
            diagram_text = self._extract_plantuml_text(results.get("data")) if results.get("data") else None
            if diagram_text and "@startuml" in diagram_text and "@enduml" in diagram_text:
                # Canonical simplified filename per task requirement
                puml_file = base_output_dir / "diagram.puml"
                puml_file.write_text(diagram_text, encoding="utf-8")
                print(f"OK: {base_name} -> diagram.puml")
                
                # Post-process the PlantUML file to clean escape characters
                try:
                    success = process_plantuml_file(puml_file)
                    if success:
                        print(f"✅ Post-processed PlantUML file: {puml_file.name}")
                    else:
                        print(f"⚠️  Post-processing had issues for: {puml_file.name}")
                except Exception as e:
                    print(f"[WARNING] Post-processing failed for {puml_file.name}: {e}")
                
                # Surface the path for orchestrator logging/downstream use
                results["puml_file"] = str(puml_file)
            else:
                print("WARNING: Could not extract valid PlantUML diagram text to write .puml file")
        except Exception as e:
            print(f"[WARNING] Failed to write .puml file: {e}")

    def _extract_plantuml_text(self, data: Dict[str, Any]) -> str:
        """
        Attempt to extract the PlantUML diagram text from the agent data structure.
        The method is defensive against variations in the response shape.
        """
        if not isinstance(data, dict):
            return ""

        # Common structures: data["typical"] may be a string with @startuml or a dict with a field
        candidate_nodes = []
        if "typical" in data:
            candidate_nodes.append(data["typical"])
        # Fallback: consider any values in data
        candidate_nodes.extend(list(data.values()))

        def find_in_obj(obj: Any) -> str:
            # String directly containing plantuml
            if isinstance(obj, str) and "@startuml" in obj:
                return obj
            # Dict: look for likely keys
            if isinstance(obj, dict):
                for key in ("plantuml", "diagram", "uml", "content", "text"):
                    val = obj.get(key)
                    if isinstance(val, str) and "@startuml" in val:
                        return val
                # Also scan nested values
                for val in obj.values():
                    found = find_in_obj(val)
                    if found:
                        return found
            # List: scan items
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
        # Final attempt: brute-force over the whole dict
        return find_in_obj(data).strip()


def main():
    """Main function for testing the agent."""
    import argparse
    
    parser = argparse.ArgumentParser(description="NetLogo PlantUML Writer Agent")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model to use (default: from config)")
    parser.add_argument("--base-name", required=True, help="Base name for the input files")
    parser.add_argument("--timestamp", help="External timestamp to use")
    parser.add_argument("--step", type=int, help="Step number for output files")
    
    args = parser.parse_args()
    
    # Create agent
    agent = NetLogoPlantUMLWriterAgent(args.model, args.timestamp)
    
    # Load input files
    scenarios_file = OUTPUT_DIR / f"{args.base_name}_{args.timestamp or agent.timestamp}_{args.model}_3_scenarios.json"
    
    if not scenarios_file.exists():
        print(f"Error: Scenarios file not found: {scenarios_file}")
        return
    
    # Load the data
    try:
        with open(scenarios_file, "r", encoding="utf-8") as f:
            scenarios_data = json.load(f)
            
    except Exception as e:
        print(f"Error loading scenarios file: {e}")
        return
    
    # Generate PlantUML diagrams
    print(f"[PlantUMLWriter] Generating PlantUML diagrams for {args.base_name}...")
    results = agent.generate_plantuml_diagrams(scenarios_data, args.base_name)
    
    # Save results
    agent.save_results(results, args.base_name, args.model, args.step)
    
    # Print summary
    if results.get("data"):
        print(f"[PlantUMLWriter] Successfully generated PlantUML diagrams:")
        if "typical" in results["data"]:
            print(f"  - Typical diagram: {results['data']['typical'].get('name', 'Unnamed')}")
        # Only typical diagram is generated
    else:
        print(f"[PlantUMLWriter] Failed to generate PlantUML diagrams")
        if results.get("errors"):
            for error in results["errors"]:
                print(f"  Error: {error}")

if __name__ == "__main__":
    main() 