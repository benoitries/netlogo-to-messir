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
    assert "LSC7-SYSTEM-NO-SELF-LOOP" in ids
    assert "LSC8-ACTOR-NO-SELF-LOOP" in ids
    assert "LSC9-INPUT-EVENT-ALLOWED-EVENTS" in ids
    assert "LSC10-OUTPUT-EVENT-DIRECTION" in ids


