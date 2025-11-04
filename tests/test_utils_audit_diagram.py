import pytest
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from utils_audit_diagram import audit_diagram


def test_diagram_valid_minimal():
    text = """
@startuml
participant System as system
participant "bill:ActAdministrator" as bill
bill -> system : oeLogin()
system --> bill : ieWelcome()
@enduml
"""
    res = audit_diagram(text)
    assert res["verdict"] is True
    assert res["violations"] == []


def test_diagram_invalid_order_and_activation_on_system():
    text = """
@startuml
participant "bill:ActAdmin" as bill
participant System as system
system -> system : ieLoop()
activate system
bill -> user : oeChat()
@enduml
"""
    res = audit_diagram(text)
    assert res["verdict"] is False
    ids = {v["id"] for v in res["violations"]}
    assert "AS2-SYS-DECLARED-FIRST" in ids or "AS5-ACT-DECLARED-AFTER-SYS" in ids
    assert "AS4-SYS-NO-SELF-LOOP" in ids
    assert "AS6-ACT-NO-ACT-ACT-EVENTS" in ids
    assert "TCS10-AB-NO-ACTIVATION-BAR-ON-SYSTEM" in ids


