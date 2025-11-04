"""
Deterministic auditor for LUCIM PlantUML Diagram rules (Step 3) — no LLM.

Input: PlantUML textual diagram (.puml content string)
Output: { "verdict": bool, "violations": [ { "id": str, "message": str, "line": int } ] }

Subset of rules implemented (pragmatic coverage):
- AS2-SYS-DECLARED-FIRST: System declared before all actors
- AS5-ACT-DECLARED-AFTER-SYS: actors declared after System
- SS3-SYS-UNIQUE-IDENTITY: exactly one System participant named "System"
- SS1-MESSAGE-DIRECTIONALITY: messages connect exactly one Actor and System
- AS4-SYS-NO-SELF-LOOP: no System→System
- AS6-ACT-NO-ACT-ACT-EVENTS: no Actor→Actor
- TCS10-AB-NO-ACTIVATION-BAR-ON-SYSTEM: never activate system
- TCS9-AB-SEQUENCE (lightweight): basic check that activate/deactivate for a given lifeline do not appear before any message referencing that lifeline (heuristic)
- GCS5/GCS6 color hints: not enforced strictly; out-of-scope for text-only validation (colors optional in PlantUML)
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


def audit_diagram(text: str) -> Dict[str, Any]:
    violations: List[Dict[str, Any]] = []

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
                    "id": "SS3-SYS-UNIQUE-IDENTITY",
                    "message": "System participant must be unique.",
                    "line": idx,
                })
            has_system_decl = True
            system_decl_line = idx
            participants_order.append("system")
            continue

        # Generic participant parsing (actors)
        mp = _PARTICIPANT_RE.match(line)
        if mp:
            alias = mp.group("alias")
            participants_order.append(alias)
            if alias != "system" and not has_system_decl:
                violations.append({
                    "id": "AS2-SYS-DECLARED-FIRST",
                    "message": "The System must be declared first before all actors.",
                    "line": idx,
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
                    violations.append({
                        "id": "AS5-ACT-DECLARED-AFTER-SYS",
                        "message": "Actors must be declared after the System.",
                        "line": system_decl_line if system_decl_line > 0 else 1,
                    })
                    break
        except ValueError:
            pass
    else:
        violations.append({
            "id": "SS3-SYS-UNIQUE-IDENTITY",
            "message": "System participant not declared (expected: participant System as system).",
            "line": 1,
        })

    # Pass 2: scan messages and activations
    seen_message_for: Dict[str, bool] = {}
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
                    "id": "TCS10-AB-NO-ACTIVATION-BAR-ON-SYSTEM",
                    "message": "There must be NO activation bar on the System lifeline.",
                    "line": idx,
                })
            # record activation presence (lightweight sequence heuristic)
            if who not in seen_message_for:
                violations.append({
                    "id": "TCS9-AB-SEQUENCE",
                    "message": "Activation should follow a message for the same lifeline.",
                    "line": idx,
                })
            continue

        md = _DEACTIVATE_RE.match(line)
        if md:
            who = md.group("who")
            if who not in seen_message_for:
                violations.append({
                    "id": "TCS9-AB-SEQUENCE",
                    "message": "Deactivation should follow an activation/message for the same lifeline.",
                    "line": idx,
                })
            continue

        mm = _MSG_RE.match(line)
        if not mm:
            continue
        lhs = mm.group("lhs")
        rhs = mm.group("rhs")
        name = mm.group("name")
        lhs_is_system = _is_system_token(lhs)
        rhs_is_system = _is_system_token(rhs)
        lhs_is_actor = not lhs_is_system
        rhs_is_actor = not rhs_is_system

        # Record message presence per lifeline for AB heuristic
        seen_message_for[lhs] = True
        seen_message_for[rhs] = True

        # AS4 — no System→System
        if lhs_is_system and rhs_is_system:
            violations.append({
                "id": "AS4-SYS-NO-SELF-LOOP",
                "message": "System→System message is forbidden.",
                "line": idx,
            })

        # AS6 — no Actor→Actor
        if lhs_is_actor and rhs_is_actor:
            violations.append({
                "id": "AS6-ACT-NO-ACT-ACT-EVENTS",
                "message": "Actor→Actor message is forbidden.",
                "line": idx,
            })

        # SS1 — must connect exactly one Actor and the System
        if not ((lhs_is_system and rhs_is_actor) or (lhs_is_actor and rhs_is_system)):
            violations.append({
                "id": "SS1-MESSAGE-DIRECTIONALITY",
                "message": "Messages must connect exactly one Actor and the System.",
                "line": idx,
            })

        # Direction-name sanity (optional)
        if name.startswith("ie") and not (lhs_is_system and rhs_is_actor):
            violations.append({
                "id": "AS8-IE-EVENT-DIRECTION",
                "message": "ie* should be System → Actor.",
                "line": idx,
            })
        if name.startswith("oe") and not (lhs_is_actor and rhs_is_system):
            violations.append({
                "id": "AS9-OE-EVENT-DIRECTION",
                "message": "oe* should be Actor → System.",
                "line": idx,
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


