"""
Deterministic auditor for LUCIM Operation Model (Step 1) — no LLM.

Input: operation model JSON (dict-like)
Output: {
    "verdict": bool,
    "violations": [ { "id": str, "message": str, "location": str, "extracted_values": dict } ],
    "fix_suggestions": [ {
        "rule": str,
        "location": str,
        "change_type": str,
        "proposed_change": str,
        "example_before": str,
        "example_after": str,
        "rationale": str
    } ]
}

Minimal schema (tolerant):
{
  "system": { "name": str },
  "actors": [ { "name": str, "type": str } ],
  "events": [
      {
        "kind": "ie" | "oe",
        "name": str,     # optional event name
        "sender": str,   # instance name ("system" or actor instance)
        "receiver": str  # instance name ("system" or actor instance)
      }
  ]
}

Rules implemented (from RULES_LUCIM_Operation_model.md):
- LOM0-JSON-BLOCK-ONLY: Operation Model must be solely a JSON block (no Markdown fences, no text outside JSON)
- LOM1-ACT-TYPE-FORMAT: actor type names FirstCapitalLetterFormat, prefixed by "Act"
- LOM2-IE-EVENT-NAME-FORMAT: input event names in camelCase
- LOM3-OE-EVENT-NAME-FORMAT: output event names in camelCase
- LOM4-IE-EVENT-DIRECTION: IE must be System → Actor
- LOM5-OE-EVENT-DIRECTION: OE must be Actor → System
- LOM6-CONDITIONS-DEFINITION: condition blocks structure (preF/preP optional arrays; postF required)
- LOM7-CONDITIONS-VALIDATION: postF required and non-empty, preF/preP optional arrays
- LOM8-INPUT-EVENTS-LIMITATION: Each actor must have at least one input event
- LOM9-OUTPUT-EVENTS-LIMITATION: Each actor must have at least one output event
Note: Actor instance names (if provided) should be camelCase, but this is not a strict LOM rule.
"""
from __future__ import annotations

import json
from typing import Dict, List, Any


def _is_camel_case(name: str) -> bool:
    if not name:
        return False
    if not name[0].islower():
        return False
    # allow letters, digits; require at least one letter overall
    has_alpha = any(ch.isalpha() for ch in name)
    return has_alpha and all(ch.isalnum() for ch in name)


def _is_act_type(type_name: str) -> bool:
    if not type_name or not type_name.startswith("Act"):
        return False
    # After Act, must be FirstCapitalLetterFormat
    tail = type_name[3:]
    if not tail:
        return False
    if not tail[0].isupper():
        return False
    return all(ch.isalnum() for ch in tail)


def _index_actors(actors: Any) -> Dict[str, Dict[str, Any]]:
    # Accept dict or list; index by lowercase instance name when available,
    # and also by actor type key when actors is a dict keyed by type.
    index: Dict[str, Dict[str, Any]] = {}
    if isinstance(actors, dict):
        for type_key, actor_obj in actors.items():
            if not isinstance(actor_obj, dict):
                continue
            # Index by explicit instance name if present
            inst_name = (actor_obj.get("name") or "").strip()
            if inst_name:
                index[inst_name.lower()] = actor_obj
            # Also index by the type key (new JSON format uses type names only)
            tk = (type_key or "").strip()
            if tk:
                index[tk.lower()] = actor_obj
    elif isinstance(actors, list):
        for actor_obj in actors:
            if not isinstance(actor_obj, dict):
                continue
            inst_name = (actor_obj.get("name") or "").strip()
            if inst_name:
                index[inst_name.lower()] = actor_obj
    return index


def _location(item: Any, fallback: str) -> str:
    # The environment JSON may not include positions; provide stable location hints
    name = None
    if isinstance(item, dict):
        name = item.get("name") or item.get("id") or item.get("message")
    return name or fallback


