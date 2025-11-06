#!/usr/bin/env python3
"""
NetLogo Abstract Syntax Extractor Agent using OpenAI models
Extracts abstract syntax from NetLogo source code into structured AST using OpenAI models.
"""

import os
import json
import datetime
import pathlib
import tiktoken
from typing import Dict, Any, Optional
from google.adk.agents import LlmAgent
from openai import OpenAI
from utils_openai_client import create_and_wait, get_output_text, get_reasoning_summary, get_usage_tokens, format_prompt_for_responses_api
from utils_response_dump import serialize_response_to_dict, verify_exact_keys, write_minimal_artifacts, write_input_instructions_before_api, write_all_output_files
from utils_config_constants import expected_keys_for_agent, validate_agent_response, PERSONA_NETLOGO_ABSTRACT_SYNTAX_EXTRACTOR, OUTPUT_DIR, DEFAULT_MODEL, get_reasoning_config, AGENT_TIMEOUTS
from utils_logging import write_reasoning_md_from_payload

from utils_task_loader import load_task_instruction

# IL Syntax descriptor files (default absolute paths)
IL_SYN_MAPPING_DEFAULT = (pathlib.Path(__file__).resolve().parent / "input-persona" / "DSL_IL_SYN-mapping.md").resolve()
IL_SYN_DESCRIPTION_DEFAULT = (pathlib.Path(__file__).resolve().parent / "input-persona" / "DSL_IL_SYN-description.md").resolve()

# Configuration
PERSONA_FILE = PERSONA_NETLOGO_ABSTRACT_SYNTAX_EXTRACTOR
WRITE_FILES = True



class NetLogoAbstractSyntaxExtractorAgent(LlmAgent):
    model: str = DEFAULT_MODEL
    timestamp: str = ""
    name: str = "NetLogo Abstract Syntax Extractor"
    
    client: OpenAI = None
    reasoning_effort: str = "medium"
    reasoning_summary: str = "auto"
    text_verbosity: str = "medium"
    # IL-SYN reference inputs (absolute paths set by orchestrator)
    il_syn_mapping_path: Optional[str] = None
    il_syn_description_path: Optional[str] = None
    persona_path: Optional[str] = None
    persona_text: str = ""
    
    def __init__(self, model_name: str = DEFAULT_MODEL, external_timestamp: str = None):
        super().__init__(
            name=f"netlogo_abstract_syntax_extractor_agent_{model_name}",
            description="Abstract syntax extraction agent for NetLogo code structure"
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
        
    def parse_netlogo_code(self, netlogo_source_code: str, filename: str, output_dir: Optional[pathlib.Path] = None) -> Dict[str, Any]:
        if not filename or not isinstance(filename, str):
            raise ValueError("filename is required and must be a non-empty string")
        
        # Resolve base output directory (use provided output_dir or fall back to OUTPUT_DIR)
        base_output_dir = output_dir if output_dir is not None else OUTPUT_DIR
        
        # Compose instructions: task_content → persona → IL-SYN references
        ilsyn_refs = ""
        try:
            # Allow orchestrator to provide absolute paths via instance attributes
            mapping_path = pathlib.Path(getattr(self, "il_syn_mapping_path", IL_SYN_MAPPING_DEFAULT))
            description_path = pathlib.Path(getattr(self, "il_syn_description_path", IL_SYN_DESCRIPTION_DEFAULT))
            mapping_txt = mapping_path.read_text(encoding="utf-8") if mapping_path.exists() else ""
            description_txt = description_path.read_text(encoding="utf-8") if description_path.exists() else ""
            ilsyn_refs = f"\n\n{description_txt}\n\n{mapping_txt}\n"
            # Log reference ingestion status similarly to semantics agent
            if mapping_path and not mapping_txt:
                print(f"[WARNING] IL-SYN mapping file not found: {mapping_path}")
            if description_path and not description_txt:
                print(f"[WARNING] IL-SYN description file not found: {description_path}")
            if mapping_txt or description_txt:
                print("OK: Ingested IL-SYN reference files for abstract syntax extraction")
        except Exception as e:
            print(f"[WARNING] Failed to load IL-SYN references: {e}")

        # Load TASK instruction using utility function
        task_content = load_task_instruction(1, "NetLogo Abstract Syntax Extractor")

        instructions = f"{task_content}\n\n{self.persona_text}{ilsyn_refs}"

        input_text = f"""
<NETLOGO-SOURCE-CODE>
{netlogo_source_code}
</NETLOGO-SOURCE-CODE>
"""
        
        # Create single system_prompt variable for both API call and file generation
        system_prompt = f"{instructions}\n\n{input_text}"
        
        # Write input-instructions.md BEFORE API call for debugging
        write_input_instructions_before_api(base_output_dir, system_prompt)
        
        # Count input tokens exactly
        exact_input_tokens = self.count_input_tokens(instructions, input_text)
        
        try:
            # Create response using OpenAI Responses API
            api_config = get_reasoning_config("netlogo_abstract_syntax_extractor")
            # Update reasoning configuration with agent's settings
            if "reasoning" in api_config:
                api_config["reasoning"]["effort"] = self.reasoning_effort
                api_config["reasoning"]["summary"] = self.reasoning_summary
            api_config.update({
                "instructions": format_prompt_for_responses_api(system_prompt),
                "input": [{"role": "user", "content": system_prompt}]
            })
            
            timeout = AGENT_TIMEOUTS.get("netlogo_abstract_syntax_extractor")
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
                # Prefer API-provided output tokens for total_output_tokens
                total_output_tokens = api_output_tokens if api_output_tokens is not None else max((tokens_used or 0) - (input_tokens or 0), 0)
                visible_output_tokens = max((total_output_tokens or 0) - (reasoning_tokens or 0), 0)
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
        """Save parsing results using unified output file generation."""
        if not WRITE_FILES:
            return
            
        # Resolve base output directory (per-agent if provided)
        base_output_dir = output_dir if output_dir is not None else OUTPUT_DIR
        
        # Use unified function to write all output files
        write_all_output_files(
            output_dir=base_output_dir,
            results=results,
            agent_type="netlogo_abstract_syntax_extractor",
            base_name=base_name,
            model=self.model,
            timestamp=self.timestamp,
            reasoning_effort=self.reasoning_effort,
            step_number=step_number
        )
