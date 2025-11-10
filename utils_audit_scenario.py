"""
Deterministic auditor for LUCIM Scenario textual rules (Step 2) — no LLM.

Input: PlantUML textual scenario (string) OR JSON scenario structure
Output: { "verdict": bool, "violations": [ { "id": str, "message": str, "line": int } ] }

Rules implemented (from RULES_LUCIM_Scenario.md):
- LSC0-JSON-BLOCK-ONLY: Scenario must be a JSON block only, no Markdown code fences
- LSC2-ACTORS-LIMITATION: At most five actors in the scenario
- LSC3-INPUT-EVENTS-LIMITATION: At least one input event to each actor
- LSC4-OUTPUT-EVENTS-LIMITATION: At least one output event from each actor
- LSC5-EVENT-SEQUENCE: Event sequence compliance with Operation Model (basic validation of conditions existence)
- LSC6-PARAMETERS-VALUE: Parameter validation against Operation Model (parameter count validation)
- LSC7-SYSTEM-NO-SELF-LOOP: No System→System events
- LSC8-ACTOR-NO-SELF-LOOP: No Actor→Actor events
- LSC9-INPUT-EVENT-ALLOWED-EVENTS: Input events must be System → Actor
- LSC10-OUTPUT-EVENT-DIRECTION: Output events must be Actor → System
- LSC11-ACTOR-INSTANCE-FORMAT: Actor instance names must be camelCase
- LSC12-ACTOR-TYPE-NAME-CONSISTENCY: Actor types must match Operation Model
- LSC13-ACTOR-INSTANCE-CONSISTENCY: Actor instances must be consistent with types
- LSC14-INPUT-EVENT-NAME-CONSISTENCY: Input event names must match Operation Model
- LSC15-OUTPUT-EVENT-NAME-CONSISTENCY: Output event names must match Operation Model
- LSC16-ACTORS-PERSISTENCE: Only actors from Operation Model allowed
- LSC17-EVENTS-PERSISTENCE: Only events from Operation Model allowed

Note: Rules LSC5, LSC6, LSC12-LSC17 require the operation_model parameter to be provided.

JSON format validation:
- Expected format: { "data": { "scenario": { "name": str, "description": str, "messages": [...] } }, "errors": [] }
- Each message must have: source, target, event_type, event_name, parameters
"""
from __future__ import annotations

import re
import json
from typing import Dict, List, Any, Optional, Union


_MSG_RE = re.compile(r"^(?P<lhs>\S+)\s*(?P<arrow>--?>|-->>|-->)\s*(?P<rhs>\S+)\s*:\s*(?P<name>\w+)\s*\((?P<params>[^)]*)\)\s*$")

# Regex for camelCase validation (LSC11)
_CAMEL_CASE_RE = re.compile(r'^[a-z][a-zA-Z0-9]*$')


def _is_system(token: str) -> bool:
    t = token.strip()
    return t == "system" or t == "System"


def _is_actor_token(token: str) -> bool:
    t = token.strip()
    # Heuristic: not system
    return not _is_system(t)


def _is_camel_case(name: str) -> bool:
    """
    Check if a name follows camelCase format (LSC11).
    Must start with lowercase letter, followed by alphanumeric characters.
    Examples: actAdministrator, chris, theClock, anEcologist
    """
    if not name or not isinstance(name, str):
        return False
    return bool(_CAMEL_CASE_RE.match(name.strip()))


def _check_lsc0_json_block_only(raw_content: str) -> List[Dict[str, Any]]:
    """
    LSC0-JSON-BLOCK-ONLY: Check that scenario is a JSON block only, no Markdown code fences.
    
    Args:
        raw_content: Raw content string to check
    
    Returns:
        List of violations
    """
    violations: List[Dict[str, Any]] = []
    
    if not raw_content or not isinstance(raw_content, str):
        return violations
    
    content_stripped = raw_content.strip()
    
    # Check for Markdown code fences
    if content_stripped.startswith("```"):
        violations.append({
            "id": "LSC0-JSON-BLOCK-ONLY",
            "message": "Scenario must be a JSON block only. Do not include Markdown code fences (```) or any text outside the JSON object.",
            "line": 0,
            "extracted_values": {}
        })
    
    # Check for non-JSON text before/after JSON
    # Try to find JSON boundaries
    json_start = content_stripped.find("{")
    json_end = content_stripped.rfind("}")
    
    if json_start > 0 or (json_end >= 0 and json_end < len(content_stripped) - 1):
        # There's text before or after the JSON
        before_json = content_stripped[:json_start].strip() if json_start > 0 else ""
        after_json = content_stripped[json_end + 1:].strip() if json_end >= 0 else ""
        
        if before_json or after_json:
            violations.append({
                "id": "LSC0-JSON-BLOCK-ONLY",
                "message": "Scenario must be a JSON block only. Do not include Markdown code fences or any text outside the JSON object.",
                "line": 0,
                "extracted_values": {"text_before": before_json[:50], "text_after": after_json[:50]}
            })
    
    return violations


