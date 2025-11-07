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
    assert "AS2-SYS-DECLARED-FIRST" in ids or "AS5-ACT-DECLARED-AFTER-SYS" in ids


def test_system_self_loop():
    res = audit_diagram(_read("system_self_loop.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "AS4-SYS-NO-SELF-LOOP" for v in res["violations"]) 


def test_actor_actor_message_forbidden():
    res = audit_diagram(_read("actor_actor_message.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "AS6-ACT-NO-ACT-ACT-EVENTS" for v in res["violations"]) 


