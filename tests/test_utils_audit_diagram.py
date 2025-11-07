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
    assert "LDR3-SYSTEM-DECLARED-FIRST" in ids or "LDR2-ACTOR-DECLARED-AFTER-SYSTEM" in ids
    assert "LDR5-SYSTEM-NO-SELF-LOOP" in ids
    assert "LDR6-ACTOR-NO-ACTOR-LOOP" in ids
    assert "LDR10-ACTIVATION-BAR-ON-SYSTEM-FORBIDDEN" in ids


