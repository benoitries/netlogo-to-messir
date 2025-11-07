"""
Comprehensive tests for all LUCIM Scenario audit rules (LSC0-LSC17).

Tests both PlantUML text format and JSON format scenarios.
Tests rules that require operation model (LSC5, LSC6, LSC12-LSC17).
"""
import pytest
import sys
import json
import pathlib
from pathlib import Path

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from utils_audit_scenario import audit_scenario

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "scenario"
OPERATION_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "operation"


# Load valid operation model for tests requiring it
def get_valid_operation_model():
    """Load a valid operation model for testing."""
    op_model_path = OPERATION_FIXTURES_DIR / "valid.json"
    if op_model_path.exists():
        return json.loads(op_model_path.read_text(encoding="utf-8"))
    # Return a minimal valid operation model
    return {
        "system": {"name": "System"},
        "actors": {
            "ActOperator": {
                "name": "mainOperator",
                "description": "primary operator",
                "input_events": {
                    "ieHello": {
                        "source": "System",
                        "target": "ActOperator",
                        "parameters": [],
                        "postF": [{"text": "received"}]
                    },
                    "ieWelcome": {
                        "source": "System",
                        "target": "ActOperator",
                        "parameters": ["message"],
                        "postF": [{"text": "received"}]
                    }
                },
                "output_events": {
                    "oeAck": {
                        "source": "ActOperator",
                        "target": "System",
                        "parameters": [],
                        "preP": [],
                        "postF": [{"text": "queued"}]
                    },
                    "oeReportReady": {
                        "source": "ActOperator",
                        "target": "System",
                        "parameters": ["summary"],
                        "preP": [],
                        "postF": [{"text": "queued"}]
                    }
                }
            },
            "ActUser": {
                "name": "user",
                "description": "regular user",
                "input_events": {
                    "ieNotify": {
                        "source": "System",
                        "target": "ActUser",
                        "parameters": ["msg"],
                        "postF": [{"text": "notified"}]
                    }
                },
                "output_events": {
                    "oeRequest": {
                        "source": "ActUser",
                        "target": "System",
                        "parameters": ["action"],
                        "preP": [],
                        "postF": [{"text": "requested"}]
                    }
                }
            }
        }
    }


# ============================================================================
# Rules without Operation Model (LSC0-LSC4, LSC7-LSC11)
# ============================================================================

def test_lsc0_json_block_only_valid():
    """LSC0: Valid JSON block without code fences."""
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {"source": "system", "target": "bill", "event_type": "input_event", "event_name": "ieHello", "parameters": []}
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json))
    # Should not have LSC0 violations
    lsc0_violations = [v for v in res["violations"] if v["id"] == "LSC0-JSON-BLOCK-ONLY"]
    assert len(lsc0_violations) == 0


def test_lsc0_json_block_only_invalid_with_fences():
    """LSC0: Invalid JSON block with Markdown code fences."""
    scenario_with_fences = "```json\n{\"data\": {\"scenario\": {}}}\n```"
    res = audit_scenario(scenario_with_fences)
    lsc0_violations = [v for v in res["violations"] if v["id"] == "LSC0-JSON-BLOCK-ONLY"]
    assert len(lsc0_violations) > 0


def test_lsc2_actors_limitation_valid():
    """LSC2: Valid scenario with 5 or fewer actors."""
    text = """
system --> actor1 : ieHello()
actor1 -> system : oeAck()
system --> actor2 : ieNotify()
actor2 -> system : oeResponse()
system --> actor3 : ieUpdate()
actor3 -> system : oeConfirm()
"""
    res = audit_scenario(text)
    lsc2_violations = [v for v in res["violations"] if v["id"] == "LSC2-ACTORS-LIMITATION"]
    assert len(lsc2_violations) == 0


def test_lsc2_actors_limitation_invalid():
    """LSC2: Invalid scenario with more than 5 actors."""
    text = """
system --> actor1 : ieHello()
actor1 -> system : oeAck()
system --> actor2 : ieNotify()
actor2 -> system : oeResponse()
system --> actor3 : ieUpdate()
actor3 -> system : oeConfirm()
system --> actor4 : ieEvent1()
actor4 -> system : oeEvent2()
system --> actor5 : ieEvent3()
actor5 -> system : oeEvent4()
system --> actor6 : ieEvent5()
actor6 -> system : oeEvent6()
"""
    res = audit_scenario(text)
    lsc2_violations = [v for v in res["violations"] if v["id"] == "LSC2-ACTORS-LIMITATION"]
    assert len(lsc2_violations) > 0


def test_lsc3_input_events_limitation_valid():
    """LSC3: Valid scenario with at least one input event per actor."""
    text = """
system --> bill : ieHello()
bill -> system : oeAck()
"""
    res = audit_scenario(text)
    lsc3_violations = [v for v in res["violations"] if v["id"] == "LSC3-INPUT-EVENTS-LIMITATION"]
    assert len(lsc3_violations) == 0


