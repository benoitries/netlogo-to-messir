#!/usr/bin/env python3
from typing import Dict, Any
import json
from openai import OpenAI
from utils_openai_client import create_and_wait, get_output_text, format_prompt_for_responses_api
from utils_task_loader import load_task_instruction
from utils_auditor_schema import normalize_auditor_like_response
from utils_config_constants import LUCIM_RULES_FILE, DEFAULT_MODEL, OPENAI_API_KEY
from utils_audit_scenario import audit_scenario as _py_audit_scenario


def audit_scenario_text(scenario_text: str) -> Dict[str, Any]:
    """Audit Step 2 (Scenario) with LLM persona; fallback to deterministic Python."""
    # Build prompt: TASK step 2 + persona + DSL + <SCENARIO-TEXT>
    try:
        task_content = load_task_instruction(2, "LUCIM Scenario Auditor (step 2)")
    except Exception:
        task_content = ""
    try:
        # Use dedicated Scenario auditor persona
        persona_text = (LUCIM_RULES_FILE.parent / "PSN_LUCIM_Scenario_Auditor.md").read_text(encoding="utf-8")
    except Exception:
        persona_text = ""
    try:
        lucim_dsl_text = LUCIM_RULES_FILE.read_text(encoding="utf-8")
    except Exception:
        lucim_dsl_text = ""

    scen_text = scenario_text or ""
    instructions = f"{task_content}\n\n{persona_text}\n\n{lucim_dsl_text}"
    input_text = f"""
<SCENARIO-TEXT>
{scen_text}
</SCENARIO-TEXT>
"""
    system_prompt = f"{instructions}\n\n{input_text}"

    # Call LLM
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        api_config = {
            "model": DEFAULT_MODEL,
            "instructions": format_prompt_for_responses_api(system_prompt),
            "input": [{"role": "user", "content": system_prompt}],
        }
        resp = create_and_wait(client, api_config)
        content = get_output_text(resp) or ""
        content_clean = content.strip()
        if content_clean.startswith("```json"):
            content_clean = content_clean.replace("```json", "").replace("```", "").strip()
        elif content_clean.startswith("```"):
            content_clean = content_clean.replace("```", "").strip()
        data = json.loads(content_clean)
        normalized = normalize_auditor_like_response(data).get("data") or {}
        return normalized
    except Exception:
        # Fallback to deterministic Python auditor
        try:
            return _py_audit_scenario(scen_text)
        except Exception:
            return {"verdict": "non-compliant", "non-compliant-rules": [{"id": "SCEN-AUDIT-ERROR", "message": "Scenario audit failed"}], "coverage": {"total_rules_in_dsl": "0", "evaluated": [], "not_applicable": [], "missing_evaluation": []}}


