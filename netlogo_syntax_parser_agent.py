#!/usr/bin/env python3
"""
NetLogo AST Agent using OpenAI models
Parses NetLogo source code into structured AST using OpenAI models.
"""

import os
import json
import datetime
import pathlib
import tiktoken
from typing import Dict, Any, Optional
from google.adk.agents import LlmAgent
from openai import OpenAI
from openai_client_utils import create_and_wait, get_output_text, get_reasoning_summary, get_usage_tokens
from response_dump_utils import serialize_response_to_dict, verify_exact_keys, write_minimal_artifacts
from response_schema_expected import expected_keys_for_agent
from logging_utils import write_reasoning_md_from_payload

from config import (
    PERSONA_SYNTAX_PARSER, OUTPUT_DIR, 
    AGENT_VERSION_SYNTAX_PARSER, get_reasoning_config,
    validate_agent_response, AGENT_TIMEOUTS, DEFAULT_MODEL
)

# IL Syntax descriptor files (default absolute paths)
IL_SYN_MAPPING_DEFAULT = (pathlib.Path(__file__).resolve().parent / "input-persona" / "DSL_IL_SYN-mapping.md").resolve()
IL_SYN_DESCRIPTION_DEFAULT = (pathlib.Path(__file__).resolve().parent / "input-persona" / "DSL_IL_SYN-description.md").resolve()

# Configuration
PERSONA_FILE = PERSONA_SYNTAX_PARSER
WRITE_FILES = True

# Load persona
persona = PERSONA_FILE.read_text(encoding="utf-8")

# Get agent version from config
AGENT_VERSION = AGENT_VERSION_SYNTAX_PARSER

def sanitize_model_name(model_name: str) -> str:
    """Sanitize model name by replacing hyphens with underscores for valid identifier."""
    return model_name.replace("-", "_")

