#!/usr/bin/env python3
"""
NetLogo Behavior Extractor using OpenAI models
Extracts behavioral patterns from NetLogo semantics using IL-SEM references and structured interface description.
"""

import os
import json
import datetime
import pathlib
import tiktoken
from typing import Dict, Any, List, Optional
from utils_config_constants import (
    PERSONA_BEHAVIOR_EXTRACTOR, OUTPUT_DIR, 
    get_reasoning_config, validate_agent_response, DEFAULT_MODEL
)

from google.adk.agents import LlmAgent
from openai import OpenAI
from utils_openai_client import create_and_wait, get_output_text, get_reasoning_summary, get_usage_tokens, format_prompt_for_responses_api
from utils_response_dump import serialize_response_to_dict, verify_exact_keys, write_minimal_artifacts, write_input_instructions_before_api, write_all_output_files
from utils_config_constants import expected_keys_for_agent
from utils_logging import write_reasoning_md_from_payload
from utils_task_loader import load_task_instruction

# Configuration
PERSONA_FILE = PERSONA_BEHAVIOR_EXTRACTOR
WRITE_FILES = True



class NetLogoBehaviorExtractorAgent(LlmAgent):
    model: str = DEFAULT_MODEL
    timestamp: str = ""
    name: str = "NetLogo Behavior Extractor"
    
    client: OpenAI = None
    reasoning_effort: str = "medium"
    reasoning_summary: str = "auto"
    text_verbosity: str = "medium"
    # IL-SEM reference inputs (absolute paths set by orchestrator)
    il_sem_mapping_path: Optional[str] = None
    il_sem_description_path: Optional[str] = None
    persona_path: Optional[str] = None
    persona_text: str = ""
    
    def __init__(self, model_name: str = DEFAULT_MODEL, external_timestamp: str = None):
        super().__init__(
            name=f"netlogo_behavior_extractor_agent_{model_name}",
            description="Behavior extraction agent building state machine from IL-SEM and structured interface description"
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
        # Initialize persona from default, can be overridden by orchestrator later
        try:
            self.persona_path = str(PERSONA_FILE)
            self.persona_text = pathlib.Path(self.persona_path).read_text(encoding="utf-8")
        except Exception:
            self.persona_text = ""
    
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

    def update_il_sem_inputs(self, mapping_path: str, description_path: str) -> None:
        """Set absolute paths for IL-SEM descriptor files provided by the orchestrator."""
        self.il_sem_mapping_path = mapping_path
        self.il_sem_description_path = description_path

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

    def update_persona_path(self, persona_path: Optional[str]) -> None:
        """Update the persona file path and reload its content."""
        if not persona_path:
            return
        self.persona_path = persona_path
        try:
            self.persona_text = pathlib.Path(persona_path).read_text(encoding="utf-8")
        except Exception as e:
            print(f"[WARNING] Failed to load persona file: {persona_path} ({e})")
            self.persona_text = ""

    
    def parse_from_ilsem_and_interface_description(self, interface_widgets: List[Dict[str, str]], case_study_name: str, output_dir: str = None) -> Dict[str, Any]:
        """
        Build semantics using only IL-SEM mapping/description and structured interface description from Agent 2a.
        This method is the canonical Stage 2b entry point (no images, no AST, no raw code).
        """
        # Resolve base output directory (per-agent if provided)
        if output_dir is None:
            output_dir = OUTPUT_DIR
        
        # Base persona + IL-SEM references
        instructions_sections: List[str] = []
        il_sem_info: List[str] = []
        desc_block: str = ""
        mapping_block: str = ""
        try:
            if self.il_sem_mapping_path and pathlib.Path(self.il_sem_mapping_path).exists():
                mapping_text = pathlib.Path(self.il_sem_mapping_path).read_text(encoding="utf-8")
                mapping_block = f"\n{mapping_text}"
            else:
                if self.il_sem_mapping_path:
                    print(f"[WARNING] IL-SEM mapping file not found: {self.il_sem_mapping_path}")
            if self.il_sem_description_path and pathlib.Path(self.il_sem_description_path).exists():
                desc_text = pathlib.Path(self.il_sem_description_path).read_text(encoding="utf-8")
                desc_block = f"\n{desc_text}"
            else:
                if self.il_sem_description_path:
                    print(f"[WARNING] IL-SEM description file not found: {self.il_sem_description_path}")
        except Exception as e:
            print(f"[WARNING] Failed to read IL-SEM files: {e}")
        # Force canonical order: Description first, then Mapping
        if desc_block:
            il_sem_info.append(desc_block)
        if mapping_block:
            il_sem_info.append(mapping_block)
        if il_sem_info:
            print("OK: Ingested IL-SEM reference files for semantics parsing (Stage 2b)")

        # Prepare interface widgets description
        interface_entries: List[str] = []
        for widget in interface_widgets:
            widget_type = widget.get('type', 'Unknown')
            widget_name = widget.get('name', 'unnamed')
            widget_desc = widget.get('description', 'No description')
            interface_entries.append(f"- {widget_type}: {widget_name} — {widget_desc}")
        
        interface_text = "\n".join(interface_entries) if interface_entries else "- (no widgets detected)"
        if not interface_entries:
            print("[WARNING] No interface widgets provided to behavior extractor")
        
        # Load TASK instruction using utility function
        task_content = load_task_instruction(2, "behavior_extractor")

        # Canonical instructions order: task_content → persona → IL-SEM references
        rules_block = "\n\n".join(il_sem_info) if il_sem_info else ""
        instructions = f"{task_content}\n\n{self.persona_text}\n\n{rules_block}".rstrip()

        # Load NetLogo source code
        netlogo_code = self._load_netlogo_source_code(case_study_name)
        
        # Build input text with required tagged sections
        input_text = f"""
<NETLOGO-SOURCE-CODE>
{netlogo_code}
</NETLOGO-SOURCE-CODE>

<NETLOGO-INTERFACE-DESCRIPTION>
{interface_text}
</NETLOGO-INTERFACE-DESCRIPTION>
"""

        # Create single system_prompt variable for both API call and file generation
        system_prompt = f"{instructions}\n\n{input_text}"
        
        # Write input-instructions.md BEFORE API call for debugging
        write_input_instructions_before_api(output_dir, system_prompt)

        exact_input_tokens = self.count_input_tokens(instructions, input_text)
        try:
            api_config = get_reasoning_config("behavior_extractor")
            if "reasoning" in api_config:
                api_config["reasoning"]["effort"] = self.reasoning_effort
                api_config["reasoning"]["summary"] = self.reasoning_summary
            api_config.update({
                "instructions": format_prompt_for_responses_api(system_prompt),
                "input": [{"role": "user", "content": system_prompt}]
            })

            from utils_config_constants import AGENT_TIMEOUTS
            timeout = AGENT_TIMEOUTS.get("behavior_extractor")
            response = create_and_wait(self.client, api_config, timeout_seconds=timeout)

            content = get_output_text(response)
            reasoning_summary = get_reasoning_summary(response)
            raw_response_serialized = serialize_response_to_dict(response)

            if not content or content.strip() == "":
                return {
                    "reasoning_summary": "Received empty response from API",
                    "data": None,
                    "errors": ["Empty response from API - this may indicate a model issue or timeout"],
                    "tokens_used": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "model": self.model,
                    "timestamp": self.timestamp
                }

            # Parse JSON response
            try:
                # Clean content (remove markdown fences if present)
                cleaned_content = content.strip()
                if cleaned_content.startswith("```json"):
                    cleaned_content = cleaned_content[7:]
                if cleaned_content.startswith("```"):
                    cleaned_content = cleaned_content[3:]
                if cleaned_content.endswith("```"):
                    cleaned_content = cleaned_content[:-3]
                cleaned_content = cleaned_content.strip()
                
                parsed_data = json.loads(cleaned_content)
                
                # Validate response structure
                if not isinstance(parsed_data, dict):
                    raise ValueError("Response must be a JSON object")
                
                # Check for required fields
                if "data" not in parsed_data:
                    raise ValueError("Response must contain 'data' field")
                
                if "errors" not in parsed_data:
                    raise ValueError("Response must contain 'errors' field")
                
                # Validate data field if present
                if parsed_data["data"] is not None:
                    if not isinstance(parsed_data["data"], dict):
                        raise ValueError("Data field must be a JSON object or null")
                
                # Validate errors field
                if not isinstance(parsed_data["errors"], list):
                    raise ValueError("Errors field must be a list")
                
                # All validations passed
                print("✓ Behavior extraction response validation successful")
                
            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse JSON response: {e}")
                return {
                    "reasoning_summary": reasoning_summary,
                    "data": None,
                    "errors": [f"JSON parsing failed: {e}"],
                    "tokens_used": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "model": self.model,
                    "timestamp": self.timestamp
                }
            except Exception as e:
                print(f"[ERROR] Response validation failed: {e}")
                return {
                    "reasoning_summary": reasoning_summary,
                    "data": None,
                    "errors": [f"Response validation failed: {e}"],
                    "tokens_used": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "model": self.model,
                    "timestamp": self.timestamp
                }

            # Extract token usage
            usage_tokens = get_usage_tokens(response)
            input_tokens = usage_tokens.get("input_tokens", 0)
            output_tokens = usage_tokens.get("output_tokens", 0)
            reasoning_tokens = usage_tokens.get("reasoning_tokens", 0)
            total_tokens = input_tokens + output_tokens + reasoning_tokens

            # Prepare response data
            response_data = {
                "reasoning_summary": reasoning_summary,
                "data": parsed_data["data"],
                "errors": parsed_data["errors"],
                "tokens_used": total_tokens,
                "input_tokens": input_tokens,
                # Provide total_output_tokens to satisfy downstream validation
                # and allow writer to derive visible_output_tokens deterministically
                "total_output_tokens": output_tokens + reasoning_tokens,
                "reasoning_tokens": reasoning_tokens,
                "model": self.model,
                "timestamp": self.timestamp,
                "interface_widgets": interface_widgets,
                # Keep raw response for optional auditing
                "raw_response": raw_response_serialized
            }

            # Write artifacts
            if WRITE_FILES:
                from pathlib import Path as _P
                write_all_output_files(
                    _P(output_dir), 
                    response_data, 
                    "behavior_extractor",
                    case_study_name, 
                    self.model,
                    self.timestamp,
                    "medium"  # reasoning_effort
                )

            return response_data

        except Exception as e:
            error_msg = f"Behavior extraction failed: {e}"
            print(f"[ERROR] {error_msg}")
            
            # Write error artifacts
            if WRITE_FILES:
                from pathlib import Path as _P
                write_minimal_artifacts(
                    _P(output_dir), 
                    error_msg
                )
            
            return {
                "reasoning_summary": "Behavior extraction failed",
                "data": None,
                "errors": [error_msg],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "reasoning_tokens": 0,
                "model": self.model,
                "timestamp": self.timestamp
            }

    def _load_netlogo_source_code(self, base_name: str) -> str:
        """Load NetLogo source code for the given case."""
        try:
            # Look for NetLogo source file in input-netlogo directory
            input_dir = pathlib.Path(__file__).parent / "input-netlogo"
            netlogo_file = input_dir / f"{base_name}-netlogo-code.md"
            
            if netlogo_file.exists():
                code_content = netlogo_file.read_text(encoding="utf-8")
                print(f"[INFO] Loaded NetLogo source code: {netlogo_file.name}")
                return code_content
            else:
                print(f"[WARNING] NetLogo source file not found: {netlogo_file}")
                return f"NetLogo source code not found for case: {base_name}"
        except Exception as e:
            print(f"[WARNING] Failed to load NetLogo source code: {e}")
            return f"Error loading NetLogo source code: {e}"

    def count_input_tokens(self, instructions: str, input_text: str) -> int:
        """Count input tokens for the given instructions and input text."""
        try:
            encoding = tiktoken.encoding_for_model(self.model)
            total_text = f"{instructions}\n\n{input_text}"
            return len(encoding.encode(total_text))
        except Exception:
            # Fallback estimation
            return len(total_text.split()) * 2


def main():
    """CLI for testing the behavior extractor."""
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python agent_2b_netlogo_behavior_extractor.py <interface-json-file> <base-name> [output-dir]")
        sys.exit(1)
    
    interface_json_file = sys.argv[1]
    base_name = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "output"
    
    # Load interface widgets
    try:
        with open(interface_json_file, 'r', encoding='utf-8') as f:
            interface_data = json.load(f)
        
        if isinstance(interface_data, dict) and "widgets" in interface_data:
            interface_widgets = interface_data["widgets"]
        elif isinstance(interface_data, list):
            interface_widgets = interface_data
        else:
            print(f"Error: Invalid interface JSON format in {interface_json_file}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error loading interface JSON: {e}")
        sys.exit(1)
    
    # Create agent
    agent = NetLogoBehaviorExtractorAgent()
    
    # Extract behavior
    result = agent.parse_from_ilsem_and_interface_description(interface_widgets, base_name, output_dir)
    
    print("Behavior extraction complete!")
    if result.get('errors'):
        print(f"Errors: {result['errors']}")
    else:
        print("✓ No errors in behavior extraction")
        print(f"Tokens used: {result.get('tokens_used', 0)}")

if __name__ == "__main__":
    main()