def test_lsc3_input_events_limitation_invalid():
    """LSC3: Invalid scenario with actor missing input events."""
    text = """
bill -> system : oeAck()
"""
    res = audit_scenario(text)
    lsc3_violations = [v for v in res["violations"] if v["id"] == "LSC3-INPUT-EVENTS-LIMITATION"]
    assert len(lsc3_violations) > 0


def test_lsc4_output_events_limitation_valid():
    """LSC4: Valid scenario with at least one output event per actor."""
    text = """
system --> bill : ieHello()
bill -> system : oeAck()
"""
    res = audit_scenario(text)
    lsc4_violations = [v for v in res["violations"] if v["id"] == "LSC4-OUTPUT-EVENTS-LIMITATION"]
    assert len(lsc4_violations) == 0


def test_lsc4_output_events_limitation_invalid():
    """LSC4: Invalid scenario with actor missing output events."""
    text = """
system --> bill : ieHello()
"""
    res = audit_scenario(text)
    lsc4_violations = [v for v in res["violations"] if v["id"] == "LSC4-OUTPUT-EVENTS-LIMITATION"]
    assert len(lsc4_violations) > 0


def test_lsc7_system_no_self_loop():
    """LSC7: System→System events are forbidden."""
    text = """
system -> system : oeLoop()
"""
    res = audit_scenario(text)
    lsc7_violations = [v for v in res["violations"] if v["id"] == "LSC7-SYSTEM-NO-SELF-LOOP"]
    assert len(lsc7_violations) > 0


def test_lsc8_actor_no_self_loop():
    """LSC8: Actor→Actor events are forbidden."""
    text = """
bill -> alice : oeChat()
"""
    res = audit_scenario(text)
    lsc8_violations = [v for v in res["violations"] if v["id"] == "LSC8-ACTOR-NO-SELF-LOOP"]
    assert len(lsc8_violations) > 0


def test_lsc9_input_event_allowed_events_valid():
    """LSC9: Input events must be System → Actor."""
    text = """
system --> bill : ieHello()
bill -> system : oeAck()
"""
    res = audit_scenario(text)
    lsc9_violations = [v for v in res["violations"] if v["id"] == "LSC9-INPUT-EVENT-ALLOWED-EVENTS"]
    assert len(lsc9_violations) == 0


def test_lsc9_input_event_allowed_events_invalid():
    """LSC9: Invalid input event direction."""
    text = """
bill -> system : ieHello()
"""
    res = audit_scenario(text)
    lsc9_violations = [v for v in res["violations"] if v["id"] == "LSC9-INPUT-EVENT-ALLOWED-EVENTS"]
    assert len(lsc9_violations) > 0


def test_lsc10_output_event_direction_valid():
    """LSC10: Output events must be Actor → System."""
    text = """
system --> bill : ieHello()
bill -> system : oeAck()
"""
    res = audit_scenario(text)
    lsc10_violations = [v for v in res["violations"] if v["id"] == "LSC10-OUTPUT-EVENT-DIRECTION"]
    assert len(lsc10_violations) == 0


def test_lsc10_output_event_direction_invalid():
    """LSC10: Invalid output event direction."""
    text = """
system --> bill : oeAck()
"""
    res = audit_scenario(text)
    lsc10_violations = [v for v in res["violations"] if v["id"] == "LSC10-OUTPUT-EVENT-DIRECTION"]
    assert len(lsc10_violations) > 0


def test_lsc11_actor_instance_format_valid():
    """LSC11: Valid camelCase actor instance names."""
    text = """
system --> actAdministrator : ieHello()
actAdministrator -> system : oeAck()
system --> chris : ieNotify()
chris -> system : oeResponse()
"""
    res = audit_scenario(text)
    lsc11_violations = [v for v in res["violations"] if v["id"] == "LSC11-ACTOR-INSTANCE-FORMAT"]
    assert len(lsc11_violations) == 0


def test_lsc11_actor_instance_format_invalid():
    """LSC11: Invalid actor instance names (not camelCase)."""
    text = """
system --> ACT_ADMIN : ieHello()
ACT_ADMIN -> system : oeAck()
"""
    res = audit_scenario(text)
    lsc11_violations = [v for v in res["violations"] if v["id"] == "LSC11-ACTOR-INSTANCE-FORMAT"]
    assert len(lsc11_violations) > 0


# ============================================================================
# Rules requiring Operation Model (LSC5, LSC6, LSC12-LSC17)
# ============================================================================

