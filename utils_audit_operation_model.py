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
        "name": str,     # optional event name
        "sender": str,   # instance name ("system" or actor instance)
        "receiver": str  # instance name ("system" or actor instance)
      }
  ]
}

Rules implemented (from RULES_LUCIM_Operation_model.md):
- LEM1-ACT-TYPE-FORMAT: actor type names FirstCapitalLetterFormat, prefixed by "Act"
- LEM2-ACT-INSTANCE-FORMAT: actor instance names in camelCase
- LEM2-IE-EVENT-NAME-FORMAT: input event names in camelCase
- LEM3-OE-EVENT-NAME-FORMAT: output event names in camelCase
- LEM4-IE-EVENT-DIRECTION: IE must be System → Actor
- LEM5-OE-EVENT-DIRECTION: OE must be Actor → System
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

    # Note: The current ruleset (RULES_LUCIM_Operation_model.md) does not define
    # a normative check for unique System naming; we therefore do not emit
    # violations about System identity here to stay aligned with the rules file.

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
            evt_name = (evt.get("name") or "").strip()

            sender_l = sender.lower()
            receiver_l = receiver.lower()

            sender_is_system = sender_l == "system"
            receiver_is_system = receiver_l == "system"
            sender_is_actor = sender_l in actor_index
            receiver_is_actor = receiver_l in actor_index

            # LEM2 / LEM3 — event name format checks when provided
            if evt_name:
                if kind == "ie" and not _is_camel_case(evt_name):
                    violations.append({
                        "id": "LEM2-IE-EVENT-NAME-FORMAT",
                        "message": "All input event names must be human-readable, in camelCase.",
                        "location": _location(evt, "event.name")
                    })
                if kind == "oe" and not _is_camel_case(evt_name):
                    violations.append({
                        "id": "LEM3-OE-EVENT-NAME-FORMAT",
                        "message": "All output event names must be human-readable, in camelCase.",
                        "location": _location(evt, "event.name")
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




