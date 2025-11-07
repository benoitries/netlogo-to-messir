from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from utils_audit_scenario import audit_scenario


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "scenario"


def test_valid_scenario_is_compliant():
    text = (FIXTURES_DIR / "valid.scenario").read_text(encoding="utf-8")
    res = audit_scenario(text)
    assert res["verdict"] is True
    assert res["violations"] == []


def test_actor_actor_forbidden():
    text = (FIXTURES_DIR / "actor_actor.scenario").read_text(encoding="utf-8")
    res = audit_scenario(text)
    assert res["verdict"] is False
    assert any(v["id"] == "LSC8-ACTOR-NO-SELF-LOOP" for v in res["violations"]) 


def test_system_system_forbidden():
    text = (FIXTURES_DIR / "system_system.scenario").read_text(encoding="utf-8")
    res = audit_scenario(text)
    assert res["verdict"] is False
    assert any(v["id"] == "LSC7-SYSTEM-NO-SELF-LOOP" for v in res["violations"]) 


def test_wrong_ie_arrow():
    text = (FIXTURES_DIR / "wrong_ie_arrow.scenario").read_text(encoding="utf-8")
    res = audit_scenario(text)
    assert res["verdict"] is False
    assert any(v["id"] == "LSC9-INPUT-EVENT-ALLOWED-EVENTS" for v in res["violations"]) 


def test_wrong_oe_arrow():
    text = (FIXTURES_DIR / "wrong_oe_arrow.scenario").read_text(encoding="utf-8")
    res = audit_scenario(text)
    assert res["verdict"] is False
    assert any(v["id"] == "LSC10-OUTPUT-EVENT-DIRECTION" for v in res["violations"]) 