def _extract_operation_model_data(operation_model: Optional[Union[Dict[str, Any], str]]) -> Dict[str, Any]:
    """
    Extract and index operation model data for validation.
    
    Args:
        operation_model: Operation model as dict or raw text string (may contain markdown fences)
    
    Returns:
        Dictionary with:
        - actor_types: set of actor type names (e.g., {"ActOperator", "ActUser"})
        - actor_type_to_events: dict mapping actor type -> {input_events: set, output_events: set}
        - all_input_events: set of all input event names
        - all_output_events: set of all output event names
        - event_to_actor_type: dict mapping event_name -> actor_type
        - event_to_parameters: dict mapping event_name -> list of parameter names
        - event_to_conditions: dict mapping event_name -> {preF: list, preP: list, postF: list}
    """
    result = {
        "actor_types": set(),
        "actor_type_to_events": {},  # actor_type -> {"input_events": set, "output_events": set}
        "all_input_events": set(),
        "all_output_events": set(),
        "event_to_actor_type": {},  # event_name -> actor_type
        "event_to_parameters": {},  # event_name -> list of parameter names
        "event_to_conditions": {}  # event_name -> {"preF": list, "preP": list, "postF": list}
    }
    
    if not operation_model:
        return result
    
    # If operation_model is a string, try to parse it as JSON
    if isinstance(operation_model, str):
        try:
            # Try to extract JSON from markdown code blocks if present
            text = operation_model.strip()
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                if end > start:
                    text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                if end > start:
                    text = text[start:end].strip()
            # Parse JSON
            operation_model = json.loads(text)
        except (json.JSONDecodeError, ValueError, TypeError):
            # If parsing fails, return empty result (auditor will work without operation model data)
            return result
    
    if not isinstance(operation_model, dict):
        return result
    
    # Extract actors from operation model
    # Support multiple formats:
    # 1. {"data": {"actors": {...}}} - wrapped format (most common from output-data.json)
    # 2. {"actors": {...}} - direct format
    actors_node = None
    
    # First, try to get from data.actors (wrapped format)
    if "data" in operation_model:
        data_node = operation_model.get("data")
        if isinstance(data_node, dict):
            actors_node = data_node.get("actors")
    
    # If not found, try direct actors key
    if not actors_node:
        actors_node = operation_model.get("actors")
    
    if not actors_node:
        return result
    
    # Handle dict format where keys are actor type names
    if isinstance(actors_node, dict):
        for actor_type, actor_data in actors_node.items():
            if not isinstance(actor_data, dict):
                continue
            
            result["actor_types"].add(actor_type)
            result["actor_type_to_events"][actor_type] = {
                "input_events": set(),
                "output_events": set()
            }
            
            # Extract input events
            input_events = actor_data.get("input_events", {})
            if isinstance(input_events, dict):
                for event_name, event_data in input_events.items():
                    if isinstance(event_data, dict):
                        result["all_input_events"].add(event_name)
                        result["actor_type_to_events"][actor_type]["input_events"].add(event_name)
                        result["event_to_actor_type"][event_name] = actor_type
                        result["event_to_parameters"][event_name] = event_data.get("parameters", [])
                        result["event_to_conditions"][event_name] = {
                            "preF": event_data.get("preF", []),
                            "preP": event_data.get("preP", []),
                            "postF": event_data.get("postF", [])
                        }
            
            # Extract output events
            output_events = actor_data.get("output_events", {})
            if isinstance(output_events, dict):
                for event_name, event_data in output_events.items():
                    if isinstance(event_data, dict):
                        result["all_output_events"].add(event_name)
                        result["actor_type_to_events"][actor_type]["output_events"].add(event_name)
                        result["event_to_actor_type"][event_name] = actor_type
                        result["event_to_parameters"][event_name] = event_data.get("parameters", [])
                        result["event_to_conditions"][event_name] = {
                            "preF": event_data.get("preF", []),
                            "preP": event_data.get("preP", []),
                            "postF": event_data.get("postF", [])
                        }
    
    return result


