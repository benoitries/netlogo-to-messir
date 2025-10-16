#!/usr/bin/env python3
"""
Expected top-level key sets for each agent's response.json.
These sets enforce exact presence: not less, not more.
"""

from typing import Dict, Set


COMMON_KEYS = {
    "agent_type",
    "model",
    "timestamp",
    "base_name",
    "step_number",
    "reasoning_summary",
    "data",
    "errors",
    "tokens_used",
    "input_tokens",
    "visible_output_tokens",
    "reasoning_tokens",
    "total_output_tokens",
    # Include raw_usage as existing agents store it in reasoning payload, not in response.json
}

# Some agents might include raw_response dump for auditing
OPTIONAL_KEYS = {"raw_response"}


AGENT_KEYS: Dict[str, Set[str]] = {
    "syntax_parser": COMMON_KEYS | OPTIONAL_KEYS,
    "semantics_parser": COMMON_KEYS | OPTIONAL_KEYS,
    "messir_mapper": COMMON_KEYS | OPTIONAL_KEYS,
    "scenario_writer": COMMON_KEYS | OPTIONAL_KEYS,
    "plantuml_writer": COMMON_KEYS | OPTIONAL_KEYS,
    "plantuml_auditor": COMMON_KEYS | OPTIONAL_KEYS,
    "plantuml_corrector": COMMON_KEYS | OPTIONAL_KEYS,
    "plantuml_final_auditor": COMMON_KEYS | OPTIONAL_KEYS,
}


def expected_keys_for_agent(agent_type: str) -> Set[str]:
    return AGENT_KEYS.get(agent_type, COMMON_KEYS | OPTIONAL_KEYS)


