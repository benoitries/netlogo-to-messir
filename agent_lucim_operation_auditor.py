#!/usr/bin/env python3
from typing import Dict, Any
import json
from utils_openai_client import create_and_wait, get_output_text, format_prompt_for_responses_api, get_openai_client_for_model, build_error_raw_payload, get_usage_tokens
from utils_config_constants import DEFAULT_MODEL, PERSONA_LUCIM_OPERATION_MODEL_AUDITOR, RULES_LUCIM_OPERATION_MODEL, OUTPUT_DIR
from utils_response_dump import write_input_instructions_before_api, serialize_response_to_dict
from utils_audit_core import extract_audit_core


def audit_operation_model(operation_model_raw_content: str, output_dir: str | None = None, model_name: str | None = None) -> Dict[str, Any]:
    """Audit Operation Model with LLM persona.

    Args:
        operation_model_raw_content: Raw content from output-data.json (may be JSON or other text)
        output_dir: Optional output directory (kept for interface parity; not used here)
        model_name: Optional model name to use (defaults to DEFAULT_MODEL if not provided)
    
    Note: Python auditor is called separately by orchestrator, not as a fallback.
    """
    try:
        persona_text = PERSONA_LUCIM_OPERATION_MODEL_AUDITOR.read_text(encoding="utf-8")
    except Exception:
        persona_text = ""
    try:
        rules_lucim_operation_model = RULES_LUCIM_OPERATION_MODEL.read_text(encoding="utf-8")
    except Exception:
        rules_lucim_operation_model = ""

    # Pass raw content to LLM (may be JSON or other text)
    om_content = operation_model_raw_content or ""
    instructions = f"{persona_text}\n\n{rules_lucim_operation_model}"
    input_text = f"""
<LUCIM-OPERATION-MODEL>
{om_content}
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
        # Store raw LLM response text directly (no JSON parsing)
        # extract_audit_core will handle the raw text content
        core = extract_audit_core(content)
        
        # Extract token usage from response (same as PlantUML auditor)
        usage = get_usage_tokens(resp)
        tokens_used = usage.get("total_tokens", 0)
        input_tokens = usage.get("input_tokens", 0)
        api_output_tokens = usage.get("output_tokens", 0)
        reasoning_tokens = usage.get("reasoning_tokens", 0)
        total_output_tokens = api_output_tokens if api_output_tokens is not None else 0
        visible_output_tokens = max((total_output_tokens or 0) - (reasoning_tokens or 0), 0)
        
        # Return raw audit data alongside derived fields, raw_response, and token metrics
        return {
            "reasoning_summary": "",  # Operation model auditor doesn't use reasoning summary
            "data": core["data"],
            "verdict": core["verdict"],
            "non-compliant-rules": core["non_compliant_rules"],
            "coverage": core["coverage"],
            "errors": core["errors"],
            "tokens_used": tokens_used,
            "input_tokens": input_tokens,
            "visible_output_tokens": visible_output_tokens,
            "raw_usage": usage,
            "reasoning_tokens": reasoning_tokens,
            "total_output_tokens": total_output_tokens,
            "raw_response": raw_response_serialized
        }
    except Exception as e:
        # No fallback: Python auditor is called separately by orchestrator
        return {
            "reasoning_summary": f"Error during model inference: {e}",
            "verdict": "non-compliant",
            "non-compliant-rules": [{"id": "OP-AUDIT-ERROR", "message": "LLM operation model audit failed"}],
            "coverage": {"total_rules_in_dsl": "0", "evaluated": [], "not_applicable": [], "missing_evaluation": []},
            "data": {},
            "errors": [f"LLM operation model audit error: {e}"],
            "tokens_used": 0,
            "input_tokens": 0,
            "visible_output_tokens": 0,
            "raw_usage": {},
            "reasoning_tokens": 0,
            "total_output_tokens": 0,
            "raw_response": build_error_raw_payload(e)
        }


