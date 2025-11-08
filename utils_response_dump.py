#!/usr/bin/env python3
"""
Utilities to serialize OpenAI Responses API objects to JSON-serializable dicts,
write response.json files, and verify exact key equality against expected schema.
"""

import json
import pathlib
from pathlib import Path
from typing import Any, Dict, Tuple, Set, Optional


def _to_builtin(obj: Any) -> Any:
    """Best-effort conversion of arbitrary objects to JSON-serializable Python builtins.

    - Tries __dict__ and dataclass/asdict-like attributes
    - Recursively converts lists/tuples/sets/dicts
    - Falls back to str(obj) for unknown types
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (list, tuple, set)):
        return [_to_builtin(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _to_builtin(v) for k, v in obj.items()}

    # Try common attributes for SDK objects
    for attr in ("model_dump", "to_dict", "dict"):
        if hasattr(obj, attr) and callable(getattr(obj, attr)):
            try:
                data = getattr(obj, attr)()
                return _to_builtin(data)
            except Exception:
                pass

    # Try __dict__
    if hasattr(obj, "__dict__"):
        try:
            return _to_builtin(vars(obj))
        except Exception:
            pass

    # Fallback to string representation
    try:
        return str(obj)
    except Exception:
        return "<unserializable>"


def serialize_response_to_dict(response: Any) -> Dict[str, Any]:
    """Serialize an OpenAI Responses API object into a JSON-serializable dict."""
    try:
        return _to_builtin(response) or {}
    except Exception:
        return {"error": "failed to serialize response"}


def verify_exact_keys(emitted: Dict[str, Any], expected_keys: Set[str]) -> Tuple[bool, Set[str], Set[str]]:
    """Check exact key equality on the top-level dict.

    Returns (ok, missing, extra)
    """
    emitted_keys = set(emitted.keys())
    missing = expected_keys - emitted_keys
    extra = emitted_keys - expected_keys
    ok = not missing and not extra
    return ok, missing, extra


def write_response_json(path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")



def _extract_instructions_from_raw(raw_response: Any) -> str:
    """Best-effort extraction of the 'instructions' field from a serialized raw_response.

    Tries several common locations as different SDKs may structure objects differently.
    Returns an empty string if nothing is found.
    """
    try:
        if isinstance(raw_response, dict):
            # Direct top-level
            if isinstance(raw_response.get("instructions"), str):
                return raw_response.get("instructions") or ""
            # Nested common containers
            for key in ("request", "body", "metadata", "config", "params"):
                sub = raw_response.get(key)
                if isinstance(sub, dict) and isinstance(sub.get("instructions"), str):
                    return sub.get("instructions") or ""
    except Exception:
        pass
    return ""


def write_input_instructions_before_api(output_dir, system_prompt: str) -> None:
    """Write input-instructions.md file BEFORE making API call.
    
    This ensures the file is available for debugging even if the API call fails.
    
    Args:
        output_dir: Directory where to write the file (Path or str)
        system_prompt: Complete system prompt to write to file
    """
    try:
        # Ensure output_dir is a Path object
        if isinstance(output_dir, str):
            output_dir = Path(output_dir)
        instr_path = output_dir / "input-instructions.md"
        instr_path.write_text(system_prompt or "", encoding="utf-8")
        print(f"OK: Created input-instructions.md before API call")
    except Exception as e:
        # Non-fatal: file creation should not break the run
        print(f"[WARNING] Failed to write input-instructions.md before API call: {e}")


def extract_raw_text_from_raw_response_dict(raw_response: Dict[str, Any]) -> str:
    """Extract plain text content from a serialized raw_response dictionary.
    
    Handles multiple response formats from different LLM providers:
    - OpenAI/GPT-5 (Responses API): raw_response["output"][1]["content"][0]["text"]
    - OpenAI/GPT-5 (ChatCompletion): raw_response["choices"][0]["message"]["content"]
    - Gemini: raw_response["_gemini_response"]["candidates"][0]["content"]["parts"][0]["text"]
    - MistralAI/Llama via OpenRouter: raw_response["choices"][0]["message"]["content"] or raw_response["output"][1]["content"][0]["text"]
    
    Args:
        raw_response: Serialized response dictionary from serialize_response_to_dict()
    
    Returns:
        Plain text string from the LLM response, or empty string if extraction fails
    """
    if raw_response is None or not isinstance(raw_response, dict):
        return ""
    
    try:
        # 1) OpenAI Responses API structure: output[1].content[0].text
        # Usually output[0] is reasoning, output[1] is the message
        if 'output' in raw_response:
            output = raw_response.get('output')
            if isinstance(output, list):
                text_chunks = []
                for output_item in output:
                    if isinstance(output_item, dict):
                        content_list = output_item.get('content', [])
                        if isinstance(content_list, list):
                            for content_item in content_list:
                                if isinstance(content_item, dict):
                                    # Check for text field
                                    text_val = content_item.get('text')
                                    if isinstance(text_val, str):
                                        text_chunks.append(text_val)
                                elif isinstance(content_item, str):
                                    text_chunks.append(content_item)
                if text_chunks:
                    return "".join(text_chunks).strip()
        
        # 2) OpenAI ChatCompletion structure: choices[0].message.content
        if 'choices' in raw_response:
            choices = raw_response.get('choices')
            if isinstance(choices, list) and len(choices) > 0:
                first_choice = choices[0]
                if isinstance(first_choice, dict):
                    message = first_choice.get('message', {})
                    if isinstance(message, dict):
                        content_val = message.get('content')
                        if isinstance(content_val, str):
                            return content_val.strip()
        
        # 3) Gemini structure: _gemini_response.candidates[0].content.parts[0].text
        if '_gemini_response' in raw_response:
            gemini_resp = raw_response.get('_gemini_response')
            if isinstance(gemini_resp, dict):
                candidates = gemini_resp.get('candidates')
                if isinstance(candidates, list) and len(candidates) > 0:
                    candidate = candidates[0]
                    if isinstance(candidate, dict):
                        content = candidate.get('content')
                        if isinstance(content, dict):
                            parts = content.get('parts')
                            if isinstance(parts, list) and len(parts) > 0:
                                part = parts[0]
                                if isinstance(part, dict):
                                    text_val = part.get('text')
                                    if isinstance(text_val, str):
                                        return text_val.strip()
        
        # 4) Check nested structures (response, result, body)
        for key in ['response', 'result', 'body']:
            if key in raw_response:
                nested_text = extract_raw_text_from_raw_response_dict(raw_response[key])
                if nested_text:
                    return nested_text
        
    except (KeyError, IndexError, TypeError, AttributeError) as e:
        # Silently fail and return empty string
        pass
    
    return ""


def write_minimal_artifacts(output_dir, raw_response: Any, instructions_text: str = None) -> None:
    """Write minimal artifacts alongside the full response outputs.

    - output-response-raw.json: contains only the JSON value of raw_response
    - Note: input-instructions.md is now generated separately before API calls
    """
    try:
        # output-response-raw.json (value only)
        raw_path = output_dir / "output-response-raw.json"
        # Ensure JSON-serializable; raw_response is expected to be a dict
        raw_path.write_text(json.dumps(raw_response if raw_response is not None else {}, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        # Non-fatal: minimal artifacts are optional and must not break the run
        print(f"[WARNING] Failed to write minimal artifacts: {e}")


def write_all_output_files(
    output_dir: pathlib.Path,
    results: Dict[str, Any],
    agent_type: str,
    base_name: str,
    model: str,
    timestamp: str,
    reasoning_effort: str,
    step_number: Optional[int] = None,
    special_files: Optional[Dict[str, Any]] = None
) -> None:
    """Unified function to write all output files for any agent.
    
    Generates:
    - output-response-full.json (complete response structure)
    - output-reasoning.md (reasoning payload with token metrics)
    - output-data.json (data field only)
    - output-response-raw.json (raw API response)
    - Optional special files (.puml for agents 5 and 7)
    
    Args:
        output_dir: Directory where to write files
        results: Agent results dictionary
        agent_type: Type of agent (for validation and file naming)
        base_name: Base name for output files
        model: AI model name
        timestamp: Timestamp string
        reasoning_effort: Reasoning effort level
        step_number: Optional step number
        special_files: Optional dict with special file data (e.g., plantuml_diagram)
    """
    try:
        # Import here to avoid circular imports
        from utils_config_constants import expected_keys_for_agent, validate_agent_response
        from utils_logging import write_reasoning_md_from_payload
        from utils_plantuml import process_plantuml_file
        
        # Create complete response structure (includes raw_response)
        # If data is a string, try to parse it as JSON to avoid double-encoding
        data_value = results.get("data", "")
        if isinstance(data_value, str):
            try:
                data_value = json.loads(data_value)
            except (json.JSONDecodeError, TypeError):
                # If parsing fails, keep the string as-is
                pass
        
        complete_response = {
            "agent_type": agent_type,
            "model": model,
            "timestamp": timestamp,
            "base_name": base_name,
            "step_number": step_number,
            "reasoning_summary": results.get("reasoning_summary", "").replace("\\n", "\n"),
            "data": data_value,
            # Preserve None values for errors (standardized structure: None on success, list on failure)
            "errors": results.get("errors"),
            "tokens_used": results.get("tokens_used", 0),
            "input_tokens": results.get("input_tokens", 0),
            "total_output_tokens": results.get("total_output_tokens", 0),
            "reasoning_tokens": results.get("reasoning_tokens", 0),
            "visible_output_tokens": results.get("visible_output_tokens", max(0, results.get("total_output_tokens", 0) - results.get("reasoning_tokens", 0))),
            "raw_response": results.get("raw_response"),
        }
        
        # Validate response before saving
        validation_errors = validate_agent_response(agent_type, complete_response)
        if validation_errors:
            print(f"[WARNING] Validation errors in {agent_type} response: {validation_errors}")
        
        # Verify exact keys before saving
        expected_keys = expected_keys_for_agent(agent_type)
        ok, missing, extra = verify_exact_keys(complete_response, expected_keys)
        if not ok:
            raise ValueError(f"response.json keys mismatch for {agent_type}. Missing: {sorted(missing)} Extra: {sorted(extra)}")

        # 1) Write output-response-full.json
        json_file = output_dir / "output-response-full.json"
        json_file.write_text(json.dumps(complete_response, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"OK: {base_name} -> output-response-full.json")
        
        # 2) Write output-reasoning.md using centralized function
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
            output_dir=output_dir,
            agent_name=agent_type,
            base_name=base_name,
            model=model,
            timestamp=timestamp,
            reasoning_effort=reasoning_effort,
            step_number=step_number,
            payload=payload,
        )
        print(f"OK: {base_name} -> output-reasoning.md")
        
        # 3) Write output-data.json with standardized conditional structure
        # EITHER data value (string) if data is not null, OR errors values (string) if data is null
        data_file = output_dir / "output-data.json"
        data_value = results.get("data")
        errors_value = results.get("errors")
        
        if data_value is not None:
            # Success case: write data value as string
            if isinstance(data_value, str):
                data_file.write_text(data_value, encoding="utf-8")
            else:
                # Convert non-string data to string
                data_file.write_text(str(data_value), encoding="utf-8")
            print(f"OK: {base_name} -> output-data.json (data)")
        elif errors_value is not None:
            # Failure case: write errors values as string
            if isinstance(errors_value, str):
                data_file.write_text(errors_value, encoding="utf-8")
            elif isinstance(errors_value, list):
                # Convert list of errors to string representation
                errors_str = str(errors_value)
                data_file.write_text(errors_str, encoding="utf-8")
            else:
                # Convert other error types to string
                data_file.write_text(str(errors_value), encoding="utf-8")
            print(f"OK: {base_name} -> output-data.json (errors)")
        else:
            # Edge case: neither data nor errors provided
            print(f"WARNING: No data or errors to save for {base_name}, writing empty file")
            data_file.write_text("", encoding="utf-8")

        # 4) Write output-response-raw.json
        raw_path = output_dir / "output-response-raw.json"
        raw_path.write_text(json.dumps(results.get("raw_response") if results.get("raw_response") is not None else {}, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"OK: {base_name} -> output-response-raw.json")
        
        # 5) Handle special files (e.g., .puml for agents 5 and 7)
        if special_files:
            _write_special_files(output_dir, special_files, base_name, agent_type)
            
    except Exception as e:
        # Non-fatal: file generation should not break the run
        print(f"[WARNING] Failed to write output files for {agent_type}: {e}")


def _write_special_files(output_dir: pathlib.Path, special_files: Dict[str, Any], base_name: str, agent_type: str) -> None:
    """Write special files like .puml diagrams for specific agents."""
    try:
        from utils_plantuml import process_plantuml_file
        
        if "plantuml_diagram" in special_files:
            diagram_text = special_files["plantuml_diagram"]
            if diagram_text and "@startuml" in diagram_text and "@enduml" in diagram_text:
                puml_filename = "diagram.puml"
                puml_file = output_dir / puml_filename
                puml_file.write_text(diagram_text, encoding="utf-8")
                print(f"OK: {base_name} -> {puml_filename}")
                
                # Post-process the PlantUML file if requested
                if special_files.get("post_process", False):
                    try:
                        success = process_plantuml_file(puml_file)
                        if success:
                            print(f"✅ Post-processed PlantUML file: {puml_filename}")
                        else:
                            print(f"⚠️  Post-processing had issues for: {puml_filename}")
                    except Exception as e:
                        print(f"[WARNING] Post-processing failed for {puml_filename}: {e}")
                
                # Surface the path for orchestrator logging/downstream use
                if hasattr(special_files, '__setitem__'):
                    special_files["puml_file"] = str(puml_file)
            else:
                print("WARNING: Could not extract valid PlantUML diagram text to write .puml file")
                
    except Exception as e:
        print(f"[WARNING] Failed to write special files for {agent_type}: {e}")