def _generate_fix_suggestion(violation: Dict[str, Any]) -> Dict[str, str]:
    """
    Generate a fix suggestion based on a violation.
    
    Args:
        violation: Violation dictionary with "id", "message", "location", and optionally "extracted_values"
        
    Returns:
        Fix suggestion dictionary matching the persona schema
    """
    rule_id = violation.get("id", "")
    location = violation.get("location", "")
    message = violation.get("message", "")
    extracted = violation.get("extracted_values", {})
    
    # Determine change_type based on rule ID
    change_type = "other"
    if "FORMAT" in rule_id:
        change_type = "retype"
    elif "DIRECTION" in rule_id:
        change_type = "reverse_direction"
    elif "LIMITATION" in rule_id or "CONDITIONS" in rule_id:
        change_type = "add"
    elif "JSON-BLOCK" in rule_id:
        change_type = "delete"
    
    # Generate proposed_change based on rule
    proposed_change = ""
    example_before = ""
    example_after = ""
    rationale = message
    
    if rule_id == "LOM0-JSON-BLOCK-ONLY":
        proposed_change = "Remove Markdown code fences and any text outside the JSON object"
        example_before = "```json\n{...}\n```"
        example_after = "{...}"
        rationale = "Operation Model must be solely a JSON block without Markdown fences or surrounding text"
    elif rule_id == "LOM1-ACT-TYPE-FORMAT":
        type_name = extracted.get("type_name", "")
        proposed_change = f"Rename actor type to FirstCapitalLetterFormat prefixed by 'Act' (e.g., 'Act{type_name.capitalize() if type_name else 'Example'}')"
        example_before = type_name or "actorType"
        example_after = f"Act{type_name.capitalize() if type_name else 'Example'}"
        rationale = "Actor type names must be FirstCapitalLetterFormat and prefixed by 'Act'"
    elif rule_id == "LOM2-IE-EVENT-NAME-FORMAT":
        event_name = extracted.get("event_name", "")
        proposed_change = f"Rename input event to camelCase format"
        example_before = event_name or "EventName"
        example_after = "eventName" if event_name else "inputEventName"
        rationale = "Input event names must be in camelCase format"
    elif rule_id == "LOM3-OE-EVENT-NAME-FORMAT":
        event_name = extracted.get("event_name", "")
        proposed_change = f"Rename output event to camelCase format"
        example_before = event_name or "EventName"
        example_after = "eventName" if event_name else "outputEventName"
        rationale = "Output event names must be in camelCase format"
    elif rule_id == "LOM4-IE-EVENT-DIRECTION":
        source = extracted.get("source", "")
        target = extracted.get("target", "")
        proposed_change = "Set source to 'System' and target to the actor instance name"
        example_before = f"source: '{source}', target: '{target}'"
        example_after = "source: 'System', target: 'ActUser'"
        rationale = "Input events must flow from System to Actor"
    elif rule_id == "LOM5-OE-EVENT-DIRECTION":
        source = extracted.get("source", "")
        target = extracted.get("target", "")
        proposed_change = "Set source to the actor instance name and target to 'System'"
        example_before = f"source: '{source}', target: '{target}'"
        example_after = "source: 'ActUser', target: 'System'"
        rationale = "Output events must flow from Actor to System"
    elif rule_id == "LOM6-CONDITIONS-DEFINITION":
        proposed_change = "Add required 'postF' array or fix condition structure"
        example_before = '{"name": "eventName"}'
        example_after = '{"name": "eventName", "postF": [{"text": "condition", "severity": "must"}]}'
        rationale = "Events must include a required 'postF' array with condition objects"
    elif rule_id == "LOM7-CONDITIONS-VALIDATION":
        proposed_change = "Ensure postF is a non-empty array; preF and preP must be arrays when provided"
        example_before = '{"postF": null}'
        example_after = '{"postF": [{"text": "condition", "severity": "must"}]}'
        rationale = "postF must be present and non-empty; preF/preP must be arrays when provided"
    elif rule_id == "LOM8-INPUT-EVENTS-LIMITATION":
        actor_type = extracted.get("actor_type", "actor")
        proposed_change = f"Add at least one input event to {actor_type}"
        example_before = f'{{"type": "{actor_type}"}}'
        example_after = f'{{"type": "{actor_type}", "input_events": {{"eventName": {{"postF": [...]}}}}}}'
        rationale = "Each actor must have at least one input event"
    elif rule_id == "LOM9-OUTPUT-EVENTS-LIMITATION":
        actor_type = extracted.get("actor_type", "actor")
        proposed_change = f"Add at least one output event to {actor_type}"
        example_before = f'{{"type": "{actor_type}"}}'
        example_after = f'{{"type": "{actor_type}", "output_events": {{"eventName": {{"postF": [...]}}}}}}'
        rationale = "Each actor must have at least one output event"
    else:
        proposed_change = "Fix the violation according to the rule requirements"
        rationale = message
    
    return {
        "rule": rule_id,
        "location": location,
        "change_type": change_type,
        "proposed_change": proposed_change,
        "example_before": example_before,
        "example_after": example_after,
        "rationale": rationale
    }