def _infer_actor_type_from_instance(instance_name: str, operation_model_data: Dict[str, Any]) -> Optional[str]:
    """
    Infer actor type from instance name (LSC13).
    
    Examples:
    - actAdministrator -> ActAdministrator
    - chris -> ActEcologist (if chris is used for ActEcologist)
    - theClock -> ActClock
    
    Strategy:
    1. Try exact match (instance name == actor type)
    2. Try camelCase variations
    3. Try removing common prefixes/suffixes
    """
    if not instance_name:
        return None
    
    actor_types = operation_model_data.get("actor_types", set())
    
    # Direct match
    if instance_name in actor_types:
        return instance_name
    
    # Try to match by removing "act" prefix and capitalizing
    if instance_name.startswith("act") and len(instance_name) > 3:
        candidate = "Act" + instance_name[3:4].upper() + instance_name[4:]
        if candidate in actor_types:
            return candidate
    
    # Try to match by adding "Act" prefix and capitalizing first letter
    candidate = "Act" + instance_name[0:1].upper() + instance_name[1:]
    if candidate in actor_types:
        return candidate
    
    # Try exact match with case-insensitive comparison
    instance_lower = instance_name.lower()
    for actor_type in actor_types:
        if actor_type.lower() == instance_lower:
            return actor_type
    
    return None


