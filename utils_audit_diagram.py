"""
Deterministic auditor for LUCIM PlantUML Diagram rules (Step 3) — no LLM.

Input: PlantUML textual diagram (.puml content string)
Output: { "verdict": bool, "violations": [ { "id": str, "message": str, "line": int } ] }

Subset of rules implemented (pragmatic coverage):
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
- LDR20-ACTIVATION-BAR-SEQUENCE: strict sequence: event → activate → deactivate
- LDR25-INPUT-EVENT-SYNTAX: ie* events must use dashed arrows (-->)
- LDR26-OUTPUT-EVENT-SYNTAX: oe* events must use continuous arrows (->)
- LDR11-LDR16 (graphical rules): not enforced strictly; out-of-scope for text-only validation
"""
from __future__ import annotations

import re
from typing import Dict, List, Any


_PARTICIPANT_RE = re.compile(r"^participant\s+\"?(?P<label>[^\"]+)\"?\s+as\s+(?P<alias>\w+)(\s+#[0-9A-Fa-f]{6})?\s*$")
_SYSTEM_SIMPLE_RE = re.compile(r"^participant\s+System\s+as\s+system(\s+#[0-9A-Fa-f]{6})?\s*$")
_MSG_RE = re.compile(r"^(?P<lhs>\S+)\s*(?P<arrow>--?>)\s*(?P<rhs>\S+)\s*:\s*(?P<name>\w+)\s*\((?P<params>[^)]*)\)\s*$")
_ACTIVATE_RE = re.compile(r"^activate\s+(?P<who>\w+)\b")
_DEACTIVATE_RE = re.compile(r"^deactivate\s+(?P<who>\w+)\b")


def _is_system_token(tok: str) -> bool:
    t = tok.strip()
    return t == "system" or t == "System"


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


def audit_diagram(text: str, raw_content: str | None = None) -> Dict[str, Any]:
    """
    Audit PlantUML Diagram for LDR rule compliance.
    
    Args:
        text: PlantUML diagram content (parsed/cleaned)
        raw_content: Optional raw content string for LDR0 validation (PlantUML block format check)
        
    Returns:
        Dictionary with "verdict" (bool) and "violations" (list of violation dicts)
    """
    violations: List[Dict[str, Any]] = []
    
    # LDR0-PLANTUML-BLOCK-ONLY: Check raw content format if provided
    if raw_content is not None:
        ldr0_violations = _check_ldr0_plantuml_block_only(raw_content)
        violations.extend(ldr0_violations)

    lines = (text or "").splitlines()
    participants_order: List[str] = []  # aliases encountered order
    has_system_decl = False
    system_decl_line = -1

    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("//"):
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
            if stripped and not stripped.startswith("//"):
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
        if not line or line.startswith("//"):
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

    # Pass 3: Verify that each event has a corresponding activation (LDR7) and deactivation (LDR20)
    # Track events that need activations
    events_needing_activation: Dict[str, List[int]] = {}  # participant -> list of event line numbers
    activations_by_participant: Dict[str, List[int]] = {}  # participant -> list of activation line numbers
    deactivations_by_participant: Dict[str, List[int]] = {}  # participant -> list of deactivation line numbers
    
    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("//"):
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
            # Check if each event has an activation that follows it
            for event_line in event_lines:
                # Find the first activation after this event
                found_activation = False
                for act_line in activation_lines:
                    if act_line > event_line:
                        # Check if activation immediately follows (LDR20)
                        if act_line != event_line + 1:
                            violations.append({
                                "id": "LDR20-ACTIVATION-BAR-SEQUENCE",
                                "message": "Strictly follow this sequence: (1) event declaration, (2) activate the participant, (3) deactivate the participant.",
                                "line": event_line,
                                "extracted_values": {"line_content": lines[event_line - 1].rstrip() if event_line <= len(lines) else "", "lifeline": participant, "activation_line": act_line}
                            })
                        
                        # Check if there's a deactivation after this activation (LDR20)
                        found_deactivation = False
                        for deact_line in deactivation_lines:
                            if deact_line > act_line:
                                # Check if deactivation immediately follows activation
                                if deact_line != act_line + 1:
                                    violations.append({
                                        "id": "LDR20-ACTIVATION-BAR-SEQUENCE",
                                        "message": "Strictly follow this sequence: (1) event declaration, (2) activate the participant, (3) deactivate the participant.",
                                        "line": act_line,
                                        "extracted_values": {"line_content": lines[act_line - 1].rstrip() if act_line <= len(lines) else "", "lifeline": participant, "deactivation_line": deact_line}
                                    })
                                found_deactivation = True
                                break
                        
                        if not found_deactivation:
                            violations.append({
                                "id": "LDR20-ACTIVATION-BAR-SEQUENCE",
                                "message": "Strictly follow this sequence: (1) event declaration, (2) activate the participant, (3) deactivate the participant.",
                                "line": act_line,
                                "extracted_values": {"line_content": lines[act_line - 1].rstrip() if act_line <= len(lines) else "", "lifeline": participant}
                            })
                        
                        found_activation = True
                        break
                
                if not found_activation:
                    violations.append({
                        "id": "LDR7-ACTIVATION-BAR-SEQUENCE",
                        "message": "For each event, an activation must be used, it must occur on the Actor lifeline immediately after the event occurrence.",
                        "line": event_line,
                        "extracted_values": {"line_content": lines[event_line - 1].rstrip() if event_line <= len(lines) else "", "lifeline": participant}
                    })

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


