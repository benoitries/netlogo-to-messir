from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from utils_audit_diagram import audit_diagram


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "diagram"


def _read(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_valid_diagram_is_compliant():
    res = audit_diagram(_read("valid.puml"))
    assert res["verdict"] is True
    assert res["violations"] == []


def test_actor_before_system():
    res = audit_diagram(_read("actor_before_system.puml"))
    assert res["verdict"] is False
    ids = {v["id"] for v in res["violations"]}
    assert "LDR3-SYSTEM-DECLARED-FIRST" in ids or "LDR2-ACTOR-DECLARED-AFTER-SYSTEM" in ids


def test_system_self_loop():
    res = audit_diagram(_read("system_self_loop.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR5-SYSTEM-NO-SELF-LOOP" for v in res["violations"]) 


def test_actor_actor_message_forbidden():
    res = audit_diagram(_read("actor_actor_message.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR6-ACTOR-NO-ACTOR-LOOP" for v in res["violations"])


def test_missing_system():
    res = audit_diagram(_read("missing_system.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR1-SYS-UNIQUE" for v in res["violations"])


def test_multiple_systems():
    res = audit_diagram(_read("multiple_systems.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR1-SYS-UNIQUE" for v in res["violations"])


def test_wrong_ie_arrow():
    res = audit_diagram(_read("wrong_ie_arrow.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR25-INPUT-EVENT-SYNTAX" for v in res["violations"])


def test_wrong_oe_arrow():
    res = audit_diagram(_read("wrong_oe_arrow.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR26-OUTPUT-EVENT-SYNTAX" for v in res["violations"])


def test_activation_on_system():
    res = audit_diagram(_read("activation_on_system.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR10-ACTIVATION-BAR-ON-SYSTEM-FORBIDDEN" for v in res["violations"])


def test_missing_activation():
    res = audit_diagram(_read("missing_activation.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR7-ACTIVATION-BAR-SEQUENCE" for v in res["violations"])


def test_nested_activation():
    res = audit_diagram(_read("nested_activation.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR8-ACTIVATION-BAR-NESTING-FORBIDDEN" for v in res["violations"])


def test_overlapping_activation():
    res = audit_diagram(_read("overlapping_activation.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR9-ACTIVATION-BAR-OVERLAPPING-FORBIDDEN" for v in res["violations"])


def test_wrong_activation_sequence():
    res = audit_diagram(_read("wrong_activation_sequence.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR20-ACTIVATION-BAR-SEQUENCE" for v in res["violations"])


def test_missing_deactivation():
    res = audit_diagram(_read("missing_deactivation.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR20-ACTIVATION-BAR-SEQUENCE" for v in res["violations"])


def test_wrong_event_direction():
    res = audit_diagram(_read("wrong_event_direction.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR4-EVENT-DIRECTIONALITY" for v in res["violations"])


def test_valid_with_activations():
    res = audit_diagram(_read("valid_with_activations.puml"))
    assert res["verdict"] is True
    assert res["violations"] == []


