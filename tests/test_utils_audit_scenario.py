import pytest
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from utils_audit_scenario import audit_scenario


def test_scenario_valid_minimal():
    text = """
system --> bill : ieWelcome()
bill -> system : oeAck()
"""
    res = audit_scenario(text)
    assert res["verdict"] is True
    assert res["violations"] == []


def test_scenario_invalid_rules():
    text = """
system -> system : ieInternal()
user1 -> user2 : oeChat()
bill -> system : ieWrong()
system --> bill : oeWrong()
"""
    res = audit_scenario(text)
    assert res["verdict"] is False
    ids = {v["id"] for v in res["violations"]}
    assert "AS4-SYS-NO-SELF-LOOP" in ids
    assert "AS6-ACT-NO-ACT-ACT-EVENTS" in ids
    assert "TCS4-IE-SYNTAX" in ids or "AS8-IE-EVENT-DIRECTION" in ids
    assert "TCS5-OE-SYNTAX" in ids or "AS9-OE-EVENT-DIRECTION" in ids


