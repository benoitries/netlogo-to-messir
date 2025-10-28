#!/usr/bin/env python3
"""
NetLogo Behavior Extractor using OpenAI models
Extracts behavioral patterns from NetLogo semantics using IL-SEM references and UI artifacts.
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

# Load persona
persona = PERSONA_FILE.read_text(encoding="utf-8")


def sanitize_model_name(model_name: str) -> str:
    """Sanitize model name by replacing hyphens with underscores for valid identifier."""
    return model_name.replace("-", "_")

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
    
    def __init__(self, model_name: str = DEFAULT_MODEL, external_timestamp: str = None):
        sanitized_name = sanitize_model_name(model_name)
        super().__init__(
            name=f"netlogo_behavior_extractor_agent_{sanitized_name}",
            description="Behavior extraction agent building state machine from IL-SEM and UI (no AST)"
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

    
    def parse_from_ilsem_and_ui(self, ui_image_paths: List[str], base_name: str, base_output_dir: str = None) -> Dict[str, Any]:
        """
        Build semantics using only IL-SEM mapping/description and two NetLogo interface images.
        This method is the canonical Stage 2 entry point (no AST, no raw code).
        """
        # Resolve base output directory (per-agent if provided)
        if base_output_dir is None:
            base_output_dir = OUTPUT_DIR
        
        # Base persona + IL-SEM references
        instructions_sections: List[str] = [persona]
        il_sem_info: List[str] = []
        try:
            if self.il_sem_mapping_path and pathlib.Path(self.il_sem_mapping_path).exists():
                mapping_text = pathlib.Path(self.il_sem_mapping_path).read_text(encoding="utf-8")
                il_sem_info.append(f"\n# IL-SEM Mapping (external reference)\n{mapping_text}")
            else:
                if self.il_sem_mapping_path:
                    print(f"[WARNING] IL-SEM mapping file not found: {self.il_sem_mapping_path}")
            if self.il_sem_description_path and pathlib.Path(self.il_sem_description_path).exists():
                desc_text = pathlib.Path(self.il_sem_description_path).read_text(encoding="utf-8")
                il_sem_info.append(f"\n# IL-SEM Description (external reference)\n{desc_text}")
            else:
                if self.il_sem_description_path:
                    print(f"[WARNING] IL-SEM description file not found: {self.il_sem_description_path}")
        except Exception as e:
            print(f"[WARNING] Failed to read IL-SEM files: {e}")
        if il_sem_info:
            instructions_sections.append("\n\n".join(il_sem_info))
            print("OK: Ingested IL-SEM reference files for semantics parsing (Stage 2)")

        # Prepare UI images references with absolute paths and sizes (best-effort)
        ui_entries: List[str] = []
        for p in ui_image_paths[:2]:
            try:
                pp = pathlib.Path(p)
                size_info = f"{pp.stat().st_size} bytes" if pp.exists() else "not found"
                ui_entries.append(f"- {pp.name} — abs: {pp.resolve()} — size: {size_info}")
            except Exception:
                ui_entries.append(f"- {p} — abs: (unresolved) — size: (unknown)")
        ui_images_text = "\n".join(ui_entries)
        if not ui_entries:
            print("[WARNING] No UI images provided to semantics parser (expected two)")
        
        instructions = "\n\n".join(instructions_sections)
        
        # Load TASK instruction using utility function
        task_content = load_task_instruction(2, "NetLogo Behavior Extractor")
        
        input_text = f"""
Filename: {base_name}
{task_content}
# Inputs Provided (Stage 2 canonical)
- IL-SEM Mapping: {self.il_sem_mapping_path if self.il_sem_mapping_path else '(unset)'}
- IL-SEM Description: {self.il_sem_description_path if self.il_sem_description_path else '(unset)'}
- UI Images (absolute paths and sizes):
{ui_images_text if ui_images_text else '- (none provided)'}

# Strict Processing Rules (override persona if conflicting)
1) Do NOT expect NetLogo source code files (.nlogo or markdown). You do not receive any code at Stage 2.
2) Treat the UI image paths listed above as provided and accessible; do NOT emit "missing_ui" errors for these entries.
3) Build a state machine only from IL-SEM mapping/description and from the UI artifacts (widgets, buttons, sliders) inferred by their filenames; if ambiguous, output the best-effort minimal state machine.
4) If information is insufficient for a rich model, return a minimal, valid state machine schema with placeholders.
"""

        # Create single system_prompt variable for both API call and file generation
        system_prompt = f"{instructions}\n\n{input_text}"
        
        # Write input-instructions.md BEFORE API call for debugging
        write_input_instructions_before_api(base_output_dir, system_prompt)

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
                    "raw_response": raw_response_serialized
                }

            try:
                content_clean = content.strip()
                # Handle fenced blocks first
                if content_clean.startswith("```json"):
                    content_clean = content_clean.replace("```json", "").replace("```", "").strip()
                elif content_clean.startswith("```"):
                    content_clean = content_clean.replace("```", "").strip()

                def _parse_best_effort_json(s: str) -> Any:
                    """Best-effort JSON extraction when prose wraps a JSON object.
                    Tries direct loads; if it fails, extracts the first top-level JSON object substring.
                    """
                    # Clean JavaScript-style comments from JSON
                    import re
                    s_clean = re.sub(r'//.*$', '', s, flags=re.MULTILINE)
                    
                    try:
                        return json.loads(s_clean)
                    except Exception:
                        pass
                    # Attempt to locate the first JSON object within the text
                    start = s.find("{")
                    end = s.rfind("}")
                    if start != -1 and end != -1 and end > start:
                        candidate = s[start:end+1].strip()
                        # Clean comments from candidate
                        candidate_clean = re.sub(r'//.*$', '', candidate, flags=re.MULTILINE)
                        try:
                            return json.loads(candidate_clean)
                        except Exception:
                            # Try to narrow to a block that begins with {"data":
                            anchor = s.find('{"data"')
                            if anchor != -1:
                                end2 = s.find("\n\n", anchor)
                                end2 = end if end2 == -1 else end2
                                candidate2 = s[anchor:end2].strip()
                                # Clean comments from candidate2
                                candidate2_clean = re.sub(r'//.*$', '', candidate2, flags=re.MULTILINE)
                                try:
                                    return json.loads(candidate2_clean)
                                except Exception:
                                    pass
                    # Give up; raise to caller
                    raise json.JSONDecodeError("Unable to parse JSON from response", s, 0)

                response_data = _parse_best_effort_json(content_clean)

                state_machine = {}
                if isinstance(response_data, dict):
                    if "data" in response_data and isinstance(response_data["data"], dict):
                        state_machine = response_data["data"]
                    else:
                        state_machine = response_data
                errors = response_data.get("errors", []) if isinstance(response_data, dict) else []

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
                    "data": state_machine,
                    "errors": errors,
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
                    "errors": [f"Failed to parse state machine JSON: {e}", f"Raw response: {content[:200]}..."],
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
            agent_type="netlogo_behavior_extractor",
            base_name=base_name,
            model=self.model,
            timestamp=self.timestamp,
            reasoning_effort=self.reasoning_effort,
            step_number=step_number
        )

