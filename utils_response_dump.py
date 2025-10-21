#!/usr/bin/env python3
"""
Utilities to serialize OpenAI Responses API objects to JSON-serializable dicts,
write response.json files, and verify exact key equality against expected schema.
"""

import json
from typing import Any, Dict, Tuple, Set


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


def write_minimal_artifacts(output_dir, raw_response: Any, instructions_text: str = None) -> None:
    """Write minimal artifacts alongside the full response outputs.

    - output-raw_response.json: contains only the JSON value of raw_response
    - input-instructions.md: contains only the instructions text; if not provided,
      it is best-effort extracted from raw_response
    """
    try:
        # 1) output-raw_response.json (value only)
        raw_path = output_dir / "output-raw_response.json"
        # Ensure JSON-serializable; raw_response is expected to be a dict
        raw_path.write_text(json.dumps(raw_response if raw_response is not None else {}, indent=2, ensure_ascii=False), encoding="utf-8")

        # 2) input-instructions.md (text only)
        instr_value = instructions_text if isinstance(instructions_text, str) else _extract_instructions_from_raw(raw_response)
        instr_path = output_dir / "input-instructions.md"
        instr_path.write_text(instr_value or "", encoding="utf-8")
    except Exception as e:
        # Non-fatal: minimal artifacts are optional and must not break the run
        print(f"[WARNING] Failed to write minimal artifacts: {e}")

