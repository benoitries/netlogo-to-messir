#!/usr/bin/env python3
from typing import Dict, Any
import json
from openai import OpenAI
from utils_openai_client import create_and_wait, get_output_text, format_prompt_for_responses_api
from utils_task_loader import load_task_instruction
from utils_auditor_schema import normalize_auditor_like_response
from utils_config_constants import LUCIM_RULES_FILE, DEFAULT_MODEL, OPENAI_API_KEY
from utils_audit_operation_model import audit_environment as _py_audit_environment


def audit_environment_model(env_data: Dict[str, Any]) -> Dict[str, Any]:
    """Audit Operation Model (formerly Environment) with LLM persona; fallback to deterministic Python."""
    try:
        task_content = load_task_instruction(1, "LUCIM Operation Model Auditor (step 1)")
    except Exception:
        task_content = ""
    try:
        persona_text = (LUCIM_RULES_FILE.parent / "PSN_LUCIM_Operation_Model_Auditor.md").read_text(encoding="utf-8")
    except Exception:
        persona_text = ""
    try:
        lucim_dsl_text = LUCIM_RULES_FILE.read_text(encoding="utf-8")
    except Exception:
        lucim_dsl_text = ""

    env_json = json.dumps(env_data or {}, ensure_ascii=False, indent=2)
    instructions = f"{task_content}\n\n{persona_text}\n\n{lucim_dsl_text}"
    input_text = f"""
<OPERATION-MODEL>
```json
{env_json}
```
</OPERATION-MODEL>
"""
    system_prompt = f"{instructions}\n\n{input_text}"

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
        try:
            return _py_audit_environment(env_data if isinstance(env_data, dict) else {})
        except Exception:
            return {"verdict": "non-compliant", "non-compliant-rules": [{"id": "OP-AUDIT-ERROR", "message": "Operation model audit failed"}], "coverage": {"total_rules_in_dsl": "0", "evaluated": [], "not_applicable": [], "missing_evaluation": []}}


