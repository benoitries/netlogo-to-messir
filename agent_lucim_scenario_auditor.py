#!/usr/bin/env python3
from typing import Dict, Any
import json
from openai import OpenAI
from utils_openai_client import create_and_wait, get_output_text, format_prompt_for_responses_api, get_openai_client_for_model, build_error_raw_payload, get_usage_tokens
from utils_config_constants import DEFAULT_MODEL, PERSONA_LUCIM_SCENARIO_AUDITOR, OUTPUT_DIR, RULES_LUCIM_SCENARIO
from utils_response_dump import write_input_instructions_before_api, serialize_response_to_dict
from utils_audit_core import extract_audit_core


def audit_scenario_text(
    scenario_text: str,
    lucim_operation_model: Dict[str, Any] | str,
    output_dir: str,
    model_name: str
) -> Dict[str, Any]:
    """Audit Step 2 (Scenario) with LLM persona.

    Args:
        scenario_text: Raw content from output-data.json (may be JSON or other text)
        lucim_operation_model: LUCIM operation model (mandatory, matches generator context)
        output_dir: Output directory (mandatory)
        model_name: Model name to use (mandatory)
    
    Note: Python auditor is called separately by orchestrator, not as a fallback.
    """
    # Build prompt: persona + rules + <SCENARIO-TEXT>
    try:
        # Use dedicated Scenario auditor persona
        persona_text = PERSONA_LUCIM_SCENARIO_AUDITOR.read_text(encoding="utf-8")
    except Exception:
        persona_text = ""
    try:
        rules_text = RULES_LUCIM_SCENARIO.read_text(encoding="utf-8")
    except Exception:
        rules_text = ""

    # Pass raw content to LLM (may be JSON or other text)
    scen_text = scenario_text or ""
    instructions = f"{persona_text}\n\n{rules_text}".strip()
    
    # Build input_text matching generator structure: LUCIM-OPERATION-MODEL + SCENARIO-TEXT
    # Both blocks are mandatory (matching generator structure)
    # Use raw text copy without json.dumps or markdown fences (same as generator)
    if isinstance(lucim_operation_model, str):
        operation_model_text = lucim_operation_model
    else:
        operation_model_text = str(lucim_operation_model)
    
    input_text = f"""
<LUCIM-OPERATION-MODEL>
{operation_model_text}
</LUCIM-OPERATION-MODEL>

<SCENARIO-TEXT>
{scen_text}
</SCENARIO-TEXT>
"""
    system_prompt = f"{instructions}\n\n{input_text}"
    try:
        # Persist exact prompt before API call
        write_input_instructions_before_api(output_dir, system_prompt)
    except Exception:
        pass

    # Call LLM
    try:
        # Use provided model (mandatory parameter)
        client = get_openai_client_for_model(model_name)
        api_config = {
            "model": model_name,
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
        
        return {
            "reasoning_summary": "",  # Scenario auditor doesn't use reasoning summary
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
            "non-compliant-rules": [{"id": "SCEN-AUDIT-ERROR", "message": "LLM scenario audit failed"}],
            "coverage": {"total_rules_in_dsl": "0", "evaluated": [], "not_applicable": [], "missing_evaluation": []},
            "data": {},
            "errors": [f"LLM scenario audit error: {e}"],
            "tokens_used": 0,
            "input_tokens": 0,
            "visible_output_tokens": 0,
            "raw_usage": {},
            "reasoning_tokens": 0,
            "total_output_tokens": 0,
            "raw_response": build_error_raw_payload(e)
        }


