#!/usr/bin/env python3
"""
NetLogo Semantics Agent using OpenAI models
Builds a semantic state machine exclusively from IL-SEM references and UI artifacts.
"""

import os
import json
import datetime
import pathlib
import tiktoken
from typing import Dict, Any, List, Optional
from config import (
    PERSONA_SEMANTICS_PARSER, OUTPUT_DIR, 
    AGENT_VERSION_SEMANTICS_PARSER, get_reasoning_config,
    validate_agent_response, DEFAULT_MODEL
)

from google.adk.agents import LlmAgent
from openai import OpenAI
from openai_client_utils import create_and_wait, get_output_text, get_reasoning_summary, get_usage_tokens
from response_dump_utils import serialize_response_to_dict, verify_exact_keys, write_minimal_artifacts
from response_schema_expected import expected_keys_for_agent
from logging_utils import write_reasoning_md_from_payload

# Configuration
PERSONA_FILE = PERSONA_SEMANTICS_PARSER
WRITE_FILES = True

# Load persona
persona = PERSONA_FILE.read_text(encoding="utf-8")

# Get agent version from config
AGENT_VERSION = AGENT_VERSION_SEMANTICS_PARSER

def sanitize_model_name(model_name: str) -> str:
    """Sanitize model name by replacing hyphens with underscores for valid identifier."""
    return model_name.replace("-", "_")

class NetLogoSemanticsParserAgent(LlmAgent):
    model: str = DEFAULT_MODEL
    timestamp: str = ""
    name: str = "NetLogo Semantics Parser"
    
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
            name=f"netlogo_semantics_agent_{sanitized_name}",
            description="Semantics-based agent building state machine from IL-SEM and UI (no AST)"
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

    
    def parse_from_ilsem_and_ui(self, ui_image_paths: List[str], base_name: str) -> Dict[str, Any]:
        """
        Build semantics using only IL-SEM mapping/description and two NetLogo interface images.
        This method is the canonical Stage 2 entry point (no AST, no raw code).
        """
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
        input_text = f"""
Filename: {base_name}

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

        exact_input_tokens = self.count_input_tokens(instructions, input_text)
        try:
            api_config = get_reasoning_config("semantics_parser")
            if "reasoning" in api_config:
                api_config["reasoning"]["effort"] = self.reasoning_effort
                api_config["reasoning"]["summary"] = self.reasoning_summary
            api_config.update({
                "instructions": instructions,
                "input": input_text
            })

            from config import AGENT_TIMEOUTS
            timeout = AGENT_TIMEOUTS.get("semantics_parser")
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
                    try:
                        return json.loads(s)
                    except Exception:
                        pass
                    # Attempt to locate the first JSON object within the text
                    start = s.find("{")
                    end = s.rfind("}")
                    if start != -1 and end != -1 and end > start:
                        candidate = s[start:end+1].strip()
                        try:
                            return json.loads(candidate)
                        except Exception:
                            # Try to narrow to a block that begins with {"data":
                            anchor = s.find('{"data"')
                            if anchor != -1:
                                end2 = s.find("\n\n", anchor)
                                end2 = end if end2 == -1 else end2
                                candidate2 = s[anchor:end2].strip()
                                try:
                                    return json.loads(candidate2)
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
                api_total_output_tokens = max((tokens_used or 0) - (input_tokens or 0), 0)
                visible_output_tokens = max((api_total_output_tokens or api_output_tokens or 0) - (reasoning_tokens or 0), 0)
                total_output_tokens = api_total_output_tokens if api_total_output_tokens is not None else (visible_output_tokens + (reasoning_tokens or 0))
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
        
    def parse_netlogo_ast(self, ast: Dict[str, Any], filename: str = "input.nlogo") -> Dict[str, Any]:
        """Deprecated. Stage 2 no longer accepts AST. Use parse_from_ilsem_and_ui()."""
        raise NotImplementedError("Semantics Parser no longer accepts AST input. Use parse_from_ilsem_and_ui(ui_images, base_name).")
    
    def parse_ast_to_state_machine(self, ast_json_str: Any, filename: str = "input.nlogo") -> Dict[str, Any]:
        """Deprecated. Stage 2 no longer accepts AST. Use parse_from_ilsem_and_ui()."""
        raise NotImplementedError("Semantics Parser no longer accepts AST input. Use parse_from_ilsem_and_ui(ui_images, base_name).")

    def parse_netlogo_code_direct(self, code: str, filename: str = "input.nlogo") -> Dict[str, Any]:
        """Deprecated. Stage 2 no longer accepts raw code. Use parse_from_ilsem_and_ui()."""
        raise NotImplementedError("Semantics Parser no longer accepts raw code input. Use parse_from_ilsem_and_ui(ui_images, base_name).")
    

    
    def save_results(self, results: Dict[str, Any], base_name: str, model_name: str, step_number = None, output_dir = None):
        """Save parsing results to a single JSON file."""
        if not WRITE_FILES:
            return
            
        # New format: base-name_timestamp_AI-model_step_agent-name_version_reasoning-suffix_rest
        agent_name = "semantics_parser"
        # Use the agent's current reasoning level instead of global config
        reasoning_suffix = f"reasoning-{self.reasoning_effort}-{self.reasoning_summary}"
        
        # Resolve base output directory (per-agent if provided)
        base_output_dir = output_dir if output_dir is not None else OUTPUT_DIR
        # Save complete response as single JSON file (simplified)
        json_file = base_output_dir / "output-response.json"
        
        # Create complete response structure
        complete_response = {
            "agent_type": "semantics_parser",
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
        validation_errors = validate_agent_response("semantics_parser", complete_response)
        if validation_errors:
            print(f"[WARNING] Validation errors in semantics parser response: {validation_errors}")
        
        # Verify exact keys before saving
        expected_keys = expected_keys_for_agent("semantics_parser")
        ok, missing, extra = verify_exact_keys(complete_response, expected_keys)
        # Debug logging to diagnose schema/key mismatches and write targets
        try:
            print(f"[DEBUG] semantics_parser.save_results WRITE_FILES={WRITE_FILES}")
            print(f"[DEBUG] semantics_parser.save_results output_dir={base_output_dir}")
            print(f"[DEBUG] semantics_parser.save_results base_name={base_name} model={self.model} step_number={step_number}")
            print(f"[DEBUG] semantics_parser emitted keys: {sorted(list(complete_response.keys()))}")
            print(f"[DEBUG] semantics_parser expected keys: {sorted(list(expected_keys))}")
            if not ok:
                print(f"[ERROR] semantics_parser missing keys: {sorted(list(missing))}")
                print(f"[ERROR] semantics_parser extra keys: {sorted(list(extra))}")
        except Exception as e:
            print(f"[WARNING] Failed to print debug schema info (semantics_parser): {e}")
        if not ok:
            raise ValueError(f"response.json keys mismatch for semantics_parser. Missing: {sorted(missing)} Extra: {sorted(extra)}")

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
        
        # Save data field as separate file
        data_file = base_output_dir / "output-data.json"
        if results.get("data"):
            data_file.write_text(json.dumps(results["data"], indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"OK: {base_name} -> output-data.json")
        else:
            print(f"WARNING: No data to save for {base_name}")

        # Write minimal artifacts (non-breaking additions)
        write_minimal_artifacts(base_output_dir, results.get("raw_response"))