class NetLogoSyntaxParserAgent(LlmAgent):
    model: str = DEFAULT_MODEL
    timestamp: str = ""
    name: str = "NetLogo Syntax Parser"
    
    client: OpenAI = None
    reasoning_effort: str = "medium"
    reasoning_summary: str = "auto"
    text_verbosity: str = "medium"
    # IL-SYN reference inputs (absolute paths set by orchestrator)
    il_syn_mapping_path: Optional[str] = None
    il_syn_description_path: Optional[str] = None
    
    def __init__(self, model_name: str = DEFAULT_MODEL, external_timestamp: str = None):
        sanitized_name = sanitize_model_name(model_name)
        super().__init__(
            name=f"netlogo_ast_agent_{sanitized_name}",
            description="AST-based agent for parsing NetLogo code structure"
        )
        self.model = model_name
        
        # Use external timestamp if provided, otherwise generate new one
        if external_timestamp:
            self.timestamp = external_timestamp
        else:
            # Format: YYYYMMDD_HHMM for better readability
            self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        
        # Configure OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise SystemExit("ERROR: OPENAI_API_KEY environment variable required")
        self.client = OpenAI(api_key=api_key)
    
    def update_il_syn_inputs(self, mapping_path: Optional[str], description_path: Optional[str]):
        """Configure IL-SYN external reference file paths.

        Args:
            mapping_path: Absolute path to DSL_IL_SYN-mapping.md
            description_path: Absolute path to DSL_IL_SYN-description.md
        """
        self.il_syn_mapping_path = mapping_path
        self.il_syn_description_path = description_path
        # Lightweight validation/logging
        try:
            if mapping_path:
                mp = pathlib.Path(mapping_path)
                if not mp.exists():
                    print(f"[WARNING] IL-SYN mapping file not found: {mapping_path}")
            if description_path:
                dp = pathlib.Path(description_path)
                if not dp.exists():
                    print(f"[WARNING] IL-SYN description file not found: {description_path}")
        except Exception as e:
            print(f"[WARNING] Failed to validate IL-SYN paths: {e}")
    
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
        reasoning_effort = config.get("reasoning_effort")
        reasoning_summary = config.get("reasoning_summary")
        text_verbosity = config.get("text_verbosity")

        if reasoning_effort is not None or reasoning_summary is not None:
            # Only update provided parts; keep existing values when None
            self.reasoning_effort = reasoning_effort or self.reasoning_effort
            self.reasoning_summary = reasoning_summary or self.reasoning_summary
        if text_verbosity is not None:
            self.text_verbosity = text_verbosity

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
        
    def parse_netlogo_code(self, code: str, filename: str, output_dir: Optional[pathlib.Path] = None) -> Dict[str, Any]:
        if not filename or not isinstance(filename, str):
            raise ValueError("filename is required and must be a non-empty string")
        # Compose instructions: persona + explicit IL-SYN references as separate context files
        ilsyn_refs = ""
        try:
            # Allow orchestrator to provide absolute paths via instance attributes
            mapping_path = pathlib.Path(getattr(self, "il_syn_mapping_path", IL_SYN_MAPPING_DEFAULT))
            description_path = pathlib.Path(getattr(self, "il_syn_description_path", IL_SYN_DESCRIPTION_DEFAULT))
            mapping_txt = mapping_path.read_text(encoding="utf-8") if mapping_path.exists() else ""
            description_txt = description_path.read_text(encoding="utf-8") if description_path.exists() else ""
            ilsyn_refs = f"\n\n[REFERENCE: DSL_IL_SYN-description.md]\n{description_txt}\n\n[REFERENCE: DSL_IL_SYN-mapping.md]\n{mapping_txt}\n"
            # Log reference ingestion status similarly to semantics agent
            if mapping_path and not mapping_txt:
                print(f"[WARNING] IL-SYN mapping file not found: {mapping_path}")
            if description_path and not description_txt:
                print(f"[WARNING] IL-SYN description file not found: {description_path}")
            if mapping_txt or description_txt:
                print("OK: Ingested IL-SYN reference files for syntax parsing")
        except Exception as e:
            print(f"[WARNING] Failed to load IL-SYN references: {e}")

        instructions = f"{persona}{ilsyn_refs}"
        
        input_text = f"""
Filename: {filename}
Code:
```
{code}
```
"""
        
        # Count input tokens exactly
        exact_input_tokens = self.count_input_tokens(instructions, input_text)
        
        try:
            # Create response using OpenAI Responses API
            api_config = get_reasoning_config("syntax_parser")
            # Update reasoning configuration with agent's settings
            if "reasoning" in api_config:
                api_config["reasoning"]["effort"] = self.reasoning_effort
                api_config["reasoning"]["summary"] = self.reasoning_summary
            api_config.update({
                "instructions": instructions,
                "input": input_text
            })
            
            timeout = AGENT_TIMEOUTS.get("syntax_parser")
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
                ast = {}
                if isinstance(response_data, dict):
                    if "data" in response_data and isinstance(response_data["data"], dict):
                        ast = response_data["data"]
                    else:
                        ast = response_data
                errors = response_data.get("errors", []) if isinstance(response_data, dict) else []

                # Extract token usage from response (centralized helper)
                usage = get_usage_tokens(response, exact_input_tokens=exact_input_tokens)
                tokens_used = usage.get("total_tokens", 0)
                input_tokens = usage.get("input_tokens", 0)
                api_output_tokens = usage.get("output_tokens", 0)
                reasoning_tokens = usage.get("reasoning_tokens", 0)
                # Prefer API-derived total output tokens when possible
                api_total_output_tokens = max((tokens_used or 0) - (input_tokens or 0), 0)
                visible_output_tokens = max((api_total_output_tokens or api_output_tokens or 0) - (reasoning_tokens or 0), 0)
                total_output_tokens = api_total_output_tokens if api_total_output_tokens is not None else (visible_output_tokens + (reasoning_tokens or 0))
                usage_dict = usage

                return {
                    "reasoning_summary": reasoning_summary,
                    "data": ast,
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
                    "errors": [f"Failed to parse AST JSON: {e}", f"Raw response: {content[:200]}..."],
                    "tokens_used": 0,
                    "input_tokens": 0,
                    "visible_output_tokens": 0,
                    "total_output_tokens": 0,
                    "raw_response": raw_response_serialized
                }
                
        except Exception as e:
            return {
                "reasoning_summary": f"Error during model inference: {e}",
                "data": None,
                "errors": [f"Model inference error: {e}", f"Model used: {self.model}"],
                "tokens_used": 0,
                "input_tokens": 0,
                "visible_output_tokens": 0,
                "total_output_tokens": 0
            }
    

    
    def save_results(self, results: Dict[str, Any], base_name: str, model_name: str, step_number = None, output_dir = None):
        """Save parsing results to a single JSON file."""
        if not WRITE_FILES:
            return
            
        # New format: base-name_timestamp_AI-model_step_agent-name_version_reasoning-suffix_rest
        agent_name = "syntax_parser"
        # Use the agent's current reasoning level instead of global config
        reasoning_suffix = f"reasoning-{self.reasoning_effort}-{self.reasoning_summary}"
        
        # Resolve base output directory (per-agent if provided)
        base_output_dir = output_dir if output_dir is not None else OUTPUT_DIR
        # Save complete response as single JSON file (simplified filename)
        json_file = base_output_dir / "output-response.json"
        
        # Create complete response structure
        complete_response = {
            "agent_type": "syntax_parser",
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
        validation_errors = validate_agent_response("syntax_parser", complete_response)
        if validation_errors:
            print(f"[WARNING] Validation errors in syntax parser response: {validation_errors}")
        
        # Verify exact keys before saving
        expected_keys = expected_keys_for_agent("syntax_parser")
        ok, missing, extra = verify_exact_keys(complete_response, expected_keys)
        # Debug logging to diagnose schema/key mismatches and write targets
        try:
            print(f"[DEBUG] syntax_parser.save_results WRITE_FILES={WRITE_FILES}")
            print(f"[DEBUG] syntax_parser.save_results output_dir={base_output_dir}")
            print(f"[DEBUG] syntax_parser.save_results base_name={base_name} model={self.model} step_number={step_number}")
            print(f"[DEBUG] syntax_parser emitted keys: {sorted(list(complete_response.keys()))}")
            print(f"[DEBUG] syntax_parser expected keys: {sorted(list(expected_keys))}")
            if not ok:
                print(f"[ERROR] syntax_parser missing keys: {sorted(list(missing))}")
                print(f"[ERROR] syntax_parser extra keys: {sorted(list(extra))}")
        except Exception as e:
            print(f"[WARNING] Failed to print debug schema info (syntax_parser): {e}")
        if not ok:
            raise ValueError(f"response.json keys mismatch for syntax_parser. Missing: {sorted(missing)} Extra: {sorted(extra)}")

        # Save complete response as JSON file
        json_file.write_text(json.dumps(complete_response, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"OK: {base_name} -> output-response.json")
        
        # Streaming artifact generation intentionally disabled to avoid legacy file creation

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
        print(f"OK: {base_name} -> reasoning.md")
        
        # Save data field as separate file
        data_file = base_output_dir / "output-data.json"
        if results.get("data"):
            data_file.write_text(json.dumps(results["data"], indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"OK: {base_name} -> output-data.json")
        else:
            print(f"WARNING: No data to save for {base_name}")

        # Write minimal artifacts (non-breaking additions)
        write_minimal_artifacts(base_output_dir, results.get("raw_response"))

