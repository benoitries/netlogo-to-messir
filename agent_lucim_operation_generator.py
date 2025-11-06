#!/usr/bin/env python3
"""
NetLogo LUCIM Operation Model Generator Agent using OpenAI models
Generates / Corrects LUCIM operation model from NetLogo source using OpenAI models.
"""

import os
import json
import datetime
import pathlib
import tiktoken
from typing import Dict, Any
from google.adk.agents import LlmAgent
from openai import OpenAI
from utils_response_dump import serialize_response_to_dict, write_input_instructions_before_api, write_all_output_files

from utils_config_constants import (
    PERSONA_LUCIM_OPERATION_MODEL_GENERATOR, OUTPUT_DIR,
    get_reasoning_config, DEFAULT_MODEL, RULES_LUCIM_OPERATION_MODEL)
from utils_path import sanitize_agent_name




class LucimOperationModelGeneratorAgent(LlmAgent):
    model: str = DEFAULT_MODEL
    timestamp: str = ""
    name: str = "NetLogo LUCIM Operation Model Generator"

    client: OpenAI = None
    reasoning_effort: str = "medium"
    reasoning_summary: str = "auto"
    text_verbosity: str = "medium"
    persona_path: str = ""
    persona_text: str = ""
    lucim_rules_path: str = ""
    lucim_rules_text: str = ""

    def __init__(self, model_name: str = DEFAULT_MODEL, external_timestamp: str = None):
        super().__init__(
            name=f"netlogo_lucim_operation_model_generator_agent_{sanitize_agent_name(model_name)}",
            description="LUCIM Operation Model Generator agent for NetLogo models"
        )
        self.model = model_name
        self.timestamp = external_timestamp or datetime.datetime.now().strftime("%Y%m%d_%H%M")
        # Configure OpenAI client with automatic provider detection based on model
        from utils_openai_client import get_openai_client_for_model
        self.client = get_openai_client_for_model(self.model)
        try:
            self.persona_path = str(PERSONA_LUCIM_OPERATION_MODEL_GENERATOR)
            self.persona_text = pathlib.Path(self.persona_path).read_text(encoding="utf-8")
        except Exception:
            self.persona_text = ""
        try:
            self.lucim_rules_path = str(RULES_LUCIM_OPERATION_MODEL)
            self.lucim_rules_text = pathlib.Path(self.lucim_rules_path).read_text(encoding="utf-8")
        except Exception:
            self.lucim_rules_text = ""

    def update_reasoning_config(self, reasoning_effort: str, reasoning_summary: str):
        self.reasoning_effort = reasoning_effort
        self.reasoning_summary = reasoning_summary

    def update_text_config(self, text_verbosity: str):
        self.text_verbosity = text_verbosity

    def update_persona_path(self, persona_path: str) -> None:
        if not persona_path:
            return
        self.persona_path = persona_path
        try:
            self.persona_text = pathlib.Path(persona_path).read_text(encoding="utf-8")
        except Exception:
            self.persona_text = ""

    def update_lucim_rules_path(self, rules_path: str) -> None:
        if not rules_path:
            return
        self.lucim_rules_path = rules_path
        try:
            self.lucim_rules_text = pathlib.Path(rules_path).read_text(encoding="utf-8")
        except Exception:
            self.lucim_rules_text = ""

    def count_input_tokens(self, instructions: str, input_text: str) -> int:
        try:
            try:
                encoding = tiktoken.encoding_for_model(self.model)
            except Exception:
                encoding = tiktoken.get_encoding("cl100k_base")
            full_input = f"{instructions}\n\n{input_text}"
            token_count = len(encoding.encode(full_input))
            return token_count
        except Exception:
            full_input = f"{instructions}\n\n{input_text}"
            estimated_tokens = len(full_input) // 4
            return estimated_tokens

    def generate_lucim_operation_model(
        self,
        netlogo_source_code: str,
        netlogo_lucim_mapping: str,
        auditor_feedback: Dict[str, Any],
        previous_operation_model: Dict[str, Any] | None,
        output_dir: str = None,
    ) -> Dict[str, Any]:
        """
        Generate / Correct LUCIM operation model
        """
        # Lazy-import heavy client utilities with retry to avoid transient FS timeouts
        def _import_utils_openai_client():
            import time as _time
            last_err = None
            for _ in range(3):
                try:
                    from utils_openai_client import (
                        create_and_wait as _create_and_wait,
                        get_output_text as _get_output_text,
                        get_reasoning_summary as _get_reasoning_summary,
                        get_usage_tokens as _get_usage_tokens,
                        format_prompt_for_responses_api as _format_prompt_for_responses_api,
                    )
                    return _create_and_wait, _get_output_text, _get_reasoning_summary, _get_usage_tokens, _format_prompt_for_responses_api
                except TimeoutError as e:  # Errno 60 on network FS
                    last_err = e
                    _time.sleep(0.5)
                except Exception as e:
                    last_err = e
                    break
            raise last_err if last_err else RuntimeError("Failed to import utils_openai_client")

        create_and_wait, get_output_text, get_reasoning_summary, get_usage_tokens, format_prompt_for_responses_api = _import_utils_openai_client()
        if not netlogo_source_code or netlogo_source_code.strip() == "":
            return {
                "reasoning_summary": "MISSING MANDATORY INPUT: NetLogo source code is required",
                "data": None,
                "errors": ["MANDATORY INPUT MISSING: NetLogo source code must be provided"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        if not netlogo_lucim_mapping or netlogo_lucim_mapping.strip() == "":
            return {
                "reasoning_summary": "MISSING MANDATORY INPUT: NetLogo to LUCIM mapping is required",
                "data": None,
                "errors": ["MANDATORY INPUT MISSING: NetLogo to LUCIM mapping must be provided"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        if not self.persona_text or self.persona_text.strip() == "":
            return {
                "reasoning_summary": "MISSING MANDATORY INPUT: Persona file is required",
                "data": None,
                "errors": ["MANDATORY INPUT MISSING: Persona PSN_LUCIM_Operation_Model_Generator.md must be provided"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }

        instructions = (
            f"{self.persona_text}\n\n"
            f"{netlogo_lucim_mapping}\n\n"
            f"{self.lucim_rules_text}\n\n"
        )
        input_text = f"""

<NETLOGO-SOURCE-CODE>
```
{netlogo_source_code}
```
</NETLOGO-SOURCE-CODE>

"""
        # Always include auditor report and previous model blocks (empty on first call)
        try:
            auditor_json = json.dumps(auditor_feedback, indent=2) if isinstance(auditor_feedback, dict) and auditor_feedback else "{}"
        except Exception:
            auditor_json = "{}"
        input_text += ("\n<AUDIT-REPORT>\n" "```json\n" + auditor_json + "\n```\n" "</AUDIT-REPORT>\n")

        try:
            prev_model_json = json.dumps(previous_operation_model, indent=2) if previous_operation_model is not None else "{}"
        except Exception:
            prev_model_json = "{}"
        input_text += (
            "\n<PREVIOUS-LUCIM-OPERATION-MODEL>\n"
            "```json\n" + prev_model_json + "\n```\n"
            "</PREVIOUS-LUCIM-OPERATION-MODEL>\n"
        )
        system_prompt = f"{instructions}\n\n{input_text}"
        base_output_dir = output_dir if output_dir is not None else OUTPUT_DIR
        write_input_instructions_before_api(base_output_dir, system_prompt)

        exact_input_tokens = self.count_input_tokens(instructions, input_text)
        try:
            api_config = get_reasoning_config("lucim_operation_model_generator")
            # Force the run-selected model (overrides DEFAULT_MODEL from configs)
            api_config["model"] = self.model
            if "reasoning" in api_config:
                api_config["reasoning"]["effort"] = self.reasoning_effort
                api_config["reasoning"]["summary"] = self.reasoning_summary
            api_config.update({
                "instructions": format_prompt_for_responses_api(system_prompt),
                "input": [{"role": "user", "content": system_prompt}]
            })
            from utils_config_constants import AGENT_TIMEOUTS
            timeout = AGENT_TIMEOUTS.get("lucim_operation_model_generator")
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
                if content_clean.startswith("```json"):
                    content_clean = content_clean.replace("```json", "").replace("```", "").strip()
                elif content_clean.startswith("```"):
                    content_clean = content_clean.replace("```", "").strip()
                response_data = json.loads(content_clean)
                operation_model = {}
                if isinstance(response_data, dict):
                    if "data" in response_data and isinstance(response_data["data"], dict):
                        operation_model = response_data["data"]
                    else:
                        operation_model = response_data
                usage = get_usage_tokens(response, exact_input_tokens=exact_input_tokens)
                tokens_used = usage.get("total_tokens", 0)
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                reasoning_tokens = usage.get("reasoning_tokens", 0)
                visible_output_tokens = max((output_tokens or 0) - (reasoning_tokens or 0), 0)
                total_output_tokens = visible_output_tokens + (reasoning_tokens or 0)
                return {
                    "reasoning_summary": reasoning_summary,
                    "data": operation_model,
                    "errors": [],
                    "tokens_used": tokens_used,
                    "input_tokens": input_tokens,
                    "visible_output_tokens": visible_output_tokens,
                    "raw_usage": usage,
                    "reasoning_tokens": reasoning_tokens,
                    "total_output_tokens": total_output_tokens,
                    "raw_response": raw_response_serialized
                }
            except json.JSONDecodeError as e:
                return {
                    "reasoning_summary": reasoning_summary,
                    "data": None,
                    "errors": [f"Failed to parse LUCIM operation model JSON: {e}", f"Raw response: {content[:200]}..."],
                    "tokens_used": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "raw_response": raw_response_serialized
                }
        except Exception as e:
            from utils_openai_client import build_error_raw_payload
            return {
                "reasoning_summary": f"Error during model inference: {e}",
                "data": None,
                "errors": [f"Model inference error: {e}", f"Model used: {self.model}"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "raw_response": build_error_raw_payload(e)
            }

    def save_results(self, results: Dict[str, Any], base_name: str, model_name: str, step_number = None, output_dir = None):
        if output_dir is None:
            output_dir = OUTPUT_DIR
        write_all_output_files(
            output_dir=output_dir,
            results=results,
            agent_type="lucim_operation_model_generator",
            base_name=base_name,
            model=self.model,
            timestamp=self.timestamp,
            reasoning_effort=self.reasoning_effort,
            step_number=step_number
        )



