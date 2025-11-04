"""
Deterministic auditor for LUCIM Scenario textual rules (Step 2) — no LLM.

Input: PlantUML textual scenario (string)
Output: { "verdict": bool, "violations": [ { "id": str, "message": str, "line": int } ] }

Rules implemented (from persona Step 2 doc):
- SS1-MESSAGE-DIRECTIONALITY: every message connects one Actor and the System
- AS3-SYS-ACT-ALLOWED-EVENTS: System↔Actor only
- AS4-SYS-NO-SELF-LOOP: no System→System
- AS6-ACT-NO-ACT-ACT-EVENTS: no Actor→Actor
- TCS4-IE-SYNTAX: ie events use dashed arrow: system --> actor : ieName(...)
- TCS5-OE-SYNTAX: oe events use continuous arrow: actor -> system : oeName(...)
- Prefix constraints: ie* for System→Actor, oe* for Actor→System
"""
from __future__ import annotations

import re
from typing import Dict, List, Any


_MSG_RE = re.compile(r"^(?P<lhs>\S+)\s*(?P<arrow>--?>|-->>|-->)\s*(?P<rhs>\S+)\s*:\s*(?P<name>\w+)\s*\((?P<params>[^)]*)\)\s*$")


def _is_system(token: str) -> bool:
    t = token.strip()
    return t == "system" or t == "System"


def _is_actor_token(token: str) -> bool:
    t = token.strip()
    # Heuristic: not system
    return not _is_system(t)


def audit_scenario(text: str) -> Dict[str, Any]:
    violations: List[Dict[str, Any]] = []
    lines = (text or "").splitlines()

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

        # AS4 — forbid System→System
        if lhs_is_system and rhs_is_system:
            violations.append({
                "id": "AS4-SYS-NO-SELF-LOOP",
                "message": "System→System message is forbidden.",
                "line": idx,
            })

        # AS6 — forbid Actor→Actor
        if lhs_is_actor and rhs_is_actor and not lhs_is_system and not rhs_is_system:
            violations.append({
                "id": "AS6-ACT-NO-ACT-ACT-EVENTS",
                "message": "Actor→Actor message is forbidden.",
                "line": idx,
            })

        # SS1 / AS3 — must be System↔Actor only
        if not ((lhs_is_system and rhs_is_actor) or (lhs_is_actor and rhs_is_system)):
            violations.append({
                "id": "SS1-MESSAGE-DIRECTIONALITY",
                "message": "Messages must connect exactly one Actor and the System.",
                "line": idx,
            })

        # TCS4 — IE: dashed arrow, system --> actor, name starts with ie
        if name.startswith("ie"):
            if not (lhs_is_system and rhs_is_actor and arrow == "-->"):
                violations.append({
                    "id": "TCS4-IE-SYNTAX",
                    "message": "ie events must be: system --> actor : ieXxx(...)",
                    "line": idx,
                })

        # TCS5 — OE: solid arrow, actor -> system, name starts with oe
        if name.startswith("oe"):
            if not (lhs_is_actor and rhs_is_system and arrow == "->"):
                violations.append({
                    "id": "TCS5-OE-SYNTAX",
                    "message": "oe events must be: actor -> system : oeXxx(...)",
                    "line": idx,
                })

        # Prefix/direction consistency checks (redundant but explicit)
        if name.startswith("ie") and lhs_is_actor and rhs_is_system:
            violations.append({
                "id": "AS8-IE-EVENT-DIRECTION",
                "message": "Input Event ie* must be System → Actor (not Actor → System).",
                "line": idx,
            })
        if name.startswith("oe") and lhs_is_system and rhs_is_actor:
            violations.append({
                "id": "AS9-OE-EVENT-DIRECTION",
                "message": "Output Event oe* must be Actor → System (not System → Actor).",
                "line": idx,
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