def _audit_scenario_json(
    scenario_data: Dict[str, Any],
    operation_model: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Audit JSON scenario structure and return violations.
    
    Args:
        scenario_data: JSON structure following format: { "data": { "scenario": {...} }, "errors": [] }
        operation_model: Optional operation model for rules requiring it (LSC5, LSC6, LSC12-LSC17)
    
    Returns:
        List of violation dictionaries
    """
    violations: List[Dict[str, Any]] = []
    
    # Extract operation model data if provided
    op_model_data = None
    if operation_model:
        op_model_data = _extract_operation_model_data(operation_model)
        # Validate extraction was successful
        if op_model_data and (len(op_model_data.get("all_input_events", set())) == 0 and len(op_model_data.get("all_output_events", set())) == 0):
            # Log warning if no events were extracted (might indicate a problem)
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Operation model extraction resulted in empty event sets. Operation model structure may be invalid.")
    else:
        # Log when operation model is not provided (this will cause false violations for LSC12-LSC17)
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Operation model not provided to scenario auditor. Rules LSC5, LSC6, LSC12-LSC17 will be skipped, but this may indicate a bug in the orchestrator.")
    
    # Validate top-level structure
    if not isinstance(scenario_data, dict):
        violations.append({
            "id": "JSON-FORMAT-ERROR",
            "message": "Scenario data must be a JSON object",
            "line": 0,
            "extracted_values": {}
        })
        return violations
    
    # Extract scenario - support both formats:
    # 1. Standardized format: {"data": {"scenario": {...}}}
    # 2. Direct format: {"scenario": {...}}
    scenario = None
    if "data" in scenario_data:
        # Standardized format: {"data": {"scenario": {...}}}
        data_node = scenario_data.get("data")
        if isinstance(data_node, dict) and "scenario" in data_node:
            scenario = data_node.get("scenario")
        elif data_node is None:
            # Error case: data is null
            violations.append({
                "id": "JSON-FORMAT-ERROR",
                "message": "Scenario data.data is null (error case)",
                "line": 0,
                "extracted_values": {}
            })
            return violations
        else:
            violations.append({
                "id": "JSON-FORMAT-ERROR",
                "message": "Scenario data.data must contain 'scenario' key",
                "line": 0,
                "extracted_values": {}
            })
            return violations
    elif "scenario" in scenario_data:
        # Direct format: {"scenario": {...}}
        scenario = scenario_data.get("scenario")
    else:
        violations.append({
            "id": "JSON-FORMAT-ERROR",
            "message": "Scenario data must contain either 'data.scenario' key (standardized format) or 'scenario' key (direct format)",
            "line": 0,
            "extracted_values": {}
        })
        return violations
    
    if not isinstance(scenario, dict):
        violations.append({
            "id": "JSON-FORMAT-ERROR",
            "message": "Scenario data.data.scenario must be a dictionary",
            "line": 0,
            "extracted_values": {}
        })
        return violations
    
    # Extract messages
    messages = scenario.get("messages", [])
    if not isinstance(messages, list):
        violations.append({
            "id": "JSON-FORMAT-ERROR",
            "message": "Scenario data.data.scenario.messages must be an array",
            "line": 0,
            "extracted_values": {}
        })
        return violations
    
    # Collect actors and events for quantitative rules (LSC2, LSC3, LSC4)
    actors_set = set()
    actor_input_events = {}  # actor -> count of input events
    actor_output_events = {}  # actor -> count of output events
    
    # Validate each message
    for msg_idx, msg in enumerate(messages):
        if not isinstance(msg, dict):
            violations.append({
                "id": "JSON-FORMAT-ERROR",
                "message": f"Message at index {msg_idx} must be a dictionary",
                "line": msg_idx + 1,
                "extracted_values": {"message_index": msg_idx}
            })
            continue
        
        # Check required fields
        required_fields = ["source", "target", "event_type", "event_name", "parameters"]
        for field in required_fields:
            if field not in msg:
                violations.append({
                    "id": "JSON-FORMAT-ERROR",
                    "message": f"Message at index {msg_idx} missing required field '{field}'",
                    "line": msg_idx + 1,
                    "extracted_values": {"message_index": msg_idx, "missing_field": field}
                })
        
        # Extract message fields
        src = msg.get("source", "")
        tgt = msg.get("target", "")
        name = msg.get("event_name", "")
        event_type = msg.get("event_type", "")
        
        # Validate event_type
        if event_type not in ["input_event", "output_event"]:
            violations.append({
                "id": "JSON-FORMAT-ERROR",
                "message": f"Message at index {msg_idx} has invalid event_type '{event_type}'. Must be 'input_event' or 'output_event'",
                "line": msg_idx + 1,
                "extracted_values": {"message_index": msg_idx, "event_type": event_type}
            })
        
        # Apply validation rules
        lhs_is_system = _is_system(src)
        rhs_is_system = _is_system(tgt)
        lhs_is_actor = _is_actor_token(src)
        rhs_is_actor = _is_actor_token(tgt)
        
        # LSC7 — forbid System→System
        if lhs_is_system and rhs_is_system:
            violations.append({
                "id": "LSC7-SYSTEM-NO-SELF-LOOP",
                "message": "Events must never be from System to System. System → System",
                "line": msg_idx + 1,
                "extracted_values": {"message_index": msg_idx, "sender": src, "receiver": tgt, "event_name": name}
            })
        
        # LSC8 — forbid Actor→Actor
        if lhs_is_actor and rhs_is_actor and not lhs_is_system and not rhs_is_system:
            violations.append({
                "id": "LSC8-ACTOR-NO-SELF-LOOP",
                "message": "Events must never be from Actor to Actor. Actor → Actor",
                "line": msg_idx + 1,
                "extracted_values": {"message_index": msg_idx, "sender": src, "receiver": tgt, "event_name": name}
            })
        
        # LSC9 — Input events must be System → Actor
        if event_type == "input_event" or name.startswith("ie"):
            if not (lhs_is_system and rhs_is_actor):
                violations.append({
                    "id": "LSC9-INPUT-EVENT-ALLOWED-EVENTS",
                    "message": "Input events must always be from the System to Actors. System → Actor",
                    "line": msg_idx + 1,
                    "extracted_values": {"message_index": msg_idx, "sender": src, "receiver": tgt, "event_name": name, "event_type": event_type}
                })
            if event_type != "input_event":
                violations.append({
                    "id": "LSC9-INPUT-EVENT-TYPE",
                    "message": f"Input events (ie*) must have event_type='input_event', got '{event_type}'",
                    "line": msg_idx + 1,
                    "extracted_values": {"message_index": msg_idx, "event_name": name, "event_type": event_type}
                })
            # Track input events per actor (LSC3)
            if rhs_is_actor:
                actor_input_events[tgt] = actor_input_events.get(tgt, 0) + 1
        
        # LSC10 — Output events must be Actor → System
        if event_type == "output_event" or name.startswith("oe"):
            if not (lhs_is_actor and rhs_is_system):
                violations.append({
                    "id": "LSC10-OUTPUT-EVENT-DIRECTION",
                    "message": "Output events must always be from Actors to the System. Actor → System",
                    "line": msg_idx + 1,
                    "extracted_values": {"message_index": msg_idx, "sender": src, "receiver": tgt, "event_name": name, "event_type": event_type}
                })
            if event_type != "output_event":
                violations.append({
                    "id": "LSC10-OUTPUT-EVENT-TYPE",
                    "message": f"Output events (oe*) must have event_type='output_event', got '{event_type}'",
                    "line": msg_idx + 1,
                    "extracted_values": {"message_index": msg_idx, "event_name": name, "event_type": event_type}
                })
            # Track output events per actor (LSC4)
            if lhs_is_actor:
                actor_output_events[src] = actor_output_events.get(src, 0) + 1
        
        # LSC11 — Actor instance format (camelCase)
        if lhs_is_actor and not _is_camel_case(src):
            violations.append({
                "id": "LSC11-ACTOR-INSTANCE-FORMAT",
                "message": f"Actor instance name '{src}' must be human-readable in camelCase (e.g., actAdministrator, chris, theClock, anEcologist)",
                "line": msg_idx + 1,
                "extracted_values": {"message_index": msg_idx, "actor_name": src}
            })
        if rhs_is_actor and not _is_camel_case(tgt):
            violations.append({
                "id": "LSC11-ACTOR-INSTANCE-FORMAT",
                "message": f"Actor instance name '{tgt}' must be human-readable in camelCase (e.g., actAdministrator, chris, theClock, anEcologist)",
                "line": msg_idx + 1,
                "extracted_values": {"message_index": msg_idx, "actor_name": tgt}
            })
        
        # Collect actors for LSC2
        if lhs_is_actor:
            actors_set.add(src)
        if rhs_is_actor:
            actors_set.add(tgt)
    
    # LSC2 — At most five actors
    if len(actors_set) > 5:
        violations.append({
            "id": "LSC2-ACTORS-LIMITATION",
            "message": f"There must be at most five actors in the scenario. Found {len(actors_set)} actors: {', '.join(sorted(actors_set))}",
            "line": 0,
            "extracted_values": {"actor_count": len(actors_set), "actors": sorted(actors_set)}
        })
    
    # LSC3 — At least one input event to each actor
    for actor in actors_set:
        if actor_input_events.get(actor, 0) == 0:
            violations.append({
                "id": "LSC3-INPUT-EVENTS-LIMITATION",
                "message": f"There must be at least one input event to each actor in the scenario. Actor '{actor}' has no input events.",
                "line": 0,
                "extracted_values": {"actor": actor}
            })
    
    # LSC4 — At least one output event from each actor
    for actor in actors_set:
        if actor_output_events.get(actor, 0) == 0:
            violations.append({
                "id": "LSC4-OUTPUT-EVENTS-LIMITATION",
                "message": f"There must be at least one output event from each actor in the scenario. Actor '{actor}' has no output events.",
                "line": 0,
                "extracted_values": {"actor": actor}
            })
    
    # Rules requiring Operation Model (LSC5, LSC6, LSC12-LSC17)
    if op_model_data:
        # Additional validation: ensure op_model_data has events extracted
        if len(op_model_data.get("all_input_events", set())) == 0 and len(op_model_data.get("all_output_events", set())) == 0:
            # Operation model was provided but extraction failed - log warning but continue
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Operation model data provided but no events extracted. This may cause false violations for LSC14-LSC17.")
        # Track actor instance to type mapping for LSC12 and LSC13
        actor_instance_to_type = {}  # instance_name -> actor_type
        scenario_actor_types = set()  # actor types found in scenario
        scenario_event_names = set()  # event names found in scenario
        
        # First pass: collect actor types and validate consistency
        for msg_idx, msg in enumerate(messages):
            if not isinstance(msg, dict):
                continue
            
            src = msg.get("source", "")
            tgt = msg.get("target", "")
            name = msg.get("event_name", "")
            event_type = msg.get("event_type", "")
            params = msg.get("parameters", [])
            
            lhs_is_system = _is_system(src)
            rhs_is_system = _is_system(tgt)
            lhs_is_actor = _is_actor_token(src)
            rhs_is_actor = _is_actor_token(tgt)
            
            # LSC12 & LSC13 — Actor type and instance consistency
            if lhs_is_actor:
                inferred_type = _infer_actor_type_from_instance(src, op_model_data)
                if inferred_type:
                    actor_instance_to_type[src] = inferred_type
                    scenario_actor_types.add(inferred_type)
                else:
                    # LSC16 — Actor persistence: actor instance must correspond to a type in operation model
                    violations.append({
                        "id": "LSC16-ACTORS-PERSISTENCE",
                        "message": f"Actor instance '{src}' does not correspond to any actor type defined in the Operation Model. Do not invent new actor types.",
                        "line": msg_idx + 1,
                        "extracted_values": {"message_index": msg_idx, "actor_instance": src}
                    })
            
            if rhs_is_actor:
                inferred_type = _infer_actor_type_from_instance(tgt, op_model_data)
                if inferred_type:
                    actor_instance_to_type[tgt] = inferred_type
                    scenario_actor_types.add(inferred_type)
                else:
                    # LSC16 — Actor persistence
                    violations.append({
                        "id": "LSC16-ACTORS-PERSISTENCE",
                        "message": f"Actor instance '{tgt}' does not correspond to any actor type defined in the Operation Model. Do not invent new actor types.",
                        "line": msg_idx + 1,
                        "extracted_values": {"message_index": msg_idx, "actor_instance": tgt}
                    })
            
            # LSC14 & LSC15 — Event name consistency
            if event_type == "input_event" or name.startswith("ie"):
                scenario_event_names.add(name)
                if name not in op_model_data["all_input_events"]:
                    violations.append({
                        "id": "LSC14-INPUT-EVENT-NAME-CONSISTENCY",
                        "message": f"Input event name '{name}' must be strictly the same name as defined in the Operation Model. Event not found in Operation Model.",
                        "line": msg_idx + 1,
                        "extracted_values": {"message_index": msg_idx, "event_name": name}
                    })
                else:
                    # LSC17 — Event persistence: event must be from operation model
                    # Already validated by LSC14, but we track it
                    pass
            
            if event_type == "output_event" or name.startswith("oe"):
                scenario_event_names.add(name)
                if name not in op_model_data["all_output_events"]:
                    violations.append({
                        "id": "LSC15-OUTPUT-EVENT-NAME-CONSISTENCY",
                        "message": f"Output event name '{name}' must be strictly the same name as defined in the Operation Model. Event not found in Operation Model.",
                        "line": msg_idx + 1,
                        "extracted_values": {"message_index": msg_idx, "event_name": name}
                    })
                else:
                    # LSC17 — Event persistence
                    pass
            
            # LSC17 — Events persistence: all events must be from operation model
            if name and name not in op_model_data["all_input_events"] and name not in op_model_data["all_output_events"]:
                violations.append({
                    "id": "LSC17-EVENTS-PERSISTENCE",
                    "message": f"Event '{name}' is not defined in the Operation Model. Events must be persistent. Do not invent new event names.",
                    "line": msg_idx + 1,
                    "extracted_values": {"message_index": msg_idx, "event_name": name}
                })
            
            # LSC6 — Parameters value validation
            if name in op_model_data["event_to_parameters"]:
                expected_params = op_model_data["event_to_parameters"][name]
                # Parameters in scenario can be string, list, or dict
                parsed_params = []
                if isinstance(params, dict):
                    # Dict format: extract parameter names (keys)
                    # Expected format: {"AparamName": value, ...}
                    parsed_params = list(params.keys())
                elif isinstance(params, str):
                    # Try to parse as JSON or treat as single value
                    try:
                        parsed = json.loads(params) if params.strip().startswith("[") else [params]
                        if isinstance(parsed, dict):
                            parsed_params = list(parsed.keys())
                        elif isinstance(parsed, list):
                            parsed_params = parsed
                        else:
                            parsed_params = [parsed] if parsed else []
                    except:
                        parsed_params = [params] if params else []
                elif isinstance(params, list):
                    parsed_params = params
                else:
                    parsed_params = []
                
                # Normalize expected params: remove type annotations (e.g., "Aparam:dtString" -> "Aparam")
                expected_param_names = []
                for ep in expected_params:
                    if isinstance(ep, str):
                        # Remove type annotation if present (format: "ParamName:dtType")
                        param_name = ep.split(":")[0].strip()
                        expected_param_names.append(param_name)
                    else:
                        expected_param_names.append(str(ep))
                
                # Normalize actual params: extract names if they contain type annotations
                actual_param_names = []
                for ap in parsed_params:
                    if isinstance(ap, str):
                        # Remove type annotation if present
                        param_name = ap.split(":")[0].strip()
                        actual_param_names.append(param_name)
                    else:
                        actual_param_names.append(str(ap))
                
                # Check parameter count (basic validation)
                # Note: Type checking would require more sophisticated validation
                if len(actual_param_names) != len(expected_param_names):
                    violations.append({
                        "id": "LSC6-PARAMETERS-VALUE",
                        "message": f"Event '{name}' has {len(actual_param_names)} parameters but Operation Model defines {len(expected_param_names)} parameters: {expected_params}",
                        "line": msg_idx + 1,
                        "extracted_values": {"message_index": msg_idx, "event_name": name, "expected_params": expected_params, "actual_params": parsed_params}
                    })
            
            # LSC12 — Actor type name consistency
            # This is validated implicitly through LSC16, but we add explicit check
            if lhs_is_actor and src in actor_instance_to_type:
                actor_type = actor_instance_to_type[src]
                if actor_type not in op_model_data["actor_types"]:
                    violations.append({
                        "id": "LSC12-ACTOR-TYPE-NAME-CONSISTENCY",
                        "message": f"Actor type '{actor_type}' (inferred from instance '{src}') must be strictly the same type name as defined in the Operation Model.",
                        "line": msg_idx + 1,
                        "extracted_values": {"message_index": msg_idx, "actor_instance": src, "actor_type": actor_type}
                    })
            
            if rhs_is_actor and tgt in actor_instance_to_type:
                actor_type = actor_instance_to_type[tgt]
                if actor_type not in op_model_data["actor_types"]:
                    violations.append({
                        "id": "LSC12-ACTOR-TYPE-NAME-CONSISTENCY",
                        "message": f"Actor type '{actor_type}' (inferred from instance '{tgt}') must be strictly the same type name as defined in the Operation Model.",
                        "line": msg_idx + 1,
                        "extracted_values": {"message_index": msg_idx, "actor_instance": tgt, "actor_type": actor_type}
                    })
            
            # LSC13 — Actor instance consistency
            if lhs_is_actor and src in actor_instance_to_type:
                actor_type = actor_instance_to_type[src]
                # Check if the event is valid for this actor type
                actor_events = op_model_data["actor_type_to_events"].get(actor_type, {})
                if event_type == "input_event" and name not in actor_events.get("input_events", set()):
                    # Event might be valid if it's defined for this actor type
                    if name in op_model_data["event_to_actor_type"]:
                        expected_actor_type = op_model_data["event_to_actor_type"][name]
                        if expected_actor_type != actor_type:
                            violations.append({
                                "id": "LSC13-ACTOR-INSTANCE-CONSISTENCY",
                                "message": f"Actor instance '{src}' (type '{actor_type}') is inconsistent. Event '{name}' is defined for actor type '{expected_actor_type}' in the Operation Model.",
                                "line": msg_idx + 1,
                                "extracted_values": {"message_index": msg_idx, "actor_instance": src, "actor_type": actor_type, "event_name": name, "expected_actor_type": expected_actor_type}
                            })
            
            if rhs_is_actor and tgt in actor_instance_to_type:
                actor_type = actor_instance_to_type[tgt]
                actor_events = op_model_data["actor_type_to_events"].get(actor_type, {})
                if event_type == "input_event" and name not in actor_events.get("input_events", set()):
                    if name in op_model_data["event_to_actor_type"]:
                        expected_actor_type = op_model_data["event_to_actor_type"][name]
                        if expected_actor_type != actor_type:
                            violations.append({
                                "id": "LSC13-ACTOR-INSTANCE-CONSISTENCY",
                                "message": f"Actor instance '{tgt}' (type '{actor_type}') is inconsistent. Event '{name}' is defined for actor type '{expected_actor_type}' in the Operation Model.",
                                "line": msg_idx + 1,
                                "extracted_values": {"message_index": msg_idx, "actor_instance": tgt, "actor_type": actor_type, "event_name": name, "expected_actor_type": expected_actor_type}
                            })
        
        # LSC5 — Event sequence validation (preF, preP, postF)
        # This requires checking conditions in sequence
        # We track the state after each event to validate preconditions
        event_sequence_state = {}  # Track state after each event
        
        for msg_idx, msg in enumerate(messages):
            if not isinstance(msg, dict):
                continue
            
            name = msg.get("event_name", "")
            if not name or name not in op_model_data["event_to_conditions"]:
                continue
            
            conditions = op_model_data["event_to_conditions"][name]
            preF = conditions.get("preF", [])
            preP = conditions.get("preP", [])
            postF = conditions.get("postF", [])
            
            # Basic validation: check if postF is present and non-empty (should be guaranteed by operation model)
            if not postF:
                violations.append({
                    "id": "LSC5-EVENT-SEQUENCE",
                    "message": f"Event '{name}' must have postF conditions defined in the Operation Model. Sequence compliance cannot be validated.",
                    "line": msg_idx + 1,
                    "extracted_values": {"message_index": msg_idx, "event_name": name}
                })
            
            # Note: Full preF/preP/postF sequence validation would require:
            # 1. Tracking system state after each event
            # 2. Validating that preF and preP conditions are satisfied before the event
            # 3. Validating that postF conditions are satisfied after the event
            # This is complex and may require domain-specific knowledge
            # For now, we validate that conditions exist and are structured correctly
            # A more sophisticated implementation would track state variables and validate conditions
    
    return violations


def audit_scenario(
    text: Union[str, Dict[str, Any]],
    raw_content: Optional[str] = None,
    operation_model: Optional[Union[Dict[str, Any], str]] = None
) -> Dict[str, Any]:
    """
    Audit scenario - supports both PlantUML text and JSON format.
    
    Args:
        text: PlantUML textual scenario (string) OR JSON scenario structure (string or dict)
        raw_content: Optional raw content string for LSC0 validation (JSON block format check)
        operation_model: Optional operation model for rules requiring it (LSC5, LSC6, LSC12-LSC17)
    
    Returns:
        { "verdict": bool, "violations": [ { "id": str, "message": str, "line": int } ] }
    """
    violations: List[Dict[str, Any]] = []
    
    # LSC0-JSON-BLOCK-ONLY: Check raw content format if provided
    if raw_content is not None:
        lsc0_violations = _check_lsc0_json_block_only(raw_content)
        violations.extend(lsc0_violations)
    elif isinstance(text, str):
        # Use text as raw_content if no separate raw_content provided
        lsc0_violations = _check_lsc0_json_block_only(text)
        violations.extend(lsc0_violations)
    
    # Try to parse as JSON first
    scenario_data = None
    if isinstance(text, dict):
        scenario_data = text
    elif isinstance(text, str) and text.strip():
        # Try to parse as JSON
        try:
            scenario_data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            # Not JSON, treat as PlantUML text
            scenario_data = None
    
    # If we have JSON data, use JSON auditor
    if scenario_data is not None:
        json_violations = _audit_scenario_json(scenario_data, operation_model=operation_model)
        violations.extend(json_violations)
    else:
        # Fall back to PlantUML text auditor
        lines = (text or "").splitlines()
        
        # Collect actors and events for quantitative rules (LSC2, LSC3, LSC4)
        actors_set = set()
        actor_input_events = {}  # actor -> count of input events
        actor_output_events = {}  # actor -> count of output events
        
        for idx, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line or line.startswith("//"):
                continue
            
            m = _MSG_RE.match(line)
            if not m:
                continue
            
            lhs = m.group("lhs")
            arrow = m.group("arrow")
            rhs = m.group("rhs")
            name = m.group("name")
            
            lhs_is_system = _is_system(lhs)
            rhs_is_system = _is_system(rhs)
            lhs_is_actor = _is_actor_token(lhs)
            rhs_is_actor = _is_actor_token(rhs)
            
            # LSC7 — forbid System→System
            if lhs_is_system and rhs_is_system:
                violations.append({
                    "id": "LSC7-SYSTEM-NO-SELF-LOOP",
                    "message": "Events must never be from System to System. System → System",
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip(), "sender": lhs, "receiver": rhs, "event_name": name}
                })
            
            # LSC8 — forbid Actor→Actor
            if lhs_is_actor and rhs_is_actor and not lhs_is_system and not rhs_is_system:
                violations.append({
                    "id": "LSC8-ACTOR-NO-SELF-LOOP",
                    "message": "Events must never be from Actor to Actor. Actor → Actor",
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip(), "sender": lhs, "receiver": rhs, "event_name": name}
                })
            
            # LSC9 — Input events must be System → Actor (dashed arrow)
            if name.startswith("ie"):
                if not (lhs_is_system and rhs_is_actor and arrow == "-->"):
                    violations.append({
                        "id": "LSC9-INPUT-EVENT-ALLOWED-EVENTS",
                        "message": "Input events must always be from the System to Actors. System → Actor (use dashed arrow: -->)",
                        "line": idx,
                        "extracted_values": {"line_content": raw.rstrip(), "sender": lhs, "receiver": rhs, "arrow": arrow, "event_name": name}
                    })
                # Track input events per actor (LSC3)
                if rhs_is_actor:
                    actor_input_events[rhs] = actor_input_events.get(rhs, 0) + 1
            
            # LSC10 — Output events must be Actor → System (solid arrow)
            if name.startswith("oe"):
                if not (lhs_is_actor and rhs_is_system and arrow == "->"):
                    violations.append({
                        "id": "LSC10-OUTPUT-EVENT-DIRECTION",
                        "message": "Output events must always be from Actors to the System. Actor → System (use solid arrow: ->)",
                        "line": idx,
                        "extracted_values": {"line_content": raw.rstrip(), "sender": lhs, "receiver": rhs, "arrow": arrow, "event_name": name}
                    })
                # Track output events per actor (LSC4)
                if lhs_is_actor:
                    actor_output_events[lhs] = actor_output_events.get(lhs, 0) + 1
            
            # LSC11 — Actor instance format (camelCase)
            if lhs_is_actor and not _is_camel_case(lhs):
                violations.append({
                    "id": "LSC11-ACTOR-INSTANCE-FORMAT",
                    "message": f"Actor instance name '{lhs}' must be human-readable in camelCase (e.g., actAdministrator, chris, theClock, anEcologist)",
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip(), "actor_name": lhs}
                })
            if rhs_is_actor and not _is_camel_case(rhs):
                violations.append({
                    "id": "LSC11-ACTOR-INSTANCE-FORMAT",
                    "message": f"Actor instance name '{rhs}' must be human-readable in camelCase (e.g., actAdministrator, chris, theClock, anEcologist)",
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip(), "actor_name": rhs}
                })
            
            # Collect actors for LSC2
            if lhs_is_actor:
                actors_set.add(lhs)
            if rhs_is_actor:
                actors_set.add(rhs)
        
        # LSC2 — At most five actors
        if len(actors_set) > 5:
            violations.append({
                "id": "LSC2-ACTORS-LIMITATION",
                "message": f"There must be at most five actors in the scenario. Found {len(actors_set)} actors: {', '.join(sorted(actors_set))}",
                "line": 0,
                "extracted_values": {"actor_count": len(actors_set), "actors": sorted(actors_set)}
            })
        
        # LSC3 — At least one input event to each actor
        for actor in actors_set:
            if actor_input_events.get(actor, 0) == 0:
                violations.append({
                    "id": "LSC3-INPUT-EVENTS-LIMITATION",
                    "message": f"There must be at least one input event to each actor in the scenario. Actor '{actor}' has no input events.",
                    "line": 0,
                    "extracted_values": {"actor": actor}
                })
        
        # LSC4 — At least one output event from each actor
        for actor in actors_set:
            if actor_output_events.get(actor, 0) == 0:
                violations.append({
                    "id": "LSC4-OUTPUT-EVENTS-LIMITATION",
                    "message": f"There must be at least one output event from each actor in the scenario. Actor '{actor}' has no output events.",
                    "line": 0,
                    "extracted_values": {"actor": actor}
                })
    
    verdict = len(violations) == 0
    return {"verdict": verdict, "violations": violations}


if __name__ == "__main__":
    sample = """
system --> bill : ieHello()
bill -> system : oeAck()
"""
    import json
    print(json.dumps(audit_scenario(sample), indent=2))