def _check_lom0_json_block_only(raw_content: str) -> List[Dict[str, str]]:
    """
    Check LOM0-JSON-BLOCK-ONLY: Operation Model must be solely a JSON block.
    
    Validates:
    - No Markdown code fences (```json or ```)
    - No text outside the JSON object
    - Content is valid JSON
    
    Args:
        raw_content: Raw content string to validate
        
    Returns:
        List of violations (empty if compliant)
    """
    violations: List[Dict[str, str]] = []
    
    if not raw_content or not isinstance(raw_content, str):
        return violations
    
    content_stripped = raw_content.strip()
    if not content_stripped:
        return violations
    
    # Check for Markdown code fences
    if "```" in content_stripped:
        violations.append({
            "id": "LOM0-JSON-BLOCK-ONLY",
            "message": "Operation Model must not include Markdown code fences. Remove the code fences (```json or ```).",
            "location": "raw_content",
            "extracted_values": {
                "has_code_fences": True,
                "content_preview": content_stripped[:200] if len(content_stripped) > 200 else content_stripped
            }
        })
        return violations  # Early return if code fences found
    
    # Try to parse as JSON to check if it's valid JSON
    try:
        # Attempt to find JSON object boundaries
        # Look for first { and last }
        first_brace = content_stripped.find("{")
        last_brace = content_stripped.rfind("}")
        
        if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:
            violations.append({
                "id": "LOM0-JSON-BLOCK-ONLY",
                "message": "Operation Model must be a valid JSON object. No JSON object found.",
                "location": "raw_content",
                "extracted_values": {
                    "content_preview": content_stripped[:200] if len(content_stripped) > 200 else content_stripped
                }
            })
            return violations
        
        # Check for text before the JSON object
        text_before = content_stripped[:first_brace].strip()
        if text_before:
            violations.append({
                "id": "LOM0-JSON-BLOCK-ONLY",
                "message": "Operation Model must not include text outside the JSON object. Remove any text before the JSON object.",
                "location": "raw_content",
                "extracted_values": {
                    "text_before": text_before,
                    "content_preview": content_stripped[:200] if len(content_stripped) > 200 else content_stripped
                }
            })
        
        # Check for text after the JSON object
        text_after = content_stripped[last_brace + 1:].strip()
        if text_after:
            violations.append({
                "id": "LOM0-JSON-BLOCK-ONLY",
                "message": "Operation Model must not include text outside the JSON object. Remove any text after the JSON object.",
                "location": "raw_content",
                "extracted_values": {
                    "text_after": text_after,
                    "content_preview": content_stripped[-200:] if len(content_stripped) > 200 else content_stripped
                }
            })
        
        # Try to parse the JSON to ensure it's valid
        json_content = content_stripped[first_brace:last_brace + 1]
        try:
            json.loads(json_content)
        except json.JSONDecodeError as e:
            violations.append({
                "id": "LOM0-JSON-BLOCK-ONLY",
                "message": f"Operation Model must be valid JSON. JSON parsing error: {str(e)}",
                "location": "raw_content",
                "extracted_values": {
                    "json_error": str(e),
                    "content_preview": json_content[:200] if len(json_content) > 200 else json_content
                }
            })
    
    except Exception as e:
        violations.append({
            "id": "LOM0-JSON-BLOCK-ONLY",
            "message": f"Error validating JSON block format: {str(e)}",
            "location": "raw_content",
            "extracted_values": {
                "error": str(e)
            }
        })
    
    return violations


