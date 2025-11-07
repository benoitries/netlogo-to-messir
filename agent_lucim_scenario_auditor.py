#!/usr/bin/env python3
from typing import Dict, Any
import json
from openai import OpenAI
from utils_openai_client import create_and_wait, get_output_text, format_prompt_for_responses_api, get_openai_client_for_model, build_error_raw_payload
from utils_config_constants import DEFAULT_MODEL, PERSONA_LUCIM_SCENARIO_AUDITOR, OUTPUT_DIR, RULES_LUCIM_SCENARIO
from utils_response_dump import write_input_instructions_before_api, serialize_response_to_dict
from utils_audit_scenario import audit_scenario as _py_audit_scenario
from utils_audit_core import extract_audit_core


def audit_scenario_text(scenario_text: str, output_dir: str | None = None, model_name: str | None = None) -> Dict[str, Any]:
    """Audit Step 2 (Scenario) with LLM persona; fallback to deterministic Python.

    Args:
        scenario_text: Textual scenario serialization (mandatory)
        output_dir: Optional output directory (kept for interface parity; not used here)
        model_name: Optional model name to use (defaults to DEFAULT_MODEL if not provided)
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

    scen_text = scenario_text or ""
    instructions = f"{persona_text}\n\n{rules_text}".strip()
    input_text = f"""
<SCENARIO-TEXT>
{scen_text}
</SCENARIO-TEXT>
"""
    system_prompt = f"{instructions}\n\n{input_text}"
    try:
        # Persist exact prompt before API call (prefer caller-provided folder)
        target_dir = output_dir if isinstance(output_dir, str) and output_dir else OUTPUT_DIR
        write_input_instructions_before_api(target_dir, system_prompt)
    except Exception:
        pass

    # Call LLM
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
        core = extract_audit_core(data)
        return {
            "data": core["data"],
            "verdict": core["verdict"],
            "non-compliant-rules": core["non_compliant_rules"],
            "coverage": core["coverage"],
            "errors": core["errors"],
            "raw_response": raw_response_serialized
        }
    except Exception as e:
        # Fallback to deterministic Python auditor
        try:
            py_result = _py_audit_scenario(scen_text)
            core = extract_audit_core(py_result)
            return {
                "data": core["data"],
                "verdict": core["verdict"],
                "non-compliant-rules": core["non_compliant_rules"],
                "coverage": core["coverage"],
                "errors": core["errors"],
                "raw_response": build_error_raw_payload(e)
            }
        except Exception as py_e:
            return {
                "verdict": "non-compliant",
                "non-compliant-rules": [{"id": "SCEN-AUDIT-ERROR", "message": "Scenario audit failed"}],
                "coverage": {"total_rules_in_dsl": "0", "evaluated": [], "not_applicable": [], "missing_evaluation": []},
                "data": {},
                "errors": [f"Scenario audit error: {py_e}"],
                "raw_response": build_error_raw_payload(py_e)
            }