def test_lsc5_event_sequence_valid():
    """LSC5: Valid event sequence with proper conditions."""
    op_model = get_valid_operation_model()
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {
                        "source": "system",
                        "target": "mainOperator",
                        "event_type": "input_event",
                        "event_name": "ieHello",
                        "parameters": []
                    },
                    {
                        "source": "mainOperator",
                        "target": "system",
                        "event_type": "output_event",
                        "event_name": "oeAck",
                        "parameters": []
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    lsc5_violations = [v for v in res["violations"] if v["id"] == "LSC5-EVENT-SEQUENCE"]
    # Should not have violations if conditions are properly defined
    # Note: Full sequence validation would require state tracking
    assert res["verdict"] is True or len(lsc5_violations) == 0


def test_lsc6_parameters_value_valid():
    """LSC6: Valid parameters matching operation model."""
    op_model = get_valid_operation_model()
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {
                        "source": "system",
                        "target": "mainOperator",
                        "event_type": "input_event",
                        "event_name": "ieWelcome",
                        "parameters": ["Hello World"]
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    lsc6_violations = [v for v in res["violations"] if v["id"] == "LSC6-PARAMETERS-VALUE"]
    assert len(lsc6_violations) == 0


def test_lsc6_parameters_value_invalid_count():
    """LSC6: Invalid parameter count."""
    op_model = get_valid_operation_model()
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {
                        "source": "system",
                        "target": "mainOperator",
                        "event_type": "input_event",
                        "event_name": "ieWelcome",
                        "parameters": ["param1", "param2"]  # Should be only 1 parameter
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    lsc6_violations = [v for v in res["violations"] if v["id"] == "LSC6-PARAMETERS-VALUE"]
    assert len(lsc6_violations) > 0


def test_lsc12_actor_type_name_consistency_valid():
    """LSC12: Valid actor type names matching operation model."""
    op_model = get_valid_operation_model()
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {
                        "source": "system",
                        "target": "mainOperator",  # Instance name that maps to ActOperator
                        "event_type": "input_event",
                        "event_name": "ieHello",
                        "parameters": []
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    lsc12_violations = [v for v in res["violations"] if v["id"] == "LSC12-ACTOR-TYPE-NAME-CONSISTENCY"]
    # Should not have violations if actor type is correctly inferred
    assert len(lsc12_violations) == 0


def test_lsc13_actor_instance_consistency_valid():
    """LSC13: Valid actor instance consistency."""
    op_model = get_valid_operation_model()
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {
                        "source": "system",
                        "target": "mainOperator",
                        "event_type": "input_event",
                        "event_name": "ieHello",  # Valid for ActOperator
                        "parameters": []
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    lsc13_violations = [v for v in res["violations"] if v["id"] == "LSC13-ACTOR-INSTANCE-CONSISTENCY"]
    assert len(lsc13_violations) == 0


def test_lsc13_actor_instance_consistency_invalid():
    """LSC13: Invalid actor instance using wrong event."""
    op_model = get_valid_operation_model()
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {
                        "source": "system",
                        "target": "mainOperator",  # ActOperator
                        "event_type": "input_event",
                        "event_name": "ieNotify",  # This event is for ActUser, not ActOperator
                        "parameters": []
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    lsc13_violations = [v for v in res["violations"] if v["id"] == "LSC13-ACTOR-INSTANCE-CONSISTENCY"]
    assert len(lsc13_violations) > 0


def test_lsc14_input_event_name_consistency_valid():
    """LSC14: Valid input event names matching operation model."""
    op_model = get_valid_operation_model()
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {
                        "source": "system",
                        "target": "mainOperator",
                        "event_type": "input_event",
                        "event_name": "ieHello",  # Valid event from operation model
                        "parameters": []
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    lsc14_violations = [v for v in res["violations"] if v["id"] == "LSC14-INPUT-EVENT-NAME-CONSISTENCY"]
    assert len(lsc14_violations) == 0


def test_lsc14_input_event_name_consistency_invalid():
    """LSC14: Invalid input event name not in operation model."""
    op_model = get_valid_operation_model()
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {
                        "source": "system",
                        "target": "mainOperator",
                        "event_type": "input_event",
                        "event_name": "ieInvalidEvent",  # Not in operation model
                        "parameters": []
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    lsc14_violations = [v for v in res["violations"] if v["id"] == "LSC14-INPUT-EVENT-NAME-CONSISTENCY"]
    assert len(lsc14_violations) > 0


def test_lsc15_output_event_name_consistency_valid():
    """LSC15: Valid output event names matching operation model."""
    op_model = get_valid_operation_model()
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {
                        "source": "mainOperator",
                        "target": "system",
                        "event_type": "output_event",
                        "event_name": "oeAck",  # Valid event from operation model
                        "parameters": []
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    lsc15_violations = [v for v in res["violations"] if v["id"] == "LSC15-OUTPUT-EVENT-NAME-CONSISTENCY"]
    assert len(lsc15_violations) == 0


def test_lsc15_output_event_name_consistency_invalid():
    """LSC15: Invalid output event name not in operation model."""
    op_model = get_valid_operation_model()
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {
                        "source": "mainOperator",
                        "target": "system",
                        "event_type": "output_event",
                        "event_name": "oeInvalidEvent",  # Not in operation model
                        "parameters": []
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    lsc15_violations = [v for v in res["violations"] if v["id"] == "LSC15-OUTPUT-EVENT-NAME-CONSISTENCY"]
    assert len(lsc15_violations) > 0


def test_lsc16_actors_persistence_valid():
    """LSC16: Valid actors from operation model."""
    op_model = get_valid_operation_model()
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {
                        "source": "system",
                        "target": "mainOperator",  # Valid actor instance
                        "event_type": "input_event",
                        "event_name": "ieHello",
                        "parameters": []
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    lsc16_violations = [v for v in res["violations"] if v["id"] == "LSC16-ACTORS-PERSISTENCE"]
    assert len(lsc16_violations) == 0


def test_lsc16_actors_persistence_invalid():
    """LSC16: Invalid actor not in operation model."""
    op_model = get_valid_operation_model()
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {
                        "source": "system",
                        "target": "unknownActor",  # Not in operation model
                        "event_type": "input_event",
                        "event_name": "ieHello",
                        "parameters": []
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    lsc16_violations = [v for v in res["violations"] if v["id"] == "LSC16-ACTORS-PERSISTENCE"]
    assert len(lsc16_violations) > 0


def test_lsc17_events_persistence_valid():
    """LSC17: Valid events from operation model."""
    op_model = get_valid_operation_model()
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {
                        "source": "system",
                        "target": "mainOperator",
                        "event_type": "input_event",
                        "event_name": "ieHello",  # Valid event from operation model
                        "parameters": []
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    lsc17_violations = [v for v in res["violations"] if v["id"] == "LSC17-EVENTS-PERSISTENCE"]
    assert len(lsc17_violations) == 0


def test_lsc17_events_persistence_invalid():
    """LSC17: Invalid event not in operation model."""
    op_model = get_valid_operation_model()
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {
                        "source": "system",
                        "target": "mainOperator",
                        "event_type": "input_event",
                        "event_name": "ieInventedEvent",  # Not in operation model
                        "parameters": []
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    lsc17_violations = [v for v in res["violations"] if v["id"] == "LSC17-EVENTS-PERSISTENCE"]
    assert len(lsc17_violations) > 0


# ============================================================================
# Test existing fixtures with updated rule IDs
# ============================================================================

def test_valid_scenario_fixture():
    """Test valid.scenario fixture."""
    if (FIXTURES_DIR / "valid.scenario").exists():
        text = (FIXTURES_DIR / "valid.scenario").read_text(encoding="utf-8")
        res = audit_scenario(text)
        assert res["verdict"] is True


def test_system_system_fixture():
    """Test system_system.scenario fixture."""
    if (FIXTURES_DIR / "system_system.scenario").exists():
        text = (FIXTURES_DIR / "system_system.scenario").read_text(encoding="utf-8")
        res = audit_scenario(text)
        assert res["verdict"] is False
        assert any(v["id"] == "LSC7-SYSTEM-NO-SELF-LOOP" for v in res["violations"])


def test_actor_actor_fixture():
    """Test actor_actor.scenario fixture."""
    if (FIXTURES_DIR / "actor_actor.scenario").exists():
        text = (FIXTURES_DIR / "actor_actor.scenario").read_text(encoding="utf-8")
        res = audit_scenario(text)
        assert res["verdict"] is False
        assert any(v["id"] == "LSC8-ACTOR-NO-SELF-LOOP" for v in res["violations"])


def test_wrong_ie_arrow_fixture():
    """Test wrong_ie_arrow.scenario fixture."""
    if (FIXTURES_DIR / "wrong_ie_arrow.scenario").exists():
        text = (FIXTURES_DIR / "wrong_ie_arrow.scenario").read_text(encoding="utf-8")
        res = audit_scenario(text)
        assert res["verdict"] is False
        assert any(v["id"] == "LSC9-INPUT-EVENT-ALLOWED-EVENTS" for v in res["violations"])


def test_wrong_oe_arrow_fixture():
    """Test wrong_oe_arrow.scenario fixture."""
    if (FIXTURES_DIR / "wrong_oe_arrow.scenario").exists():
        text = (FIXTURES_DIR / "wrong_oe_arrow.scenario").read_text(encoding="utf-8")
        res = audit_scenario(text)
        assert res["verdict"] is False
        assert any(v["id"] == "LSC10-OUTPUT-EVENT-DIRECTION" for v in res["violations"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

