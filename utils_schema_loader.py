#!/usr/bin/env python3
"""
Utilities to load agent output templates from input-persona files and validate data
against those templates. This keeps persona/DSL files as the single source of truth
for agent-specific output structures.

The loader extracts the JSON block that follows the heading "Output must include:".
Validation is intentionally lightweight: it checks that the keys present in the
template exist in the provided data (shallow check by default).
"""

from __future__ import annotations

import json
from typing import Dict, Any, Optional

from utils_config_constants import (
    PERSONA_SYNTAX_PARSER,
    PERSONA_SEMANTICS_PARSER,
    PERSONA_MESSIR_MAPPER,
    PERSONA_SCENARIO_WRITER,
    PERSONA_PLANTUML_WRITER,
    PERSONA_PLANTUML_AUDITOR,
    PERSONA_PLANTUML_CORRECTOR,
)


AGENT_TO_PERSONA = {
    "syntax_parser": PERSONA_SYNTAX_PARSER,
    "semantics_parser": PERSONA_SEMANTICS_PARSER,
    "messir_mapper": PERSONA_MESSIR_MAPPER,
    "scenario_writer": PERSONA_SCENARIO_WRITER,
    "plantuml_writer": PERSONA_PLANTUML_WRITER,
    "plantuml_auditor": PERSONA_PLANTUML_AUDITOR,
    "plantuml_corrector": PERSONA_PLANTUML_CORRECTOR,
}


def _extract_first_json_block_after_marker(text: str, marker: str = "Output must include:") -> Optional[str]:
    """Extract the first fenced JSON code block that appears after a given marker line.

    Returns the raw JSON string (without fences) or None if not found.
    """
    try:
        idx = text.find(marker)
        if idx == -1:
            return None
        after = text[idx:]
        # Look for ```json ... ``` block
        fence_start = after.find("```json")
        if fence_start == -1:
            # Accept generic code fence too
            fence_start = after.find("```")
            if fence_start == -1:
                return None
        body = after[fence_start + 3:] if after[fence_start:fence_start+7] != "```json" else after[fence_start + 7:]
        fence_end = body.find("```")
        if fence_end == -1:
            return None
        json_raw = body[:fence_end].strip()
        return json_raw
    except Exception:
        return None


def load_persona_output_template(persona_path) -> Optional[Dict[str, Any]]:
    """Load the output JSON template from a persona file if present.

    Returns a dict template or None if no template can be found/parsed.
    """
    try:
        text = persona_path.read_text(encoding="utf-8")
    except Exception:
        return None

    raw = _extract_first_json_block_after_marker(text)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def get_template_for_agent(agent_type: str) -> Optional[Dict[str, Any]]:
    persona_path = AGENT_TO_PERSONA.get(agent_type)
    if not persona_path:
        return None
    return load_persona_output_template(persona_path)


def validate_data_against_template(data: Any, template: Any, shallow: bool = True) -> Dict[str, Any]:
    """Validate that all keys present in the template exist in data.

    - If shallow=True, only validate dict keys at the top level of the template.
    - If shallow=False, recurse for dicts and iterate for lists where template has exemplar entries.

    Returns a report dict with keys: { "missing_keys": [..] }.
    """
    report = {"missing_keys": []}

    def _validate(d: Any, t: Any, prefix: str = ""):
        if isinstance(t, dict):
            if not isinstance(d, dict):
                report["missing_keys"].append(prefix or "<root>")
                return
            for k, v in t.items():
                path = f"{prefix}.{k}" if prefix else k
                if k not in d:
                    report["missing_keys"].append(path)
                    continue
                if not shallow:
                    _validate(d[k], v, path)
        elif isinstance(t, list) and not shallow:
            if not isinstance(d, list) or len(t) == 0:
                return
            # Validate against the first exemplar in the template list
            _validate(d[0] if d else {}, t[0], prefix + "[0]")
        else:
            # Primitive: no further validation
            return

    _validate(data, template)
    return report


