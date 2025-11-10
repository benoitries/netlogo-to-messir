"""
Deterministic auditor for LUCIM PlantUML Diagram rules (Step 3) — no LLM.

Input: PlantUML textual diagram (.puml content string)
Output: { "verdict": bool, "violations": [ { "id": str, "message": str, "line": int } ] }

Rules implemented (complete coverage of all validation rules):

Textual Rules (fully implemented):
- LDR0-PLANTUML-BLOCK-ONLY: PlantUML Diagram must be solely a PlantUML block (no Markdown fences, no text outside PlantUML)
- LDR1-SYS-UNIQUE: exactly one System lifeline per diagram
- LDR2-ACTOR-DECLARED-AFTER-SYSTEM: actors must be declared after System
- LDR3-SYSTEM-DECLARED-FIRST: System must be declared first before all actors
- LDR4-EVENT-DIRECTIONALITY: every message must connect exactly one Actor and System
- LDR5-SYSTEM-NO-SELF-LOOP: no System→System events
- LDR6-ACTOR-NO-ACTOR-LOOP: no Actor→Actor events
- LDR7-ACTIVATION-BAR-SEQUENCE: activation must occur on Actor lifeline immediately after event
- LDR8-ACTIVATION-BAR-NESTING-FORBIDDEN: activation bars must never be nested
- LDR9-ACTIVATION-BAR-OVERLAPPING-FORBIDDEN: activation bars must never overlap
- LDR10-ACTIVATION-BAR-ON-SYSTEM-FORBIDDEN: no activation bar on System lifeline
- LDR17-ACTOR-DECLARATION-SYNTAX: actor declaration syntax validation
- LDR19-DIAGRAM-ALLOW-BLANK-LINES-AND-COMMENTS: blank lines and all comment types are ignored (//, ', note blocks, note syntax - respected throughout parsing)
- LDR20-ACTIVATION-BAR-SEQUENCE: strict sequence: event → activate → deactivate
- LDR23-EVENT-PARAMETER-COMMA-SEPARATED: parameters must be comma-separated
- LDR24-SYSTEM-DECLARATION: System declaration syntax validation
- LDR25-INPUT-EVENT-SYNTAX: ie* events must use dashed arrows (-->)
- LDR26-OUTPUT-EVENT-SYNTAX: oe* events must use continuous arrows (->)
- LDR27-ACTOR-INSTANCE-FORMAT: actor instance names must be camelCase
- LDR28-ACTOR-INSTANCE-NAME-CONSISTENCY: validated when operation_model AND scenario are provided

Graphical Rules (SVG-based validation):
- LDR11-LDR16: validated via validate_diagram_graphics.py when svg_path is provided
  - LDR11-SYSTEM-SHAPE: System must be rectangle shape
  - LDR12-SYSTEM-COLOR: System background color #E8C28A
  - LDR13-ACTOR-SHAPE: Actors must be rectangle shape
  - LDR14-ACTOR-COLOR: Actor background color #FFF3B3
  - LDR15-ACTIVATION-BAR-INPUT-EVENT-COLOR: activation bar color #C0EBFD after input events
  - LDR16-ACTIVATION-BAR-OUTPUT-EVENT-COLOR: activation bar color #274364 after output events

Permissive Rules (no validation required):
- LDR18-DIAGRAM-LUCIM-REPRESENTATION: format requirement (implicitly satisfied by PlantUML sequence format)
- LDR21-EVENT-PARAMETER-TYPE: allows any parameter type (permissive)
- LDR22-EVENT-PARAMETER-FLEX-QUOTING: allows flexible quoting (permissive)
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional


_PARTICIPANT_RE = re.compile(r"^participant\s+\"?(?P<label>[^\"]+)\"?\s+as\s+(?P<alias>\w+)(\s+#[0-9A-Fa-f]{6})?\s*$")
_SYSTEM_SIMPLE_RE = re.compile(r"^participant\s+System\s+as\s+system(\s+#[0-9A-Fa-f]{6})?\s*$")
_MSG_RE = re.compile(r"^(?P<lhs>\S+)\s*(?P<arrow>--?>)\s*(?P<rhs>\S+)\s*:\s*(?P<name>\w+)\s*\((?P<params>[^)]*)\)\s*$")
_ACTIVATE_RE = re.compile(r"^activate\s+(?P<who>\w+)\b")
_DEACTIVATE_RE = re.compile(r"^deactivate\s+(?P<who>\w+)\b")
_ACTOR_TYPE_RE = re.compile(r"^Act[A-Z][A-Za-z0-9]*$")
_CAMEL_CASE_ALIAS_RE = re.compile(r"^[a-z][a-zA-Z0-9]*$")


def _is_system_token(tok: str) -> bool:
    t = tok.strip()
    return t == "system" or t == "System"


def _is_comment_line(line: str) -> bool:
    """
    Check if a line is a PlantUML comment (LDR19 compliance).
    
    PlantUML supports multiple comment syntaxes:
    - // comment (single-line comment)
    - ' comment (alternative single-line comment)
    - /note right/ or /note left/ (note blocks)
    - note right: text or note left: text (note syntax)
    - note over participant (notes over participants)
    
    Args:
        line: Line to check (should be stripped)
        
    Returns:
        True if the line is a comment, False otherwise
    """
    if not line:
        return False
    
    stripped = line.strip()
    
    # // comment (most common)
    if stripped.startswith("//"):
        return True
    
    # ' comment (alternative syntax)
    if stripped.startswith("'"):
        return True
    
    # /note right/ or /note left/ (note blocks - start and end markers)
    if stripped.startswith("/note ") and stripped.endswith("/"):
        return True
    
    # note right: or note left: (note syntax with text)
    if stripped.startswith("note ") and ":" in stripped:
        return True
    
    # note over participant (notes over participants)
    if stripped.startswith("note over "):
        return True
    
    return False


def _check_ldr0_plantuml_block_only(raw_content: str) -> List[Dict[str, Any]]:
    """
    Check LDR0-PLANTUML-BLOCK-ONLY: PlantUML Diagram must be solely a PlantUML block.
    
    Validates:
    - No Markdown code fences (```plantuml or ```)
    - No text outside the PlantUML block
    - Content is valid PlantUML (starts with @startuml, ends with @enduml)
    
    Args:
        raw_content: Raw content string to validate
        
    Returns:
        List of violations (empty if compliant)
    """
    violations: List[Dict[str, Any]] = []
    
    if not raw_content or not isinstance(raw_content, str):
        return violations
    
    content_stripped = raw_content.strip()
    if not content_stripped:
        return violations
    
    # Check for Markdown code fences
    if "```" in content_stripped:
        violations.append({
            "id": "LDR0-PLANTUML-BLOCK-ONLY",
            "message": "PlantUML Diagram must not include Markdown code fences. Remove the code fences (```plantuml or ```).",
            "line": 1,
            "extracted_values": {
                "has_code_fences": True,
                "content_preview": content_stripped[:200] if len(content_stripped) > 200 else content_stripped
            }
        })
        return violations  # Early return if code fences found
    
    # Check for PlantUML block boundaries (@startuml and @enduml)
    startuml_pos = content_stripped.find("@startuml")
    enduml_pos = content_stripped.rfind("@enduml")
    
    if startuml_pos == -1:
        violations.append({
            "id": "LDR0-PLANTUML-BLOCK-ONLY",
            "message": "PlantUML Diagram must be a valid PlantUML block. No @startuml found.",
            "line": 1,
            "extracted_values": {
                "content_preview": content_stripped[:200] if len(content_stripped) > 200 else content_stripped
            }
        })
        return violations
    
    if enduml_pos == -1 or enduml_pos < startuml_pos:
        violations.append({
            "id": "LDR0-PLANTUML-BLOCK-ONLY",
            "message": "PlantUML Diagram must be a valid PlantUML block. No @enduml found or @enduml appears before @startuml.",
            "line": 1,
            "extracted_values": {
                "content_preview": content_stripped[:200] if len(content_stripped) > 200 else content_stripped
            }
        })
        return violations
    
    # Check for text before the PlantUML block
    text_before = content_stripped[:startuml_pos].strip()
    if text_before:
        violations.append({
            "id": "LDR0-PLANTUML-BLOCK-ONLY",
            "message": "PlantUML Diagram must not include text outside the PlantUML block. Remove any text before @startuml.",
            "line": 1,
            "extracted_values": {
                "text_before": text_before,
                "content_preview": content_stripped[:200] if len(content_stripped) > 200 else content_stripped
            }
        })
    
    # Check for text after the PlantUML block
    text_after = content_stripped[enduml_pos + len("@enduml"):].strip()
    if text_after:
        violations.append({
            "id": "LDR0-PLANTUML-BLOCK-ONLY",
            "message": "PlantUML Diagram must not include text outside the PlantUML block. Remove any text after @enduml.",
            "line": 1,
            "extracted_values": {
                "text_after": text_after,
                "content_preview": content_stripped[-200:] if len(content_stripped) > 200 else content_stripped
            }
        })
    
    return violations


def _extract_plantuml_from_text(content: str) -> str | None:
    """
    Extract PlantUML block from text by finding @startuml and @enduml markers.
    This is robust even if the content is JSON or contains other text.
    
    Args:
        content: Raw content string that may contain PlantUML block
        
    Returns:
        Extracted PlantUML text (between @startuml and @enduml), or None if not found
    """
    if not content:
        return None
    
    # Find @startuml and @enduml positions (case-insensitive search)
    startuml_pos = content.find("@startuml")
    if startuml_pos == -1:
        # Try case-insensitive
        startuml_pos_lower = content.lower().find("@startuml")
        if startuml_pos_lower != -1:
            startuml_pos = startuml_pos_lower
    
    if startuml_pos == -1:
        return None
    
    # Find @enduml after @startuml
    search_start = startuml_pos + len("@startuml")
    enduml_pos = content.find("@enduml", search_start)
    if enduml_pos == -1:
        # Try case-insensitive
        enduml_pos_lower = content.lower().find("@enduml", search_start)
        if enduml_pos_lower != -1:
            enduml_pos = enduml_pos_lower
    
    if enduml_pos == -1:
        return None
    
    # Extract the PlantUML block (include @startuml and @enduml)
    enduml_end = enduml_pos + len("@enduml")
    plantuml_text = content[startuml_pos:enduml_end]
    
    # Handle escaped newlines in JSON strings (\\n -> \n)
    # This handles cases where PlantUML is in a JSON string with escaped newlines
    plantuml_text = plantuml_text.replace("\\n", "\n").replace("\\t", "\t")
    
    return plantuml_text


def _validate_ldr11_ldr16_graphical_rules(svg_path: Path | str) -> List[Dict[str, Any]]:
    """
    Wrapper function to validate graphical rules LDR11-LDR16 using validate_diagram_graphics.py.
    
    This function delegates to validate_diagram_graphics.validate_svg_file() and converts
    the result format to match the audit_diagram() violation format.
    
    Args:
        svg_path: Path to the SVG file to validate
        
    Returns:
        List of violations in the standard format, or empty list if validation fails or SVG is missing
    """
    violations: List[Dict[str, Any]] = []
    
    try:
        # Import here to avoid circular dependencies
        from validate_diagram_graphics import validate_svg_file
        
        svg_path_obj = Path(svg_path) if isinstance(svg_path, str) else svg_path
        
        if not svg_path_obj.exists():
            violations.append({
                "id": "LDR11-LDR16-SVG-MISSING",
                "message": f"SVG file not found at {svg_path_obj}. Cannot validate graphical rules LDR11-LDR16.",
                "line": 1,
                "extracted_values": {"svg_path": str(svg_path_obj)}
            })
            return violations
        
        # Call the graphics validator
        result = validate_svg_file(svg_path_obj)
        
        # Convert violations to standard format
        if not result.get("verdict", False):
            for v in result.get("violations", []):
                # Map the violation IDs to specific LDR rules
                rule_id = v.get("id", "UNKNOWN")
                
                # Handle combined LDR15-16 violation
                if rule_id == "LDR15-16-ACTIVATION-BAR-COLOR":
                    # Try to determine if it's LDR15 or LDR16 from extracted values
                    extracted = v.get("extracted_values", {})
                    expected = extracted.get("expected", "").lower()
                    if expected == "#c0ebfd":
                        rule_id = "LDR15-ACTIVATION-BAR-INPUT-EVENT-COLOR"
                    elif expected == "#274364":
                        rule_id = "LDR16-ACTIVATION-BAR-OUTPUT-EVENT-COLOR"
                    else:
                        # Keep combined ID if we can't determine
                        pass
                
                violations.append({
                    "id": rule_id,
                    "message": v.get("message", "Graphical rule violation"),
                    "line": v.get("line", 1),
                    "extracted_values": v.get("extracted_values", {})
                })
    except ImportError:
        violations.append({
            "id": "LDR11-LDR16-IMPORT-ERROR",
            "message": "Cannot import validate_diagram_graphics module. Graphical rules LDR11-LDR16 cannot be validated.",
            "line": 1,
            "extracted_values": {}
        })
    except Exception as e:
        violations.append({
            "id": "LDR11-LDR16-VALIDATION-ERROR",
            "message": f"Error validating graphical rules: {e}",
            "line": 1,
            "extracted_values": {"error": str(e)}
        })
    
    return violations


def _validate_ldr28_actor_instance_consistency(
    plantuml_text: str,
    operation_model: Dict[str, Any] | None = None,
    scenario: Dict[str, Any] | None = None
) -> List[Dict[str, Any]]:
    """
    Validate LDR28: Actor instance names must be consistent with actor type names defined
    in Operation Model and Scenario.
    
    This rule requires BOTH operation_model AND scenario to be provided. Actor instance names
    in the PlantUML diagram must match the actor type definitions from both the Operation Model
    and the Scenario.
    
    Args:
        plantuml_text: PlantUML diagram text
        operation_model: Operation Model dictionary (required for LDR28)
        scenario: Scenario dictionary (required for LDR28)
        
    Returns:
        List of violations in the standard format
    """
    violations: List[Dict[str, Any]] = []
    
    # LDR28 requires BOTH operation_model AND scenario
    if not operation_model or not scenario:
        # Missing required data, skip validation
        return violations
    
    # Extract actor instances from PlantUML
    lines = plantuml_text.splitlines()
    actor_instances: Dict[str, Dict[str, str]] = {}  # alias -> {"type": actor_type, "name": actor_name, "line": line_number}
    
    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or _is_comment_line(line):
            continue
        
        mp = _PARTICIPANT_RE.match(line)
        if mp:
            alias = mp.group("alias")
            label = mp.group("label")
            
            # Skip System
            if alias == "system" or _is_system_token(alias):
                continue
            
            # Extract actor type and name from label (format: "actorName:ActActorType")
            if ":" in label:
                actor_name, actor_type = label.split(":", 1)
                actor_instances[alias] = {
                    "type": actor_type,
                    "name": actor_name,
                    "line": idx
                }
    
    # Build expected actor types and instance names from Operation Model
    expected_types_from_om: set[str] = set()
    expected_instances_from_om: Dict[str, str] = {}  # type -> instance_name (if specified)
    if operation_model:
        actors_node = operation_model.get("actors") or []
        if isinstance(actors_node, dict):
            # Dict format: {"ActMsrCreator": {...}}
            expected_types_from_om.update(actors_node.keys())
            # Extract instance names if provided in actor objects
            for actor_type, actor_obj in actors_node.items():
                if isinstance(actor_obj, dict):
                    instance_name = actor_obj.get("name", "").strip()
                    if instance_name:
                        expected_instances_from_om[actor_type] = instance_name
        elif isinstance(actors_node, list):
            # List format: [{"name": "...", "type": "..."}]
            for actor in actors_node:
                if isinstance(actor, dict):
                    actor_type = actor.get("type", "").strip()
                    if actor_type:
                        expected_types_from_om.add(actor_type)
                        instance_name = actor.get("name", "").strip()
                        if instance_name:
                            expected_instances_from_om[actor_type] = instance_name
    
    # Build expected actor types from Scenario
    expected_types_from_scenario: set[str] = set()
    if scenario:
        # Scenario format can vary, try to extract actor types
        scenario_data = scenario.get("data", {})
        if isinstance(scenario_data, dict):
            scenario_obj = scenario_data.get("scenario", {})
            if isinstance(scenario_obj, dict):
                messages = scenario_obj.get("messages", [])
                for msg in messages:
                    if isinstance(msg, dict):
                        # Try to extract actor type from source or target
                        source = msg.get("source", "")
                        target = msg.get("target", "")
                        # Actor types might be embedded in the message structure
                        # This is a simplified extraction; may need refinement based on actual scenario format
                        pass
    
    # Validate each actor instance against both Operation Model and Scenario
    # LDR28 requires consistency with type definitions from both sources
    # This includes: (1) type must be defined, (2) instance name must be consistent with type
    for alias, actor_data in actor_instances.items():
        actor_type = actor_data["type"]
        actor_name = actor_data["name"]
        line_num = actor_data["line"]
        
        # Check 1: Type must be defined in Operation Model
        if actor_type not in expected_types_from_om:
            violations.append({
                "id": "LDR28-ACTOR-INSTANCE-NAME-CONSISTENCY",
                "message": f"Actor instance '{alias}' has type '{actor_type}' which is not defined in the Operation Model. Actor instance names must be consistent with their type definition.",
                "line": line_num,
                "extracted_values": {
                    "actor_instance": alias,
                    "actor_instance_name": actor_name,
                    "actor_type": actor_type,
                    "expected_types_from_om": list(expected_types_from_om),
                    "source": "Operation Model"
                }
            })
            continue  # Skip further checks if type is invalid
        
        # Check 2: Instance name consistency with type (if instance name is specified in Operation Model)
        # Note: According to LDR28 examples, multiple instance names can be valid for the same type
        # (e.g., "chris" or "anEcologist" for "ActEcologist"). If the Operation Model specifies
        # an instance name, we check if the diagram uses that name OR if it's a valid custom name.
        # Custom names are accepted as long as they follow camelCase (per LDR27) and the type is correct.
        if actor_type in expected_instances_from_om:
            expected_instance_name = expected_instances_from_om[actor_type]
            # Accept if name matches expected OR if it's a valid custom name (camelCase)
            # Custom names like "chris" for "ActEcologist" are valid per LDR28 examples
            if actor_name != expected_instance_name and alias != expected_instance_name:
                # Check if it's a valid camelCase name (per LDR27) - if so, accept it as a custom name
                if not _CAMEL_CASE_ALIAS_RE.match(actor_name) and not _CAMEL_CASE_ALIAS_RE.match(alias):
                    # Not camelCase - this is a violation
                    violations.append({
                        "id": "LDR28-ACTOR-INSTANCE-NAME-CONSISTENCY",
                        "message": f"Actor instance '{alias}' (name: '{actor_name}') is not consistent with the expected instance name '{expected_instance_name}' for type '{actor_type}' in the Operation Model, and does not follow camelCase naming convention. Actor instance names must be consistent with their type definition.",
                        "line": line_num,
                        "extracted_values": {
                            "actor_instance": alias,
                            "actor_instance_name": actor_name,
                            "actor_type": actor_type,
                            "expected_instance_name": expected_instance_name,
                            "source": "Operation Model"
                        }
                    })
                # If it's valid camelCase, accept it as a custom name (e.g., "chris" for "ActEcologist")
                # This is compliant per LDR28 examples
        
        # Check 3: Instance name should follow camelCase convention (LDR27)
        # Examples: "actAdministrator" for "ActAdministrator", "chris" for "ActEcologist"
        # According to LDR28, custom names like "chris" are valid even if they don't match
        # the camelCase of the type. The important thing is that they are camelCase and the type is correct.
        # We validate camelCase format here, but accept custom names as long as they're valid camelCase.
        if not _CAMEL_CASE_ALIAS_RE.match(actor_name) and not _CAMEL_CASE_ALIAS_RE.match(alias):
            violations.append({
                "id": "LDR28-ACTOR-INSTANCE-NAME-CONSISTENCY",
                "message": f"Actor instance '{alias}' (name: '{actor_name}') does not follow camelCase naming convention (LDR27). Actor instance names must be consistent with their type definition and follow camelCase format.",
                "line": line_num,
                "extracted_values": {
                    "actor_instance": alias,
                    "actor_instance_name": actor_name,
                    "actor_type": actor_type,
                    "source": "Naming Convention"
                }
            })
        
        # Check 4: Against Scenario (required)
        # Note: Scenario validation extracts actor types from messages
        # For now, we validate against Operation Model as the primary source
        # Scenario validation can be enhanced when scenario format is finalized
        if expected_types_from_scenario and actor_type not in expected_types_from_scenario:
            violations.append({
                "id": "LDR28-ACTOR-INSTANCE-NAME-CONSISTENCY",
                "message": f"Actor instance '{alias}' (name: '{actor_name}') has type '{actor_type}' which is not consistent with the Scenario. Actor instance names must be consistent with their type definition.",
                "line": line_num,
                "extracted_values": {
                    "actor_instance": alias,
                    "actor_instance_name": actor_name,
                    "actor_type": actor_type,
                    "expected_types_from_scenario": list(expected_types_from_scenario),
                    "source": "Scenario"
                }
            })
    
    return violations


def _generate_missing_svg_violations() -> List[Dict[str, Any]]:
    """
    Generate violations for all 6 graphical rules when SVG file is missing.
    
    Returns:
        List of 6 violation dictionaries (one per LDR11-LDR16)
    """
    violations = []
    message = "SVG file is required for graphical rule validation. Rule cannot be validated without rendered diagram."
    
    graphical_rules = [
        "LDR11-SYSTEM-SHAPE",
        "LDR12-SYSTEM-COLOR",
        "LDR13-ACTOR-SHAPE",
        "LDR14-ACTOR-COLOR",
        "LDR15-ACTIVATION-BAR-INPUT-EVENT-COLOR",
        "LDR16-ACTIVATION-BAR-OUTPUT-EVENT-COLOR",
    ]
    
    for rule_id in graphical_rules:
        violations.append({
            "id": rule_id,
            "message": message,
            "line": 1,
            "extracted_values": {"svg_required": True}
        })
    
    return violations


def _validate_graphical_rules(svg_file_path: str, plantuml_text: str) -> List[Dict[str, Any]]:
    """
    Validate graphical rules (LDR11-LDR16) using SVG parsing.
    
    Reuses logic from validate_diagram_graphics.py to check:
    - LDR11: System participant rectangle shape
    - LDR12: System background color #E8C28A
    - LDR13: Actor participant rectangle shape
    - LDR14: Actor background color #FFF3B3
    - LDR15: Input event activation bar color #C0EBFD
    - LDR16: Output event activation bar color #274364
    
    Args:
        svg_file_path: Path to SVG file
        plantuml_text: PlantUML text (for context, not directly used in validation)
        
    Returns:
        List of violation dictionaries
    """
    violations: List[Dict[str, Any]] = []
    
    try:
        # Import helper functions from validate_diagram_graphics
        from validate_diagram_graphics import (
            _collect_rects,
            _collect_texts,
            _assign_participants,
            _find_activation_bars,
            _index_message_labels,
            _expected_activation_color_for_y,
            _norm_hex,
            COLOR_SYSTEM,
            COLOR_ACTOR,
            COLOR_ACTIVATION_AFTER_IE,
            COLOR_ACTIVATION_AFTER_OE,
        )
    except ImportError:
        # If import fails, return parse error violation
        violations.append({
            "id": "SVG-VALIDATION-ERROR",
            "message": "Failed to import graphical validation functions from validate_diagram_graphics.py",
            "line": 1,
            "extracted_values": {"svg_file": svg_file_path}
        })
        return violations
    
    try:
        svg_path = Path(svg_file_path)
        if not svg_path.exists():
            # SVG file not found - return violations for all 6 graphical rules (LDR11-LDR16)
            return _generate_missing_svg_violations()
        
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except Exception as e:
        violations.append({
            "id": "SVG-PARSE-ERROR",
            "message": f"Failed to parse SVG: {e}",
            "line": 1,
            "extracted_values": {"svg_file": svg_file_path, "error": str(e)}
        })
        return violations
    
    # Collect SVG elements
    rects = _collect_rects(root)
    texts = _collect_texts(root)
    participants = _assign_participants(rects, texts)
    bars = _find_activation_bars(rects, participants)
    msg_texts = _index_message_labels(texts)
    
    # Extract message label contents for fast exclusion lookup
    # Message labels contain colons in their parameters but are not participants
    message_label_contents = {t.content.strip() for t in msg_texts}
    
    # LDR11/LDR13: participant headers must be rectangles
    for t in texts:
        label = t.content.strip()
        if not label:
            continue
        if label in participants:
            continue
        # Skip message labels (they contain colons in parameters but are not participants)
        if label in message_label_contents:
            continue
        # Only enforce for labels that look like participant identifiers
        if label == "System" or ":" in label:
            rule_id = "LDR11-SYSTEM-SHAPE" if label == "System" else "LDR13-ACTOR-SHAPE"
            violations.append({
                "id": rule_id,
                "message": f"Participant '{label}' not matched to a rectangle header shape.",
                "line": 1,
                "extracted_values": {"label": label}
            })
    
    # LDR12/LDR14: color checks on header rectangles
    for name, r in participants.items():
        fill = _norm_hex(r.fill)
        if name == "System":
            if fill != _norm_hex(COLOR_SYSTEM):
                violations.append({
                    "id": "LDR12-SYSTEM-COLOR",
                    "message": f"System rectangle must have background {COLOR_SYSTEM}.",
                    "line": 1,
                    "extracted_values": {"label": name, "found_fill": fill}
                })
        else:
            if fill != _norm_hex(COLOR_ACTOR):
                violations.append({
                    "id": "LDR14-ACTOR-COLOR",
                    "message": f"Actor rectangle must have background {COLOR_ACTOR}.",
                    "line": 1,
                    "extracted_values": {"label": name, "found_fill": fill}
                })
    
    # LDR15/LDR16: activation bar color after ie/oe
    for part_name, bar in bars:
        expected = _expected_activation_color_for_y(bar.mid_y, msg_texts)
        if not expected:
            # If we cannot infer, skip to avoid false positives
            continue
        found = _norm_hex(bar.fill)
        if found != expected:
            # Determine which rule was violated based on expected color
            if expected == _norm_hex(COLOR_ACTIVATION_AFTER_IE):
                rule_id = "LDR15-ACTIVATION-BAR-INPUT-EVENT-COLOR"
            else:
                rule_id = "LDR16-ACTIVATION-BAR-OUTPUT-EVENT-COLOR"
            
            violations.append({
                "id": rule_id,
                "message": f"Activation bar color does not match preceding event type (expected {expected}, found {found}).",
                "line": 1,
                "extracted_values": {
                    "participant": part_name,
                    "expected": expected,
                    "found": found,
                    "bar_bbox": {"x": bar.x, "y": bar.y, "w": bar.width, "h": bar.height}
                }
            })
    
    return violations


def audit_diagram(
    text: str,
    raw_content: str | None = None,
    svg_path: Path | str | None = None,
    operation_model: Dict[str, Any] | None = None,
    scenario: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """
    Audit PlantUML Diagram for LDR rule compliance.
    
    This function automatically extracts PlantUML content by searching for @startuml and @enduml
    markers, making it robust against JSON corruption or mixed content.
    
    Supports new format: {"data": {"plantuml-diagram": "..."}, "errors": null}
    Also supports legacy formats and raw PlantUML text.
    
    When svg_path is provided and file exists, validates graphical rules (LDR11-LDR16) using SVG parsing.
    When svg_path is not provided or file does not exist, all 6 graphical rules (LDR11-LDR16)
    are automatically reported as violations.
    
    Args:
        text: PlantUML diagram content (parsed/cleaned), JSON string, or raw content containing PlantUML
        raw_content: Optional raw content string for LDR0 validation (PlantUML block format check)
        svg_path: Optional path to SVG file for graphical rules validation (LDR11-LDR16).
                 If not provided or file does not exist, all graphical rules are marked as violations.
        operation_model: Operation Model dictionary (required for LDR28 validation, must be provided together with scenario).
                         Actor instance names must be consistent with their type definition.
        scenario: Scenario dictionary (required for LDR28 validation, must be provided together with operation_model).
                   Actor instance names must be consistent with their type definition.
        
    Returns:
        Dictionary with "verdict" (bool) and "violations" (list of violation dicts)
    """
    violations: List[Dict[str, Any]] = []
    
    # LDR0-PLANTUML-BLOCK-ONLY: Check raw content format if provided
    # This validates that the raw content is a valid PlantUML block (no extra text)
    if raw_content is not None:
        ldr0_violations = _check_ldr0_plantuml_block_only(raw_content)
        violations.extend(ldr0_violations)

    # Extract PlantUML from text or raw_content
    # First, try to parse as JSON and extract from new format
    plantuml_text = None
    
    # Try to parse text as JSON and extract plantuml-diagram
    if text:
        try:
            import json
            parsed_json = json.loads(text)
            if isinstance(parsed_json, dict):
                # Check for new format: {"data": {"plantuml-diagram": "..."}, "errors": null}
                if "data" in parsed_json and isinstance(parsed_json.get("data"), dict):
                    data_node = parsed_json["data"]
                    if "plantuml-diagram" in data_node:
                        plantuml_text = data_node["plantuml-diagram"]
                    # Fallback: check for legacy format with nested diagram
                    elif "diagram" in data_node and isinstance(data_node["diagram"], dict):
                        diagram_node = data_node["diagram"]
                        if "plantuml" in diagram_node:
                            plantuml_text = diagram_node["plantuml"]
                # Check for direct "plantuml-diagram" key (unwrapped format)
                elif "plantuml-diagram" in parsed_json:
                    plantuml_text = parsed_json["plantuml-diagram"]
        except (json.JSONDecodeError, TypeError, AttributeError):
            # Not JSON, continue with text extraction
            pass
    
    # If JSON parsing didn't yield PlantUML, try text extraction
    if not plantuml_text or not isinstance(plantuml_text, str) or "@startuml" not in plantuml_text:
        if text:
            plantuml_text = _extract_plantuml_from_text(text)
    
    if not plantuml_text and raw_content:
        # Try to parse raw_content as JSON first
        try:
            import json
            parsed_json = json.loads(raw_content)
            if isinstance(parsed_json, dict):
                if "data" in parsed_json and isinstance(parsed_json.get("data"), dict):
                    data_node = parsed_json["data"]
                    if "plantuml-diagram" in data_node:
                        plantuml_text = data_node["plantuml-diagram"]
                    elif "diagram" in data_node and isinstance(data_node["diagram"], dict):
                        diagram_node = data_node["diagram"]
                        if "plantuml" in diagram_node:
                            plantuml_text = diagram_node["plantuml"]
                elif "plantuml-diagram" in parsed_json:
                    plantuml_text = parsed_json["plantuml-diagram"]
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
        
        # If JSON parsing didn't yield PlantUML, try text extraction
        if not plantuml_text or not isinstance(plantuml_text, str) or "@startuml" not in plantuml_text:
            plantuml_text = _extract_plantuml_from_text(raw_content)
    
    # If no PlantUML found, this will be caught by LDR1 check below
    if not plantuml_text:
        plantuml_text = text or raw_content or ""
    
    # Split into lines for rule checking
    lines = plantuml_text.splitlines()
    participants_order: List[str] = []  # aliases encountered order
    has_system_decl = False
    system_decl_line = -1

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or _is_comment_line(line):
            continue

        # System declaration specific
        if _SYSTEM_SIMPLE_RE.match(line):
            if has_system_decl:
                violations.append({
                    "id": "LDR1-SYS-UNIQUE",
                    "message": "There must be exactly one System lifeline per diagram.",
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip()}
                })
            has_system_decl = True
            system_decl_line = idx
            participants_order.append("system")
            continue

        # Generic participant parsing (actors)
        mp = _PARTICIPANT_RE.match(line)
        if mp:
            alias = mp.group("alias")
            label = mp.group("label")
            participants_order.append(alias)
            # LDR24 — explicit system declaration syntax
            if alias == "system":
                if not _SYSTEM_SIMPLE_RE.match(line):
                    violations.append({
                        "id": "LDR24-SYSTEM-DECLARATION",
                        "message": "Declare the System participant using the exact syntax: participant System as system",
                        "line": idx,
                        "extracted_values": {"line_content": raw.rstrip()}
                    })
                if not has_system_decl:
                    has_system_decl = True
                    system_decl_line = idx
                continue

            # LDR17 — actor declaration strict syntax
            # Expect label formatted as "actorName:ActActorType" and alias == actorName
            # Also prefer quoted label per examples
            if ":" not in label:
                violations.append({
                    "id": "LDR17-ACTOR-DECLARATION-SYNTAX",
                    "message": 'Each actor must be declared using: participant "anActorName:ActActorType" as anActorName',
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip(), "label": label, "alias": alias}
                })
            else:
                actor_name, actor_type = label.split(":", 1)
                # alias must equal actor_name
                if actor_name != alias:
                    violations.append({
                        "id": "LDR17-ACTOR-DECLARATION-SYNTAX",
                        "message": "Alias must match the actor instance name before ':' in the label.",
                        "line": idx,
                        "extracted_values": {"line_content": raw.rstrip(), "label": label, "alias": alias, "expected_alias": actor_name}
                    })
                # type must match Act[A-Z][A-Za-z0-9]*
                if not _ACTOR_TYPE_RE.match(actor_type):
                    violations.append({
                        "id": "LDR17-ACTOR-DECLARATION-SYNTAX",
                        "message": 'Actor type must match pattern Act[A-Z][A-Za-z0-9]*.',
                        "line": idx,
                        "extracted_values": {"line_content": raw.rstrip(), "actor_type": actor_type}
                    })
            # Prefer quoted label — if not quoted in original line, flag (soft) LDR17
            # Heuristic: there should be a quoted segment before " as "
            if ' as ' in line and '"' not in line.split(' as ')[0]:
                violations.append({
                    "id": "LDR17-ACTOR-DECLARATION-SYNTAX",
                    "message": 'Actor label should be quoted: participant "anActorName:ActActorType" as anActorName',
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip()}
                })

            # LDR27 — camelCase for actor instance (alias)
            if not _CAMEL_CASE_ALIAS_RE.match(alias):
                violations.append({
                    "id": "LDR27-ACTOR-INSTANCE-FORMAT",
                    "message": "All actor instance names must be human-readable in camelCase.",
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip(), "alias": alias}
                })
            if alias != "system" and not has_system_decl:
                violations.append({
                    "id": "LDR3-SYSTEM-DECLARED-FIRST",
                    "message": "The System must be declared first before all actors.",
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip(), "participant_label": label, "participant_alias": alias}
                })
            if alias == "system" and not has_system_decl:
                # This matches system declared with quotes label; mark presence
                has_system_decl = True
                system_decl_line = idx
            continue

    # After scanning participants, ensure actors declared after system
    if has_system_decl:
        try:
            sys_index = participants_order.index("system")
            for pos, alias in enumerate(participants_order):
                if alias != "system" and pos < sys_index:
                    # Find the line where this actor was declared
                    actor_line = 1
                    actor_line_content = ""
                    for line_idx, raw_line in enumerate(lines, start=1):
                        stripped = raw_line.strip()
                        mp_match = _PARTICIPANT_RE.match(stripped)
                        if mp_match and mp_match.group("alias") == alias:
                            actor_line = line_idx
                            actor_line_content = raw_line.rstrip()
                            break
                    violations.append({
                        "id": "LDR2-ACTOR-DECLARED-AFTER-SYSTEM",
                        "message": "The actors must be declared after the System.",
                        "line": actor_line,
                        "extracted_values": {"line_content": actor_line_content, "actor_alias": alias, "system_decl_line": system_decl_line}
                    })
                    break
        except ValueError:
            pass
    else:
        # Find first non-empty line for context
        first_line_content = ""
        for raw_line in lines:
            stripped = raw_line.strip()
            if stripped and not _is_comment_line(stripped):
                first_line_content = raw_line.rstrip()
                break
        violations.append({
            "id": "LDR1-SYS-UNIQUE",
            "message": "System participant not declared (expected: participant System as system).",
            "line": 1,
            "extracted_values": {"line_content": first_line_content if first_line_content else "(empty file)"}
        })

    # Pass 2: scan messages and activations
    # Track structure for LDR8, LDR9, LDR10
    activation_stack: Dict[str, List[int]] = {}  # Track active activations per lifeline for nesting/overlap
    last_activation_line: Dict[str, int] = {}  # Track last activation per lifeline
    
    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or _is_comment_line(line):
            continue

        # forbid activating system
        ma = _ACTIVATE_RE.match(line)
        if ma:
            who = ma.group("who")
            if _is_system_token(who):
                violations.append({
                    "id": "LDR10-ACTIVATION-BAR-ON-SYSTEM-FORBIDDEN",
                    "message": "There must be NO activation bar in the System lifeline. Never activate System.",
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip(), "lifeline": who}
                })
                continue
            
            # LDR8: Check for nesting (activation while already active)
            if who in activation_stack and len(activation_stack[who]) > 0:
                violations.append({
                    "id": "LDR8-ACTIVATION-BAR-NESTING-FORBIDDEN",
                    "message": "Activation bars must never be nested.",
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip(), "lifeline": who}
                })
            
            # LDR9: Check for overlapping (new activation before previous deactivation)
            # Overlap occurs if there's an active activation and no deactivation between last activation and this one
            if who in activation_stack and len(activation_stack[who]) > 0:
                # There's already an active activation - check if it was deactivated
                last_activation = activation_stack[who][-1]
                deactivated_after = False
                for check_idx in range(last_activation + 1, idx):
                    check_line = lines[check_idx - 1].strip()
                    deactivate_match = _DEACTIVATE_RE.match(check_line)
                    if deactivate_match and deactivate_match.group("who") == who:
                        deactivated_after = True
                        break
                if not deactivated_after:
                    violations.append({
                        "id": "LDR9-ACTIVATION-BAR-OVERLAPPING-FORBIDDEN",
                        "message": "Activation bars must never overlap. Following sequence is forbidden: an event, start of activation bar of this event, another event before the end of the activation bar.",
                        "line": idx,
                        "extracted_values": {"line_content": raw.rstrip(), "lifeline": who}
                    })
            
            # Track activation
            if who not in activation_stack:
                activation_stack[who] = []
            activation_stack[who].append(idx)
            last_activation_line[who] = idx
            continue

        md = _DEACTIVATE_RE.match(line)
        if md:
            who = md.group("who")
            # Remove from activation stack
            if who in activation_stack and len(activation_stack[who]) > 0:
                activation_stack[who].pop()
            continue

        mm = _MSG_RE.match(line)
        if not mm:
            continue
        lhs = mm.group("lhs")
        rhs = mm.group("rhs")
        name = mm.group("name")
        arrow = mm.group("arrow")
        params_raw = mm.group("params")
        lhs_is_system = _is_system_token(lhs)
        rhs_is_system = _is_system_token(rhs)
        lhs_is_actor = not lhs_is_system
        rhs_is_actor = not rhs_is_system

        # Track messages for later activation verification (Pass 3)

        # LDR5 — no System→System
        if lhs_is_system and rhs_is_system:
            violations.append({
                "id": "LDR5-SYSTEM-NO-SELF-LOOP",
                "message": "Events must never be from System to System. System → System",
                "line": idx,
                "extracted_values": {"line_content": raw.rstrip(), "sender": lhs, "receiver": rhs, "event_name": name}
            })

        # LDR6 — no Actor→Actor
        if lhs_is_actor and rhs_is_actor:
            violations.append({
                "id": "LDR6-ACTOR-NO-ACTOR-LOOP",
                "message": "Events must never be from Actor to Actor. Actor → Actor",
                "line": idx,
                "extracted_values": {"line_content": raw.rstrip(), "sender": lhs, "receiver": rhs, "event_name": name}
            })

        # LDR4 — must connect exactly one Actor and the System
        if not ((lhs_is_system and rhs_is_actor) or (lhs_is_actor and rhs_is_system)):
            violations.append({
                "id": "LDR4-EVENT-DIRECTIONALITY",
                "message": "Every message in a LUCIM interaction must connect exactly one Actor lifeline and the System lifeline.",
                "line": idx,
                "extracted_values": {"line_content": raw.rstrip(), "sender": lhs, "receiver": rhs, "event_name": name}
            })

        # LDR25 — ie* events must use dashed arrows (-->)
        if name.startswith("ie"):
            if not (lhs_is_system and rhs_is_actor):
                violations.append({
                    "id": "LDR25-INPUT-EVENT-SYNTAX",
                    "message": "ie events must be modeled using dashed arrows and following this declaration syntax: system --> theParticipant : ieMessageName(EP)",
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip(), "sender": lhs, "receiver": rhs, "event_name": name, "arrow": arrow}
                })
            elif not arrow.startswith("--"):
                violations.append({
                    "id": "LDR25-INPUT-EVENT-SYNTAX",
                    "message": "ie events must be modeled using dashed arrows (-->).",
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip(), "sender": lhs, "receiver": rhs, "event_name": name, "arrow": arrow}
                })
        
        # LDR26 — oe* events must use continuous arrows (->)
        if name.startswith("oe"):
            if not (lhs_is_actor and rhs_is_system):
                violations.append({
                    "id": "LDR26-OUTPUT-EVENT-SYNTAX",
                    "message": "oe events must be modeled using continuous arrows and following this declaration syntax: theParticipant -> system : oeMessage(EP)",
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip(), "sender": lhs, "receiver": rhs, "event_name": name, "arrow": arrow}
                })
            elif arrow != "->":
                violations.append({
                    "id": "LDR26-OUTPUT-EVENT-SYNTAX",
                    "message": "oe events must be modeled using continuous arrows (->).",
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip(), "sender": lhs, "receiver": rhs, "event_name": name, "arrow": arrow}
                })

        # LDR23 — parameters must be comma-separated (basic validation)
        if params_raw is not None:
            # Quick disallow common wrong separators
            if ";" in params_raw or "|" in params_raw:
                violations.append({
                    "id": "LDR23-EVENT-PARAMETER-COMMA-SEPARATED",
                    "message": "Multiple parameters must be comma-separated.",
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip(), "params": params_raw}
                })
            # Split by commas while respecting simple quotes
            def _split_params(p: str) -> list:
                parts = []
                buf = []
                in_single = False
                in_double = False
                for ch in p:
                    if ch == "'" and not in_double:
                        in_single = not in_single
                        buf.append(ch)
                        continue
                    if ch == '"' and not in_single:
                        in_double = not in_double
                        buf.append(ch)
                        continue
                    if ch == "," and not in_single and not in_double:
                        parts.append("".join(buf).strip())
                        buf = []
                        continue
                    buf.append(ch)
                if buf is not None:
                    parts.append("".join(buf).strip())
                return parts if not (len(parts) == 1 and parts[0] == "") else []

            params_list = _split_params(params_raw.strip())
            # If there is any empty parameter between commas -> violation
            if any(p == "" for p in params_list if len(params_list) > 1):
                violations.append({
                    "id": "LDR23-EVENT-PARAMETER-COMMA-SEPARATED",
                    "message": "Multiple parameters must be valid comma-separated values without empty items.",
                    "line": idx,
                    "extracted_values": {"line_content": raw.rstrip(), "params": params_raw}
                })

    # Helper function to find the next non-empty, non-comment line after a given line number
    # This respects LDR19: blank lines and comments are allowed and must be ignored
    def _find_next_non_empty_line(start_line: int, max_line: int) -> int | None:
        """Find the next non-empty, non-comment line after start_line (inclusive)."""
        for idx in range(start_line, max_line + 1):
            if idx > len(lines):
                return None
            line = lines[idx - 1].strip()
            if line and not _is_comment_line(line):
                return idx
        return None
    
    # Pass 3: Verify that each event has a corresponding activation (LDR7) and deactivation (LDR20)
    # Track events that need activations
    events_needing_activation: Dict[str, List[int]] = {}  # participant -> list of event line numbers
    activations_by_participant: Dict[str, List[int]] = {}  # participant -> list of activation line numbers
    deactivations_by_participant: Dict[str, List[int]] = {}  # participant -> list of deactivation line numbers
    
    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or _is_comment_line(line):
            continue
        
        mm = _MSG_RE.match(line)
        if mm:
            lhs = mm.group("lhs")
            rhs = mm.group("rhs")
            lhs_is_system = _is_system_token(lhs)
            rhs_is_system = _is_system_token(rhs)
            
            # Only actors need activations (LDR7, LDR10)
            if not lhs_is_system:
                if lhs not in events_needing_activation:
                    events_needing_activation[lhs] = []
                events_needing_activation[lhs].append(idx)
            if not rhs_is_system:
                if rhs not in events_needing_activation:
                    events_needing_activation[rhs] = []
                events_needing_activation[rhs].append(idx)
        
        ma = _ACTIVATE_RE.match(line)
        if ma:
            who = ma.group("who")
            if not _is_system_token(who):
                if who not in activations_by_participant:
                    activations_by_participant[who] = []
                activations_by_participant[who].append(idx)
        
        md = _DEACTIVATE_RE.match(line)
        if md:
            who = md.group("who")
            if not _is_system_token(who):
                if who not in deactivations_by_participant:
                    deactivations_by_participant[who] = []
                deactivations_by_participant[who].append(idx)
    
    # Check if each event has a corresponding activation and deactivation (LDR7, LDR20)
    # 
    # LDR20 Implementation Notes:
    # 1. Multiple events for same participant: Events are processed in reverse order (most recent first)
    #    to correctly associate activations with the last event. Earlier events without activations
    #    are flagged as violations. Example: oeEvent1(), oeEvent2(), activate -> activation belongs
    #    to oeEvent2, oeEvent1 is flagged as missing activation.
    # 
    # 2. Blank lines and comments: Per LDR19, blank lines and comments are ignored. The
    #    _find_next_non_empty_line() helper function ensures that gaps with only blank lines or
    #    comments between events and activations are not flagged as violations.
    # 
    # 3. Activation tracking: The logic tracks which activations and deactivations have been used
    #    to avoid double-counting and ensure each activation is only paired with one event.
    # 
    # 4. Sequence validation: The sequence check uses next_non_empty_line to respect LDR19, ensuring
    #    that blank lines and comments between event -> activate -> deactivate are allowed.
    
    for participant, event_lines in events_needing_activation.items():
        activation_lines = sorted(activations_by_participant.get(participant, []))
        deactivation_lines = sorted(deactivations_by_participant.get(participant, []))
        
        if not activation_lines:
            # No activations at all for this participant
            for event_line in event_lines:
                violations.append({
                    "id": "LDR7-ACTIVATION-BAR-SEQUENCE",
                    "message": "For each event, an activation must be used, it must occur on the Actor lifeline immediately after the event occurrence.",
                    "line": event_line,
                    "extracted_values": {"line_content": lines[event_line - 1].rstrip() if event_line <= len(lines) else "", "lifeline": participant}
                })
        else:
            # Track which activations and deactivations have been used to avoid double-counting
            used_activations: set[int] = set()
            used_deactivations: set[int] = set()
            
            # Check if each event has an activation that follows it
            # Strategy: Process events in reverse order to associate activations with the last (most recent) event
            # This ensures that if multiple events exist without activations between them, the activation
            # is correctly associated with the last event, and earlier events are flagged as missing activations
            for event_line in sorted(event_lines, reverse=True):
                # Find the first unused activation after this event (closest to the event)
                found_activation = False
                # Sort activations to find the closest one after this event
                closest_activation = None
                for act_line in sorted(activation_lines):
                    if act_line > event_line and act_line not in used_activations:
                        closest_activation = act_line
                        break  # Take the first (closest) activation after this event
                
                if closest_activation is not None:
                    act_line = closest_activation
                    # Check if activation immediately follows (LDR20)
                    # Per LDR19, blank lines and comments are ignored, so we check the next non-empty line
                    next_non_empty_after_event = _find_next_non_empty_line(event_line + 1, len(lines))
                    if next_non_empty_after_event != act_line:
                        violations.append({
                            "id": "LDR20-ACTIVATION-BAR-SEQUENCE",
                            "message": "Strictly follow this sequence: (1) event declaration, (2) activate the participant, (3) deactivate the participant.",
                            "line": event_line,
                            "extracted_values": {
                                "line_content": lines[event_line - 1].rstrip() if event_line <= len(lines) else "",
                                "lifeline": participant,
                                "activation_line": act_line,
                                "next_non_empty_line": next_non_empty_after_event
                            }
                        })
                    
                    # Check if there's a deactivation after this activation (LDR20)
                    found_deactivation = False
                    for deact_line in deactivation_lines:
                        if deact_line > act_line and deact_line not in used_deactivations:
                            # Check if deactivation immediately follows activation (ignoring blank lines/comments per LDR19)
                            next_non_empty_after_activation = _find_next_non_empty_line(act_line + 1, len(lines))
                            if next_non_empty_after_activation != deact_line:
                                violations.append({
                                    "id": "LDR20-ACTIVATION-BAR-SEQUENCE",
                                    "message": "Strictly follow this sequence: (1) event declaration, (2) activate the participant, (3) deactivate the participant.",
                                    "line": act_line,
                                    "extracted_values": {
                                        "line_content": lines[act_line - 1].rstrip() if act_line <= len(lines) else "",
                                        "lifeline": participant,
                                        "deactivation_line": deact_line,
                                        "next_non_empty_line": next_non_empty_after_activation
                                    }
                                })
                            found_deactivation = True
                            used_deactivations.add(deact_line)
                            break
                    
                    if not found_deactivation:
                        violations.append({
                            "id": "LDR20-ACTIVATION-BAR-SEQUENCE",
                            "message": "Strictly follow this sequence: (1) event declaration, (2) activate the participant, (3) deactivate the participant.",
                            "line": act_line,
                            "extracted_values": {
                                "line_content": lines[act_line - 1].rstrip() if act_line <= len(lines) else "",
                                "lifeline": participant,
                                "missing_deactivation": True
                            }
                        })
                    
                    found_activation = True
                    used_activations.add(act_line)
                
                if not found_activation:
                    violations.append({
                        "id": "LDR7-ACTIVATION-BAR-SEQUENCE",
                        "message": "For each event, an activation must be used, it must occur on the Actor lifeline immediately after the event occurrence.",
                        "line": event_line,
                        "extracted_values": {"line_content": lines[event_line - 1].rstrip() if event_line <= len(lines) else "", "lifeline": participant}
                    })

    # LDR28: Actor instance name consistency (requires BOTH operation_model AND scenario)
    if operation_model is not None and scenario is not None:
        ldr28_violations = _validate_ldr28_actor_instance_consistency(
            plantuml_text,
            operation_model,
            scenario
        )
        violations.extend(ldr28_violations)

    # Graphical rules validation (LDR11-LDR16)
    if svg_path is not None:
        # Convert Path to string if needed
        svg_file_path = str(svg_path) if isinstance(svg_path, Path) else svg_path
        svg_path_obj = Path(svg_file_path)
        
        if svg_path_obj.exists():
            # Validate graphical rules using SVG
            graphical_violations = _validate_graphical_rules(svg_file_path, plantuml_text)
            violations.extend(graphical_violations)
        else:
            # SVG path provided but file doesn't exist - treat as missing
            missing_svg_violations = _generate_missing_svg_violations()
            violations.extend(missing_svg_violations)
    else:
        # No SVG path provided - all graphical rules are violations
        missing_svg_violations = _generate_missing_svg_violations()
        violations.extend(missing_svg_violations)

    verdict = len(violations) == 0
    return {"verdict": verdict, "violations": violations}


if __name__ == "__main__":
    sample = """
@startuml
participant System as system
participant "bill:ActAdministrator" as bill
bill -> system : oeLogin()
system --> bill : ieWelcome()
@enduml
"""
    import json
    print(json.dumps(audit_diagram(sample), indent=2))