def audit_operation_model(env: Dict[str, Any], raw_content: str | None = None) -> Dict[str, Any]:
    """
    Audit Operation Model for LOM rule compliance.
    
    Args:
        env: Operation Model as a dictionary (parsed JSON)
        raw_content: Optional raw content string for LOM0 validation (JSON block format check)
        
    Returns:
        Dictionary with:
        - "verdict" (bool): True if compliant, False if non-compliant
        - "violations" (list): List of violation dicts with "id", "message", "location", "extracted_values"
        - "fix_suggestions" (list): List of fix suggestion dicts matching persona schema
    """
    violations: List[Dict[str, Any]] = []
    
    # LOM0-JSON-BLOCK-ONLY: Check raw content format if provided
    if raw_content is not None:
        lom0_violations = _check_lom0_json_block_only(raw_content)
        violations.extend(lom0_violations)

    # Note: The current ruleset (RULES_LUCIM_Operation_model.md) does not define
    # a normative check for unique System naming; we therefore do not emit
    # violations about System identity here to stay aligned with the rules file.

    actors_node = env.get("actors") or []
    # Normalize to list of dicts for iteration
    # Handle two formats:
    # 1. Dict format: {"ActMsrCreator": {...}} - type is the key
    # 2. List format: [{"name": "...", "type": "..."}] - type is in the object
    actors_list = []
    actor_type_map = {}  # Map to store type from dict key when needed
    
    if isinstance(actors_node, dict):
        # Extract type from dict keys
        for type_key, actor_obj in actors_node.items():
            if isinstance(actor_obj, dict):
                actors_list.append(actor_obj)
                # Store the type from the key for later use
                actor_type_map[id(actor_obj)] = type_key
    elif isinstance(actors_node, list):
        actors_list = [v for v in actors_node if isinstance(v, dict)]
    else:
        actors_list = []
    actor_index = _index_actors(actors_node)

    # LOM1 — actor type formatting
    for actor in actors_list:
        inst_name = (actor.get("name") or "").strip()
        # Try to get type from object first, then from dict key map
        type_name = (actor.get("type") or "").strip()
        if not type_name and id(actor) in actor_type_map:
            type_name = actor_type_map[id(actor)].strip()
        
        # LOM1-ACT-TYPE-FORMAT: Always check type format (required)
        if not _is_act_type(type_name):
            violations.append({
                "id": "LOM1-ACT-TYPE-FORMAT",
                "message": 'Actor type name must be FirstCapitalLetterFormat and prefixed by "Act".',
                "location": _location(actor, "actor"),
                "extracted_values": {
                    "type_name": type_name,
                    "actor_content": json.dumps(actor, indent=2, ensure_ascii=False)
                }
            })
        
        # Note: Actor instance names are not strictly required by LOM rules.
        # If provided, they should be camelCase, but this is not enforced as a LOM rule.

    # Normalize events: accept list/dict; if missing, derive from actor input/output events if present
    events_node = env.get("events")
    events: List[Dict[str, Any]] = []
    if isinstance(events_node, list):
        events = [e for e in events_node if isinstance(e, dict)]
    elif isinstance(events_node, dict):
        events = [e for e in events_node.values() if isinstance(e, dict)]
    else:
        # Attempt to derive minimal events from actors' input/output events blocks
        for actor in actors_list:
            inst_name = (actor.get("name") or "").strip()
            if not inst_name and id(actor) in actor_type_map:
                # New JSON format: use the type key as the identifier
                inst_name = actor_type_map[id(actor)].strip()
            inp = actor.get("input_events")
            if isinstance(inp, dict):
                for ev in inp.values():
                    if isinstance(ev, dict):
                        events.append({
                            "kind": "ie",
                            "sender": "system",
                            "receiver": inst_name,
                            "name": (ev.get("name") or "").strip() if isinstance(ev.get("name"), str) else ""
                        })
            outp = actor.get("output_events")
            if isinstance(outp, dict):
                for ev in outp.values():
                    if isinstance(ev, dict):
                        events.append({
                            "kind": "oe",
                            "sender": inst_name,
                            "receiver": "system",
                            "name": (ev.get("name") or "").strip() if isinstance(ev.get("name"), str) else ""
                        })

            # Validate event parameter blocks when present (new JSON format)
            for block_name in ("input_events", "output_events"):
                ev_block = actor.get(block_name)
                if not isinstance(ev_block, dict):
                    continue
                for ev_key, ev_val in ev_block.items():
                    if not isinstance(ev_val, dict):
                        continue
                    params = ev_val.get("parameters")
                    if params is not None:
                        if not isinstance(params, list) or not all(isinstance(p, str) for p in params):
                            violations.append({
                                "id": "LOM6-CONDITIONS-DEFINITION",
                                "message": 'Event "parameters" must be an array of strings (may be empty).',
                                "location": _location(ev_val, f"{block_name}.{ev_key}.parameters"),
                                "extracted_values": {
                                    "parameters": json.dumps(params, ensure_ascii=False)
                                }
                            })
                    # LOM6 — postF presence is required (validation of non-empty handled in LOM7)
                    if "postF" not in ev_val:
                        violations.append({
                            "id": "LOM6-CONDITIONS-DEFINITION",
                            "message": 'Event must include a required "postF" array (see LOM6-CONDITIONS-DEFINITION).',
                            "location": _location(ev_val, f"{block_name}.{ev_key}.postF")
                        })
                    # LOM6 — Validate structure of condition arrays: preF, preP, postF
                    for cond_field in ("preF", "preP", "postF"):
                        cond_list = ev_val.get(cond_field)
                        if cond_list is None:
                            continue
                        if not isinstance(cond_list, list):
                            violations.append({
                                "id": "LOM6-CONDITIONS-DEFINITION",
                                "message": f'Event "{cond_field}" must be an array of condition objects (LOM6).',
                                "location": _location(ev_val, f"{block_name}.{ev_key}.{cond_field}"),
                                "extracted_values": {cond_field: json.dumps(cond_list, ensure_ascii=False)}
                            })
                            continue
                        seen_ids = set()
                        for idx, cond in enumerate(cond_list):
                            if not isinstance(cond, dict):
                                violations.append({
                                    "id": "LOM6-CONDITIONS-DEFINITION",
                                    "message": f'Each item in "{cond_field}" must be an object (LOM6).',
                                    "location": _location(ev_val, f"{block_name}.{ev_key}.{cond_field}[{idx}]"),
                                    "extracted_values": {"item": json.dumps(cond, ensure_ascii=False)}
                                })
                                continue
                            text = cond.get("text")
                            if not isinstance(text, str) or not text.strip():
                                violations.append({
                                    "id": "LOM6-CONDITIONS-DEFINITION",
                                    "message": f'Condition "text" in "{cond_field}" must be a non-empty string (LOM6).',
                                    "location": _location(ev_val, f"{block_name}.{ev_key}.{cond_field}[{idx}].text")
                                })
                            severity = cond.get("severity")
                            if severity is not None and severity not in ("must", "should", "may"):
                                violations.append({
                                    "id": "LOM6-CONDITIONS-DEFINITION",
                                    "message": f'Condition "severity" must be one of: "must", "should", "may" (LOM6).',
                                    "location": _location(ev_val, f"{block_name}.{ev_key}.{cond_field}[{idx}].severity"),
                                    "extracted_values": {"severity": json.dumps(severity, ensure_ascii=False)}
                                })
                            cond_id = cond.get("id")
                            if isinstance(cond_id, str) and cond_id:
                                if cond_id in seen_ids:
                                    violations.append({
                                        "id": "LOM6-CONDITIONS-DEFINITION",
                                        "message": f'Condition "id" must be unique within the event for field "{cond_field}" (LOM6).',
                                        "location": _location(ev_val, f"{block_name}.{ev_key}.{cond_field}[{idx}].id"),
                                        "extracted_values": {"id": cond_id}
                                    })
                                else:
                                    seen_ids.add(cond_id)
                    # If explicit source/target provided, check direction consistency
                    src = (ev_val.get("source") or "").strip().lower()
                    tgt = (ev_val.get("target") or "").strip().lower()
                    # Accept instance name or actor type key as identifier for this actor
                    act_type_key = (actor_type_map.get(id(actor), "") or "").strip().lower()
                    acceptable_actor_tokens = set(filter(None, [
                        inst_name.lower() if inst_name else "",
                        act_type_key
                    ]))
                    if block_name == "input_events":
                        # LOM4-IE-EVENT-DIRECTION: Expect System → Actor
                        tgt_ok = (not tgt) or (tgt in acceptable_actor_tokens)
                        if (src and src != "system") or (not tgt_ok):
                            violations.append({
                                "id": "LOM4-IE-EVENT-DIRECTION",
                                "message": "All input events must have their source from the System and their target to an Actor.",
                                "location": _location(ev_val, f"{block_name}.{ev_key}"),
                                "extracted_values": {
                                    "source": ev_val.get("source"),
                                    "target": ev_val.get("target")
                                }
                            })
                    if block_name == "output_events":
                        # LOM5-OE-EVENT-DIRECTION: Expect Actor → System
                        src_ok = (not src) or (src in acceptable_actor_tokens)
                        if (not src_ok) or (tgt and tgt != "system"):
                            violations.append({
                                "id": "LOM5-OE-EVENT-DIRECTION",
                                "message": "All output events must have their source from an Actor and their target to the System.",
                                "location": _location(ev_val, f"{block_name}.{ev_key}"),
                                "extracted_values": {
                                    "source": ev_val.get("source"),
                                    "target": ev_val.get("target")
                                }
                            })

                    # LOM6/LOM7 — Event conditions validation (preF, preP optional; postF required and non-empty)
                    preF = ev_val.get("preF")
                    preP = ev_val.get("preP")
                    postF = ev_val.get("postF")

                    # postF must be present and non-empty list
                    if not isinstance(postF, list) or len(postF) == 0:
                        violations.append({
                            "id": "LOM7-CONDITIONS-VALIDATION",
                            "message": "postF must be present and a non-empty array.",
                            "location": _location(ev_val, f"{block_name}.{ev_key}.postF"),
                            "extracted_values": {
                                "postF": json.dumps(postF, ensure_ascii=False)
                            }
                        })

                    # preF/preP: if present, must be arrays (may be empty)
                    if preF is not None and not isinstance(preF, list):
                        violations.append({
                            "id": "LOM7-CONDITIONS-VALIDATION",
                            "message": "preF must be an array when provided (may be empty).",
                            "location": _location(ev_val, f"{block_name}.{ev_key}.preF"),
                            "extracted_values": {
                                "preF": json.dumps(preF, ensure_ascii=False)
                            }
                        })
                    if preP is not None and not isinstance(preP, list):
                        violations.append({
                            "id": "LOM7-CONDITIONS-VALIDATION",
                            "message": "preP must be an array when provided (may be empty).",
                            "location": _location(ev_val, f"{block_name}.{ev_key}.preP"),
                            "extracted_values": {
                                "preP": json.dumps(preP, ensure_ascii=False)
                            }
                        })
    if events:
        for evt in events:
            kind = (evt.get("kind") or "").lower().strip()  # "ie" or "oe" expected
            sender = (evt.get("sender") or "").strip()
            receiver = (evt.get("receiver") or "").strip()
            evt_name = (evt.get("name") or "").strip()

            sender_l = sender.lower()
            receiver_l = receiver.lower()

            sender_is_system = sender_l == "system"
            receiver_is_system = receiver_l == "system"
            sender_is_actor = sender_l in actor_index
            receiver_is_actor = receiver_l in actor_index

            # LOM2 / LOM3 — event name format checks when provided
            if evt_name:
                if kind == "ie" and not _is_camel_case(evt_name):
                    violations.append({
                        "id": "LOM2-IE-EVENT-NAME-FORMAT",
                        "message": "All input event names must be human-readable, in camelCase.",
                        "location": _location(evt, "event.name"),
                        "extracted_values": {
                            "event_name": evt_name,
                            "event_content": json.dumps(evt, indent=2, ensure_ascii=False)
                        }
                    })
                if kind == "oe" and not _is_camel_case(evt_name):
                    violations.append({
                        "id": "LOM3-OE-EVENT-NAME-FORMAT",
                        "message": "All output event names must be human-readable, in camelCase.",
                        "location": _location(evt, "event.name"),
                        "extracted_values": {
                            "event_name": evt_name,
                            "event_content": json.dumps(evt, indent=2, ensure_ascii=False)
                        }
                    })

            # LOM4-IE-EVENT-DIRECTION: IE direction System→Actor
            if kind == "ie":
                if not (sender_is_system and receiver_is_actor):
                    violations.append({
                        "id": "LOM4-IE-EVENT-DIRECTION",
                        "message": "All input events must have their source from the System and their target to an Actor.",
                        "location": _location(evt, "event"),
                        "extracted_values": {
                            "sender": sender,
                            "receiver": receiver,
                            "event_name": evt_name if evt_name else "(unnamed)",
                            "event_content": json.dumps(evt, indent=2, ensure_ascii=False)
                        }
                    })

            # LOM5-OE-EVENT-DIRECTION: OE direction Actor→System
            if kind == "oe":
                if not (sender_is_actor and receiver_is_system):
                    violations.append({
                        "id": "LOM5-OE-EVENT-DIRECTION",
                        "message": "All output events must have their source from an Actor and their target to the System.",
                        "location": _location(evt, "event"),
                        "extracted_values": {
                            "sender": sender,
                            "receiver": receiver,
                            "event_name": evt_name if evt_name else "(unnamed)",
                            "event_content": json.dumps(evt, indent=2, ensure_ascii=False)
                        }
                    })

    # LOM8 and LOM9 — Check that each actor has at least one input event and one output event
    # Count input and output events per actor
    actor_input_events = {}  # actor identifier -> count of input events
    actor_output_events = {}  # actor identifier -> count of output events
    
    # Count from events list if present
    if events:
        for evt in events:
            kind = (evt.get("kind") or "").lower().strip()
            sender = (evt.get("sender") or "").strip()
            receiver = (evt.get("receiver") or "").strip()
            
            sender_l = sender.lower()
            receiver_l = receiver.lower()
            
            sender_is_actor = sender_l in actor_index
            receiver_is_actor = receiver_l in actor_index
            
            if kind == "ie" and receiver_is_actor:
                # Input event: System → Actor
                actor_input_events[receiver_l] = actor_input_events.get(receiver_l, 0) + 1
            elif kind == "oe" and sender_is_actor:
                # Output event: Actor → System
                actor_output_events[sender_l] = actor_output_events.get(sender_l, 0) + 1
    
    # Also count from actors' input_events and output_events blocks (new JSON format)
    for actor in actors_list:
        inst_name = (actor.get("name") or "").strip()
        if not inst_name and id(actor) in actor_type_map:
            inst_name = actor_type_map[id(actor)].strip()
        
        # Get actor identifier (prefer type key, fallback to instance name)
        actor_id = None
        if id(actor) in actor_type_map:
            actor_id = actor_type_map[id(actor)].lower()
        elif inst_name:
            actor_id = inst_name.lower()
        
        if not actor_id:
            continue
        
        # Count input events from actor's input_events block
        inp = actor.get("input_events")
        if isinstance(inp, dict):
            input_count = sum(1 for ev in inp.values() if isinstance(ev, dict))
            if input_count > 0:
                actor_input_events[actor_id] = actor_input_events.get(actor_id, 0) + input_count
        
        # Count output events from actor's output_events block
        outp = actor.get("output_events")
        if isinstance(outp, dict):
            output_count = sum(1 for ev in outp.values() if isinstance(ev, dict))
            if output_count > 0:
                actor_output_events[actor_id] = actor_output_events.get(actor_id, 0) + output_count
    
    # LOM8-INPUT-EVENTS-LIMITATION: Each actor must have at least one input event
    for actor in actors_list:
        inst_name = (actor.get("name") or "").strip()
        type_name = (actor.get("type") or "").strip()
        if not type_name and id(actor) in actor_type_map:
            type_name = actor_type_map[id(actor)].strip()
        
        # Get actor identifier
        actor_id = None
        if id(actor) in actor_type_map:
            actor_id = actor_type_map[id(actor)].lower()
        elif inst_name:
            actor_id = inst_name.lower()
        elif type_name:
            actor_id = type_name.lower()
        
        if not actor_id:
            continue
        
        if actor_input_events.get(actor_id, 0) == 0:
            violations.append({
                "id": "LOM8-INPUT-EVENTS-LIMITATION",
                "message": "Each actor must have at least one input event in the operation model.",
                "location": _location(actor, type_name or inst_name or "actor"),
                "extracted_values": {
                    "actor_type": type_name or inst_name or "unknown",
                    "actor_content": json.dumps(actor, indent=2, ensure_ascii=False)
                }
            })
    
    # LOM9-OUTPUT-EVENTS-LIMITATION: Each actor must have at least one output event
    for actor in actors_list:
        inst_name = (actor.get("name") or "").strip()
        type_name = (actor.get("type") or "").strip()
        if not type_name and id(actor) in actor_type_map:
            type_name = actor_type_map[id(actor)].strip()
        
        # Get actor identifier
        actor_id = None
        if id(actor) in actor_type_map:
            actor_id = actor_type_map[id(actor)].lower()
        elif inst_name:
            actor_id = inst_name.lower()
        elif type_name:
            actor_id = type_name.lower()
        
        if not actor_id:
            continue
        
        if actor_output_events.get(actor_id, 0) == 0:
            violations.append({
                "id": "LOM9-OUTPUT-EVENTS-LIMITATION",
                "message": "Each actor must have at least one output event in the operation model.",
                "location": _location(actor, type_name or inst_name or "actor"),
                "extracted_values": {
                    "actor_type": type_name or inst_name or "unknown",
                    "actor_content": json.dumps(actor, indent=2, ensure_ascii=False)
                }
            })

    verdict = len(violations) == 0
    
    # Generate fix suggestions for each violation
    fix_suggestions: List[Dict[str, str]] = []
    for violation in violations:
        suggestion = _generate_fix_suggestion(violation)
        fix_suggestions.append(suggestion)
    
    return {
        "verdict": verdict,
        "violations": violations,
        "fix_suggestions": fix_suggestions
    }


