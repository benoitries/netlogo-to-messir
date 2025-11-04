#!/usr/bin/env python3
"""
NetLogo LUCIM Operation Synthesizer Agent using OpenAI models
Synthesizes LUCIM operation model concepts from NetLogo source using OpenAI models.
"""

import os
import json
import datetime
import pathlib
import tiktoken
from typing import Dict, Any
from google.adk.agents import LlmAgent
from openai import OpenAI
from utils_openai_client import create_and_wait, get_output_text, get_reasoning_summary, get_usage_tokens, format_prompt_for_responses_api
from utils_response_dump import serialize_response_to_dict, write_input_instructions_before_api, write_all_output_files
from utils_config_constants import expected_keys_for_agent
from utils_task_loader import load_task_instruction

from utils_config_constants import (
    PERSONA_LUCIM_OPERATION_MODEL_GENERATOR, OUTPUT_DIR, LUCIM_RULES_FILE,
    get_reasoning_config, DEFAULT_MODEL)


def sanitize_model_name(model_name: str) -> str:
    """Sanitize model name by replacing hyphens with underscores for valid identifier."""
    return model_name.replace("-", "_")


class LucimOperationModelGeneratorAgent(LlmAgent):
    model: str = DEFAULT_MODEL
    timestamp: str = ""
    name: str = "NetLogo LUCIM Operation Synthesizer"

    client: OpenAI = None
    reasoning_effort: str = "medium"
    reasoning_summary: str = "auto"
    text_verbosity: str = "medium"
    persona_path: str = ""
    persona_text: str = ""
    lucim_rules_path: str = ""
    lucim_rules_text: str = ""

    def __init__(self, model_name: str = DEFAULT_MODEL, external_timestamp: str = None):
        sanitized_name = sanitize_model_name(model_name)
        super().__init__(
            name=f"netlogo_lucim_operation_synthesizer_agent_{sanitized_name}",
            description="LUCIM Operation Synthesizer agent for NetLogo models"
        )
        self.model = model_name
        self.timestamp = external_timestamp or datetime.datetime.now().strftime("%Y%m%d_%H%M")
        from utils_config_constants import OPENAI_API_KEY
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        try:
            self.persona_path = str(PERSONA_LUCIM_OPERATION_MODEL_GENERATOR)
            self.persona_text = pathlib.Path(self.persona_path).read_text(encoding="utf-8")
        except Exception:
            self.persona_text = ""
        try:
            self.lucim_rules_path = str(LUCIM_RULES_FILE)
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

    def synthesize_lucim_operation_from_source_code(
        self,
        netlogo_source_code: str,
        lucim_dsl_definition: str,
        netlogo_lucim_mapping: str,
        output_dir: str = None,
    ) -> Dict[str, Any]:
        """
        Synthesize LUCIM operation model directly from NetLogo source code.
        Used by persona-v3-limited-agents workflow.
        """
        if not netlogo_source_code or netlogo_source_code.strip() == "":
            return {
                "reasoning_summary": "MISSING MANDATORY INPUT: NetLogo source code is required",
                "data": None,
                "errors": ["MANDATORY INPUT MISSING: NetLogo source code must be provided"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
        if not lucim_dsl_definition or lucim_dsl_definition.strip() == "":
            return {
                "reasoning_summary": "MISSING MANDATORY INPUT: LUCIM DSL definition is required",
                "data": None,
                "errors": ["MANDATORY INPUT MISSING: LUCIM DSL definition must be provided"],
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

        task_content = load_task_instruction(3, "LUCIM Operation Synthesizer")
        instructions = (
            f"{task_content}\n\n{self.persona_text}\n\n"
            f"<LUCIM-DSL-DESCRIPTION>\n{lucim_dsl_definition}\n</LUCIM-DSL-DESCRIPTION>\n\n"
            f"<NL-LUCIM-ENV-MAPPING>\n{netlogo_lucim_mapping}\n</NL-LUCIM-ENV-MAPPING>"
        )
        input_text = f"""
<NETLOGO-SOURCE-CODE>
```
{netlogo_source_code}
```
</NETLOGO-SOURCE-CODE>
"""
        system_prompt = f"{instructions}\n\n{input_text}"
        base_output_dir = output_dir if output_dir is not None else OUTPUT_DIR
        write_input_instructions_before_api(base_output_dir, system_prompt)

        exact_input_tokens = self.count_input_tokens(instructions, input_text)
        try:
            api_config = get_reasoning_config("lucim_operation_synthesizer")
            if "reasoning" in api_config:
                api_config["reasoning"]["effort"] = self.reasoning_effort
                api_config["reasoning"]["summary"] = self.reasoning_summary
            api_config.update({
                "instructions": format_prompt_for_responses_api(system_prompt),
                "input": [{"role": "user", "content": system_prompt}]
            })
            from utils_config_constants import AGENT_TIMEOUTS
            timeout = AGENT_TIMEOUTS.get("lucim_operation_synthesizer")
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
            return {
                "reasoning_summary": f"Error during model inference: {e}",
                "data": None,
                "errors": [f"Model inference error: {e}", f"Model used: {self.model}"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }

    def save_results(self, results: Dict[str, Any], base_name: str, model_name: str, step_number = None, output_dir = None):
        if output_dir is None:
            output_dir = OUTPUT_DIR
        write_all_output_files(
            output_dir=output_dir,
            results=results,
            agent_type="lucim_operation_synthesizer",
            base_name=base_name,
            model=self.model,
            timestamp=self.timestamp,
            reasoning_effort=self.reasoning_effort,
            step_number=step_number
        )



