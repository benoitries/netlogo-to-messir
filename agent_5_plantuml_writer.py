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
from typing import Dict, Any, Optional
from utils_config_constants import (
    PERSONA_PLANTUML_WRITER, OUTPUT_DIR, LUCIM_RULES_FILE,
    get_reasoning_config, validate_agent_response, DEFAULT_MODEL)

from google.adk.agents import LlmAgent
from openai import OpenAI
from utils_openai_client import create_and_wait, get_output_text, get_reasoning_summary, get_usage_tokens, format_prompt_for_responses_api
from utils_response_dump import serialize_response_to_dict, verify_exact_keys, write_minimal_artifacts, write_all_output_files, write_input_instructions_before_api
from utils_schema_loader import get_template_for_agent, validate_data_against_template
from utils_config_constants import expected_keys_for_agent
from utils_logging import write_reasoning_md_from_payload
from utils_task_loader import load_task_instruction
from utils_plantuml import process_plantuml_file

# Configuration
PERSONA_FILE = PERSONA_PLANTUML_WRITER

WRITE_FILES = True


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
    persona_path: str = ""
    persona_text: str = ""
    lucim_rules_path: str = ""
    lucim_dsl_definition: str = ""
    
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
        # Initialize persona and rules from defaults; orchestrator can override
        try:
            self.persona_path = str(PERSONA_FILE)
            self.persona_text = pathlib.Path(self.persona_path).read_text(encoding="utf-8")
        except Exception:
            self.persona_text = ""
        try:
            self.lucim_rules_path = str(LUCIM_RULES_FILE)
            self.lucim_dsl_definition = pathlib.Path(self.lucim_rules_path).read_text(encoding="utf-8")
        except Exception:
            self.lucim_dsl_definition = ""
    
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
            self.lucim_dsl_definition = pathlib.Path(rules_path).read_text(encoding="utf-8")
        except Exception as e:
            print(f"[WARNING] Failed to load LUCIM rules file: {rules_path} ({e})")
            self.lucim_dsl_definition = ""
    
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
        
    def generate_plantuml_diagrams(self, lucim_scenario: Dict[str, Any], non_compliant_rules: list = None, output_dir: Optional[pathlib.Path] = None) -> Dict[str, Any]:
        """
        Generate PlantUML sequence diagrams from scenario JSON data using the PlantUML Writer persona.
        
        Args:
            lucim_scenario (Dict[str, Any]): Scenario JSON data containing one typical scenario.
            non_compliant_rules (list, optional): Optional list of non-compliant rules from previous audit.
            output_dir (Optional[pathlib.Path], optional): Optional output directory for file outputs. Defaults to None.
        
        Returns:
            Dict[str, Any]: Dictionary containing reasoning, PlantUML diagrams, and any errors.
        """
        # Resolve base output directory (use provided output_dir or fall back to OUTPUT_DIR)
        base_output_dir = output_dir if output_dir is not None else OUTPUT_DIR
        
        # Load TASK instruction using utility function
        task_content = load_task_instruction(5, "PlantUML Writer")

        # Build canonical instructions order: task_content → persona → LUCIM DSL definition
        instructions = f"{task_content}\n\n{self.persona_text}\n\n{self.lucim_dsl_definition}"

        # Normalize input to handle list of scenarios or single scenario.
        # Expected final block to send to the model: { "scenario": { ... } }
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
        # Build input text with required tagged sections
        input_text = f"""
<LUCIM-SCENARIO>
```json
{json.dumps({"scenario": scenario_block} if scenario_block is not None else normalized_input, indent=2)}
```
</LUCIM-SCENARIO>
"""

        # Create single system_prompt variable for both API call and file generation
        system_prompt = f"{instructions}\n\n{input_text}"
        
        # Write input-instructions.md BEFORE API call for debugging
        write_input_instructions_before_api(base_output_dir, system_prompt)
        
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
                "instructions": format_prompt_for_responses_api(system_prompt),
                "input": [{"role": "user", "content": system_prompt}]
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
                # Normalize to list of {"diagram": {...}} under 'data'.
                plantuml_diagrams_obj = {}
                data_list: list = []
                if isinstance(response_data, dict):
                    if "data" in response_data and isinstance(response_data["data"], (dict, list)):
                        plantuml_diagrams_obj = response_data["data"] if isinstance(response_data["data"], dict) else {}
                        # If already a list, trust it but normalize items to have 'diagram' wrapper
                        if isinstance(response_data["data"], list):
                            for item in response_data["data"]:
                                if isinstance(item, dict) and "diagram" in item:
                                    data_list.append(item)
                                elif isinstance(item, dict):
                                    data_list.append({"diagram": item})
                                elif isinstance(item, str):
                                    data_list.append({"diagram": {"plantuml": item}})
                    else:
                        plantuml_diagrams_obj = response_data
                errors = response_data.get("errors", []) if isinstance(response_data, dict) else []

                # If JSON data is empty or missing PlantUML, attempt to extract raw @startuml...@enduml from content
                have_valid_uml = False
                if data_list:
                    # check if any item contains a valid UML text
                    for it in data_list:
                        uml = self._extract_plantuml_text(it.get("diagram") if isinstance(it, dict) else it)
                        if uml:
                            have_valid_uml = True
                            break
                else:
                    have_valid_uml = bool(self._extract_plantuml_text(plantuml_diagrams_obj))

                if (not data_list and not plantuml_diagrams_obj) or (not have_valid_uml):
                    import re
                    m = re.search(r"@startuml[\s\S]*?@enduml", content)
                    if m:
                        uml_text = m.group(0)
                        data_list = [{
                            "diagram": {
                                "name": "typical",
                                "plantuml": uml_text
                            }
                        }]
                # If we still don't have a list but have an object, convert it
                if not data_list and isinstance(plantuml_diagrams_obj, dict):
                    # turn each entry into a diagram item if it looks like a diagram
                    if any(k in plantuml_diagrams_obj for k in ("plantuml", "name")):
                        data_list = [{"diagram": plantuml_diagrams_obj}]
                    else:
                        for key, val in plantuml_diagrams_obj.items():
                            if isinstance(val, dict):
                                item = val if ("plantuml" in val or "name" in val) else {"name": key, **val}
                                data_list.append({"diagram": item})
                            elif isinstance(val, str):
                                data_list.append({"diagram": {"name": key, "plantuml": val}})

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
                    "data": data_list,
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
        """Save parsing results using unified output file generation."""
        if not WRITE_FILES:
            return
            
        # Resolve base output directory (per-agent if provided)
        base_output_dir = output_dir if output_dir is not None else OUTPUT_DIR
        
        # Optional: Validate data against persona template (shallow)
        try:
            template = get_template_for_agent("plantuml_writer")
            if template is not None:
                report = validate_data_against_template(results.get("data"), template)
                if report.get("missing_keys"):
                    print(f"[WARNING] Data is missing keys from persona template: {report['missing_keys']}")
        except Exception as e:
            print(f"[WARNING] Persona template validation failed (plantuml_writer): {e}")

        # Extract PlantUML diagram text for special file handling
        diagram_text = self._extract_plantuml_text(results.get("data")) if results.get("data") else None

        # Defensive fallback: if no data detected, attempt to extract UML directly from raw_response text
        if (not diagram_text or "@startuml" not in diagram_text or "@enduml" not in diagram_text):
            try:
                raw = results.get("raw_response")
                # Attempt to find a text field containing the UML block
                uml_text = ""
                import re
                raw_json = json.dumps(raw) if not isinstance(raw, (dict, list)) else json.dumps(raw)
                m = re.search(r"@startuml[\s\S]*?@enduml", raw_json)
                if m:
                    # Unescape common JSON escapes (minimal)
                    uml_text = m.group(0)
                    uml_text = uml_text.replace("\\n", "\n").replace("\\t", "\t").replace("\\\"", '"')
                if uml_text and "@startuml" in uml_text and "@enduml" in uml_text:
                    diagram_text = uml_text
                    # Also backfill a minimal data structure so downstream files are emitted
                    results["data"] = [{"diagram": {"name": "typical", "plantuml": uml_text}}]
                    # Ensure errors is a list
                    results.setdefault("errors", [])
            except Exception:
                pass
        
        # Prepare special files for unified function
        special_files = None
        if diagram_text and "@startuml" in diagram_text and "@enduml" in diagram_text:
            special_files = {
                "plantuml_diagram": diagram_text,
                "post_process": True
            }
            # Surface the path for orchestrator logging/downstream use
            results["puml_file"] = str(base_output_dir / "diagram.puml")
        
        # Use unified function to write all output files
        write_all_output_files(
            output_dir=base_output_dir,
            results=results,
            agent_type="plantuml_writer",
            base_name=base_name,
            model=self.model,
            timestamp=self.timestamp,
            reasoning_effort=self.reasoning_effort,
            step_number=step_number,
            special_files=special_files
        )

    def _extract_plantuml_text(self, data: Dict[str, Any]) -> str:
        """
        Attempt to extract the PlantUML diagram text from the agent data structure.
        The method is defensive against variations in the response shape.
        """
        # Accept dict or list structures and find the first PlantUML block
        if data is None:
            return ""
        candidate_nodes = []
        if isinstance(data, dict):
            if "typical" in data:
                candidate_nodes.append(data["typical"])
            if "diagram" in data:
                candidate_nodes.append(data["diagram"])
            candidate_nodes.extend(list(data.values()))
        elif isinstance(data, list):
            candidate_nodes.extend(data)

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
    results = agent.generate_plantuml_diagrams(scenarios_data)
    
    # Save results
    agent.save_results(results, args.base_name, args.model, args.step)
    
    # Print summary
    if results.get("data"):
        print(f"[PlantUMLWriter] Successfully generated PlantUML diagrams:")
        try:
            # Expect a list of {"diagram": {...}}
            items = results["data"] if isinstance(results["data"], list) else []
            for idx, item in enumerate(items):
                if isinstance(item, dict):
                    diag = item.get("diagram", {})
                    if isinstance(diag, dict):
                        print(f"  - Diagram {idx+1}: {diag.get('name', 'Unnamed')}")
        except Exception:
            pass
    else:
        print(f"[PlantUMLWriter] Failed to generate PlantUML diagrams")
        if results.get("errors"):
            for error in results["errors"]:
                print(f"  Error: {error}")

if __name__ == "__main__":
    main() 