def extract_event_conditions(env: Dict[str, Any]) -> Dict[str, Any]:
    """Extract preF/preP/postF for all events in the actors blocks.

    Returns a dict:
    {
      "input_events": {
         "<actorKey>.<eventKey>": {"preF": [...], "preP": [...], "postF": [...]} ,
         ...
      },
      "output_events": { ... }
    }
    The actorKey is the actor type key when actors is a dict, or the actor instance name otherwise.
    """
    result: Dict[str, Any] = {"input_events": {}, "output_events": {}}
    actors_node = env.get("actors") or []
    actor_type_map: Dict[int, str] = {}
    actors_list: List[Dict[str, Any]] = []

    if isinstance(actors_node, dict):
        for type_key, actor_obj in actors_node.items():
            if isinstance(actor_obj, dict):
                actors_list.append(actor_obj)
                actor_type_map[id(actor_obj)] = type_key
    elif isinstance(actors_node, list):
        actors_list = [v for v in actors_node if isinstance(v, dict)]

    for actor in actors_list:
        # Prefer type key when present; otherwise use instance name
        actor_key = actor_type_map.get(id(actor)) or (actor.get("name") or "").strip()
        if not actor_key:
            actor_key = "<unknown-actor>"
        for block_name in ("input_events", "output_events"):
            ev_block = actor.get(block_name)
            if not isinstance(ev_block, dict):
                continue
            for ev_key, ev_val in ev_block.items():
                if not isinstance(ev_val, dict):
                    continue
                entry = {
                    "preF": ev_val.get("preF") or [],
                    "preP": ev_val.get("preP") or [],
                    "postF": ev_val.get("postF") or []
                }
                result[block_name][f"{actor_key}.{ev_key}"] = entry
    return result

if __name__ == "__main__":
    # Tiny manual harness
    sample = {
        "system": {"name": "System"},
        "actors": [
            {"name": "theCreator", "type": "ActMsrCreator"},
            {"name": "bill", "type": "ActAdministrator"}
        ],
        "events": [
            {"kind": "oe", "sender": "bill", "receiver": "system"},
            {"kind": "ie", "sender": "system", "receiver": "bill"}
        ]
    }
    import json
    print(json.dumps(audit_operation_model(sample), indent=2))




