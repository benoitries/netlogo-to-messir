#!/usr/bin/env python3
from typing import Dict, Any
import json
from utils_openai_client import create_and_wait, get_output_text, format_prompt_for_responses_api, get_openai_client_for_model, build_error_raw_payload
from utils_auditor_schema import normalize_auditor_like_response
from utils_config_constants import DEFAULT_MODEL, PERSONA_LUCIM_OPERATION_MODEL_AUDITOR, RULES_LUCIM_OPERATION_MODEL, OUTPUT_DIR
from utils_response_dump import write_input_instructions_before_api, serialize_response_to_dict
from utils_audit_operation_model import audit_environment as _py_audit_environment


def audit_operation_model(operation_model_data: Dict[str, Any], output_dir: str | None = None, model_name: str | None = None) -> Dict[str, Any]:
    """Audit Operation Model  with LLM persona; fallback to deterministic Python.

    Args:
        operation_model_data: JSON Operation Model produced by the generator (mandatory)
        output_dir: Optional output directory (kept for interface parity; not used here)
        model_name: Optional model name to use (defaults to DEFAULT_MODEL if not provided)
    """
    try:
        persona_text = PERSONA_LUCIM_OPERATION_MODEL_AUDITOR.read_text(encoding="utf-8")
    except Exception:
        persona_text = ""
    try:
        rules_lucim_operation_model = RULES_LUCIM_OPERATION_MODEL.read_text(encoding="utf-8")
    except Exception:
        rules_lucim_operation_model = ""

    operation_model_json = json.dumps(operation_model_data or {}, ensure_ascii=False, indent=2)
    instructions = f"{persona_text}\n\n{rules_lucim_operation_model}"
    input_text = f"""
<LUCIM-OPERATION-MODEL>
```json
{operation_model_json}
```
</LUCIM-OPERATION-MODEL>
"""
    system_prompt = f"{instructions}\n\n{input_text}"
    try:
        # Persist exact prompt before API call (prefer caller-provided folder)
        target_dir = output_dir if isinstance(output_dir, str) and output_dir else OUTPUT_DIR
        write_input_instructions_before_api(target_dir, system_prompt)
    except Exception:
        pass

    try:
        # Use provided model or fallback to DEFAULT_MODEL
        effective_model = model_name if model_name else DEFAULT_MODEL
        client = get_openai_client_for_model(effective_model)
        api_config = {
            "model": effective_model,
            "instructions": format_prompt_for_responses_api(system_prompt),
            "input": [{"role": "user", "content": system_prompt}],
        }
        resp = create_and_wait(client, api_config)
        # Serialize raw response for output-raw_response.json
        raw_response_serialized = serialize_response_to_dict(resp)
        content = get_output_text(resp) or ""
        content_clean = content.strip()
        if content_clean.startswith("```json"):
            content_clean = content_clean.replace("```json", "").replace("```", "").strip()
        elif content_clean.startswith("```"):
            content_clean = content_clean.replace("```", "").strip()
        data = json.loads(content_clean)
        normalized = normalize_auditor_like_response(data).get("data") or {}
        # Return normalized audit result with raw_response included
        return {
            **normalized,
            "raw_response": raw_response_serialized
        }
    except Exception as e:
        try:
            # Fallback to Python deterministic audit
            py_result = _py_audit_environment(operation_model_data if isinstance(operation_model_data, dict) else {})
            # Include error raw payload for debugging
            return {
                **py_result,
                "raw_response": build_error_raw_payload(e)
            }
        except Exception as py_e:
            return {
                "verdict": "non-compliant",
                "non-compliant-rules": [{"id": "OP-AUDIT-ERROR", "message": "Operation model audit failed"}],
                "coverage": {"total_rules_in_dsl": "0", "evaluated": [], "not_applicable": [], "missing_evaluation": []},
                "raw_response": build_error_raw_payload(py_e)
            }


