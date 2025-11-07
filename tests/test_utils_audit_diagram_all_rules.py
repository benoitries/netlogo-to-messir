"""
Comprehensive test suite for all LDR* rules in utils_audit_diagram.

This test suite covers all LUCIM Diagram Rules (LDR*) with both valid and non-compliant cases.
"""
import pytest
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from utils_audit_diagram import audit_diagram

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "diagram"


def _read(name: str) -> str:
    """Read a fixture file."""
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


# ============================================================================
# VALID CASES
# ============================================================================

def test_ldr_valid_minimal():
    """Test a minimal valid diagram."""
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


def test_ldr_valid_with_activations():
    """Test a valid diagram with proper activation bars."""
    res = audit_diagram(_read("valid_with_activations.puml"))
    assert res["verdict"] is True
    assert res["violations"] == []


def test_ldr_valid_from_fixture():
    """Test the valid fixture."""
    res = audit_diagram(_read("valid.puml"))
    assert res["verdict"] is True
    assert res["violations"] == []


# ============================================================================
# LDR1-SYS-UNIQUE: Exactly one System lifeline
# ============================================================================

def test_ldr1_missing_system():
    """LDR1: Missing System declaration."""
    res = audit_diagram(_read("missing_system.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR1-SYS-UNIQUE" for v in res["violations"])


def test_ldr1_multiple_systems():
    """LDR1: Multiple System declarations."""
    res = audit_diagram(_read("multiple_systems.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR1-SYS-UNIQUE" for v in res["violations"])


# ============================================================================
# LDR2-ACTOR-DECLARED-AFTER-SYSTEM: Actors must be declared after System
# ============================================================================

def test_ldr2_actor_before_system():
    """LDR2: Actor declared before System."""
    res = audit_diagram(_read("actor_before_system.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR2-ACTOR-DECLARED-AFTER-SYSTEM" for v in res["violations"])


# ============================================================================
# LDR3-SYSTEM-DECLARED-FIRST: System must be declared first
# ============================================================================

def test_ldr3_system_not_first():
    """LDR3: System not declared first."""
    res = audit_diagram(_read("actor_before_system.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR3-SYSTEM-DECLARED-FIRST" for v in res["violations"])


# ============================================================================
# LDR4-EVENT-DIRECTIONALITY: Messages must connect exactly one Actor and System
# ============================================================================

def test_ldr4_wrong_event_direction():
    """LDR4: Wrong event direction (System->Actor for oe, Actor->System for ie)."""
    res = audit_diagram(_read("wrong_event_direction.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR4-EVENT-DIRECTIONALITY" for v in res["violations"])


# ============================================================================
# LDR5-SYSTEM-NO-SELF-LOOP: No System→System events
# ============================================================================

def test_ldr5_system_self_loop():
    """LDR5: System→System message is forbidden."""
    res = audit_diagram(_read("system_self_loop.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR5-SYSTEM-NO-SELF-LOOP" for v in res["violations"])


# ============================================================================
# LDR6-ACTOR-NO-ACTOR-LOOP: No Actor→Actor events
# ============================================================================

def test_ldr6_actor_actor_message():
    """LDR6: Actor→Actor message is forbidden."""
    res = audit_diagram(_read("actor_actor_message.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR6-ACTOR-NO-ACTOR-LOOP" for v in res["violations"])


# ============================================================================
# LDR7-ACTIVATION-BAR-SEQUENCE: Activation must occur immediately after event
# ============================================================================

def test_ldr7_missing_activation():
    """LDR7: Missing activation after event."""
    res = audit_diagram(_read("missing_activation.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR7-ACTIVATION-BAR-SEQUENCE" for v in res["violations"])


# ============================================================================
# LDR8-ACTIVATION-BAR-NESTING-FORBIDDEN: No nested activation bars
# ============================================================================

def test_ldr8_nested_activation():
    """LDR8: Nested activation bars are forbidden."""
    res = audit_diagram(_read("nested_activation.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR8-ACTIVATION-BAR-NESTING-FORBIDDEN" for v in res["violations"])


# ============================================================================
# LDR9-ACTIVATION-BAR-OVERLAPPING-FORBIDDEN: No overlapping activation bars
# ============================================================================

def test_ldr9_overlapping_activation():
    """LDR9: Overlapping activation bars are forbidden."""
    res = audit_diagram(_read("overlapping_activation.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR9-ACTIVATION-BAR-OVERLAPPING-FORBIDDEN" for v in res["violations"])


# ============================================================================
# LDR10-ACTIVATION-BAR-ON-SYSTEM-FORBIDDEN: No activation bar on System
# ============================================================================

def test_ldr10_activation_on_system():
    """LDR10: Activation bar on System is forbidden."""
    res = audit_diagram(_read("activation_on_system.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR10-ACTIVATION-BAR-ON-SYSTEM-FORBIDDEN" for v in res["violations"])


# ============================================================================
# LDR20-ACTIVATION-BAR-SEQUENCE: Strict sequence: event → activate → deactivate
# ============================================================================

def test_ldr20_wrong_activation_sequence():
    """LDR20: Activation not immediately after event."""
    res = audit_diagram(_read("wrong_activation_sequence.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR20-ACTIVATION-BAR-SEQUENCE" for v in res["violations"])


def test_ldr20_missing_deactivation():
    """LDR20: Missing deactivation after activation."""
    res = audit_diagram(_read("missing_deactivation.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR20-ACTIVATION-BAR-SEQUENCE" for v in res["violations"])


# ============================================================================
# LDR25-INPUT-EVENT-SYNTAX: ie* events must use dashed arrows (-->)
# ============================================================================

def test_ldr25_wrong_ie_arrow():
    """LDR25: ie* event using continuous arrow instead of dashed."""
    res = audit_diagram(_read("wrong_ie_arrow.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR25-INPUT-EVENT-SYNTAX" for v in res["violations"])


def test_ldr25_ie_wrong_direction():
    """LDR25: ie* event in wrong direction (should be System→Actor)."""
    text = """
@startuml
participant System as system
participant "bill:ActAdministrator" as bill
bill --> system : ieWelcome()
@enduml
"""
    res = audit_diagram(text)
    assert res["verdict"] is False
    assert any(v["id"] == "LDR25-INPUT-EVENT-SYNTAX" for v in res["violations"])


# ============================================================================
# LDR26-OUTPUT-EVENT-SYNTAX: oe* events must use continuous arrows (->)
# ============================================================================

def test_ldr26_wrong_oe_arrow():
    """LDR26: oe* event using dashed arrow instead of continuous."""
    res = audit_diagram(_read("wrong_oe_arrow.puml"))
    assert res["verdict"] is False
    assert any(v["id"] == "LDR26-OUTPUT-EVENT-SYNTAX" for v in res["violations"])


def test_ldr26_oe_wrong_direction():
    """LDR26: oe* event in wrong direction (should be Actor→System)."""
    text = """
@startuml
participant System as system
participant "bill:ActAdministrator" as bill
system -> bill : oeLogin()
@enduml
"""
    res = audit_diagram(text)
    assert res["verdict"] is False
    assert any(v["id"] == "LDR26-OUTPUT-EVENT-SYNTAX" for v in res["violations"])


# ============================================================================
# COMPLEX CASES: Multiple violations
# ============================================================================

def test_multiple_violations():
    """Test a diagram with multiple violations."""
    text = """
@startuml
participant "bill:ActAdmin" as bill
participant System as system
system -> system : ieLoop()
activate system
bill -> user : oeChat()
system -> bill : oeWrong()
bill --> system : ieWrong()
@enduml
"""
    res = audit_diagram(text)
    assert res["verdict"] is False
    ids = {v["id"] for v in res["violations"]}
    # Should have multiple violations
    assert len(res["violations"]) > 1
    assert "LDR3-SYSTEM-DECLARED-FIRST" in ids or "LDR2-ACTOR-DECLARED-AFTER-SYSTEM" in ids
    assert "LDR5-SYSTEM-NO-SELF-LOOP" in ids
    assert "LDR6-ACTOR-NO-ACTOR-LOOP" in ids
    assert "LDR10-ACTIVATION-BAR-ON-SYSTEM-FORBIDDEN" in ids
    assert "LDR25-INPUT-EVENT-SYNTAX" in ids or "LDR26-OUTPUT-EVENT-SYNTAX" in ids


def test_complete_valid_sequence():
    """Test a complete valid sequence with all elements."""
    text = """
@startuml
participant System as system
participant "bill:ActAdministrator" as bill
participant "alice:ActUser" as alice

bill -> system : oeLogin()
activate bill
deactivate bill

system --> bill : ieWelcome()
activate bill
deactivate bill

alice -> system : oeRequest()
activate alice
deactivate alice

system --> alice : ieResponse()
activate alice
deactivate alice
@enduml
"""
    res = audit_diagram(text)
    assert res["verdict"] is True
    assert res["violations"] == []

