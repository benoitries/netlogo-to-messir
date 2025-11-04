"""
Deterministic auditor for LUCIM Operation Model (Step 1) — no LLM.

Input: operation model JSON (dict-like)
Output: { "verdict": bool, "violations": [ { "id": str, "message": str, "location": str } ] }

Minimal schema (tolerant):
{
  "system": { "name": str },
  "actors": [ { "name": str, "type": str } ],
  "events": [
      {
        "kind": "ie" | "oe",
        "sender": str,   # instance name ("system" or actor instance)
        "receiver": str  # instance name ("system" or actor instance)
      }
  ]
}

Rules implemented (from persona Step 1 doc):
- AS1-SYS-UNIQUE: exactly one System named "System"
- SS3-SYS-UNIQUE-IDENTITY: one logical System lifeline, canonical rendered name "System"
- AS7/NAM2 actor type format: FirstCapitalLetterFormat prefixed by "Act"
- NAM1 actor instance format: camelCase
- AS3 allowed events System↔Actor only
- AS4 no System→System
- AS6 no Actor→Actor
- AS8 IE direction: System→Actor
- AS9 OE direction: Actor→System
"""
from __future__ import annotations

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
    # Accept dict or list; normalize to iterable of dicts and index by lowercase name
    if isinstance(actors, dict):
        iterable = actors.values()
    elif isinstance(actors, list):
        iterable = actors
    else:
        iterable = []
    index: Dict[str, Dict[str, Any]] = {}
    for a in iterable:
        if not isinstance(a, dict):
            continue
        nm = (a.get("name") or "").strip()
        if nm:
            index[nm.lower()] = a
    return index


def _location(item: Any, fallback: str) -> str:
    # The environment JSON may not include positions; provide stable location hints
    name = None
    if isinstance(item, dict):
        name = item.get("name") or item.get("id") or item.get("message")
    return name or fallback


def audit_environment(env: Dict[str, Any]) -> Dict[str, Any]:
    violations: List[Dict[str, str]] = []

    system = (env or {}).get("system") or {}
    system_name = (system.get("name") or "").strip()

    # AS1 / SS3 — exactly one System named "System"
    if system_name != "System":
        violations.append({
            "id": "AS1-SYS-UNIQUE",
            "message": 'There must be exactly one System per model that is always named "System".',
            "location": "system.name"
        })
        violations.append({
            "id": "SS3-SYS-UNIQUE-IDENTITY",
            "message": 'There SHALL be exactly one logical System lifeline named "System".',
            "location": "system.name"
        })

    actors_node = env.get("actors") or []
    # Normalize to list of dicts for iteration
    if isinstance(actors_node, dict):
        actors_list = [v for v in actors_node.values() if isinstance(v, dict)]
    elif isinstance(actors_node, list):
        actors_list = [v for v in actors_node if isinstance(v, dict)]
    else:
        actors_list = []
    actor_index = _index_actors(actors_node)

    # LEM2 / LEM1 — actor instance/type formatting
    for actor in actors_list:
        inst_name = (actor.get("name") or "").strip()
        type_name = (actor.get("type") or "").strip()
        if not _is_camel_case(inst_name):
            violations.append({
                "id": "LEM2-ACT-INSTANCE-FORMAT",
                "message": "Actor instance names must be human-readable, in camelCase.",
                "location": _location(actor, "actor")
            })
        if not _is_act_type(type_name):
            violations.append({
                "id": "LEM1-ACT-TYPE-FORMAT",
                "message": 'Actor type name must be FirstCapitalLetterFormat and prefixed by "Act".',
                "location": _location(actor, "actor")
            })

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
            inp = actor.get("input_events")
            if isinstance(inp, dict):
                for ev in inp.values():
                    if isinstance(ev, dict):
                        events.append({
                            "kind": "ie",
                            "sender": "system",
                            "receiver": inst_name
                        })
            outp = actor.get("output_events")
            if isinstance(outp, dict):
                for ev in outp.values():
                    if isinstance(ev, dict):
                        events.append({
                            "kind": "oe",
                            "sender": inst_name,
                            "receiver": "system"
                        })
    if events:
        for evt in events:
            kind = (evt.get("kind") or "").lower().strip()  # "ie" or "oe" expected
            sender = (evt.get("sender") or "").strip()
            receiver = (evt.get("receiver") or "").strip()

            sender_l = sender.lower()
            receiver_l = receiver.lower()

            sender_is_system = sender_l == "system"
            receiver_is_system = receiver_l == "system"
            sender_is_actor = sender_l in actor_index
            receiver_is_actor = receiver_l in actor_index

            # AS4 — System→System forbidden
            if sender_is_system and receiver_is_system:
                violations.append({
                    "id": "AS4-SYS-NO-SELF-LOOP",
                    "message": "Events must never be from System to System.",
                    "location": _location(evt, "event")
                })

            # AS6 — Actor→Actor forbidden
            if sender_is_actor and receiver_is_actor:
                violations.append({
                    "id": "AS6-ACT-NO-ACT-ACT-EVENTS",
                    "message": "Events must never be from Actor to Actor.",
                    "location": _location(evt, "event")
                })

            # AS3 — System↔Actor only
            if not ((sender_is_system and receiver_is_actor) or (sender_is_actor and receiver_is_system)):
                violations.append({
                    "id": "AS3-SYS-ACT-ALLOWED-EVENTS",
                    "message": "Events must always be between the System and an Actor (no Actor↔Actor, no System↔System).",
                    "location": _location(evt, "event")
                })

            # LEM4 — IE direction System→Actor
            if kind == "ie":
                if not (sender_is_system and receiver_is_actor):
                    violations.append({
                        "id": "LEM4-IE-EVENT-DIRECTION",
                        "message": "Input Event (ie) must be System → Actor.",
                        "location": _location(evt, "event")
                    })

            # LEM5 — OE direction Actor→System
            if kind == "oe":
                if not (sender_is_actor and receiver_is_system):
                    violations.append({
                        "id": "LEM5-OE-EVENT-DIRECTION",
                        "message": "Output Event (oe) must be Actor → System.",
                        "location": _location(evt, "event")
                    })

    verdict = len(violations) == 0
    return {"verdict": verdict, "violations": violations}


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
    print(json.dumps(audit_environment(sample), indent=2))




