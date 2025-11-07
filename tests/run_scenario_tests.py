#!/usr/bin/env python3
"""
Simple test runner for scenario audit tests without pytest dependency.
"""
import sys
import json
import pathlib
from pathlib import Path

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from utils_audit_scenario import audit_scenario

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "scenario"
OPERATION_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "operation"


def get_valid_operation_model(use_file=True):
    """Load a valid operation model for testing."""
    if use_file:
        op_model_path = OPERATION_FIXTURES_DIR / "valid.json"
        if op_model_path.exists():
            return json.loads(op_model_path.read_text(encoding="utf-8"))
    # Return a minimal valid operation model with ie/oe prefixed events
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


def run_test(name, test_func):
    """Run a single test and report results."""
    try:
        test_func()
        print(f"✅ {name}")
        return True
    except AssertionError as e:
        print(f"❌ {name}: {e}")
        return False
    except Exception as e:
        print(f"⚠️  {name}: Error - {e}")
        return False


def test_valid_scenario():
    """Test valid scenario."""
    text = """
system --> bill : ieHello()
bill -> system : oeAck()
"""
    res = audit_scenario(text)
    assert res["verdict"] is True, f"Expected valid, got violations: {res['violations']}"


def test_system_system_forbidden():
    """Test LSC7: System→System forbidden."""
    text = """
system -> system : oeLoop()
"""
    res = audit_scenario(text)
    assert res["verdict"] is False
    assert any(v["id"] == "LSC7-SYSTEM-NO-SELF-LOOP" for v in res["violations"])


def test_actor_actor_forbidden():
    """Test LSC8: Actor→Actor forbidden."""
    text = """
bill -> alice : oeChat()
"""
    res = audit_scenario(text)
    assert res["verdict"] is False
    assert any(v["id"] == "LSC8-ACTOR-NO-SELF-LOOP" for v in res["violations"])


def test_wrong_ie_arrow():
    """Test LSC9: Input events must be System → Actor."""
    text = """
system -> bill : ieHello()
"""
    res = audit_scenario(text)
    assert res["verdict"] is False
    assert any(v["id"] == "LSC9-INPUT-EVENT-ALLOWED-EVENTS" for v in res["violations"])


def test_wrong_oe_arrow():
    """Test LSC10: Output events must be Actor → System."""
    text = """
bill --> system : oeAck()
"""
    res = audit_scenario(text)
    assert res["verdict"] is False
    assert any(v["id"] == "LSC10-OUTPUT-EVENT-DIRECTION" for v in res["violations"])


def test_lsc2_too_many_actors():
    """Test LSC2: At most 5 actors."""
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
    assert res["verdict"] is False
    assert any(v["id"] == "LSC2-ACTORS-LIMITATION" for v in res["violations"])


def test_lsc3_missing_input_events():
    """Test LSC3: At least one input event per actor."""
    text = """
bill -> system : oeAck()
"""
    res = audit_scenario(text)
    assert res["verdict"] is False
    assert any(v["id"] == "LSC3-INPUT-EVENTS-LIMITATION" for v in res["violations"])


def test_lsc4_missing_output_events():
    """Test LSC4: At least one output event per actor."""
    text = """
system --> bill : ieHello()
"""
    res = audit_scenario(text)
    assert res["verdict"] is False
    assert any(v["id"] == "LSC4-OUTPUT-EVENTS-LIMITATION" for v in res["violations"])


def test_lsc11_camelcase_valid():
    """Test LSC11: Valid camelCase actor names."""
    text = """
system --> actAdministrator : ieHello()
actAdministrator -> system : oeAck()
"""
    res = audit_scenario(text)
    lsc11_violations = [v for v in res["violations"] if v["id"] == "LSC11-ACTOR-INSTANCE-FORMAT"]
    assert len(lsc11_violations) == 0


def test_lsc11_camelcase_invalid():
    """Test LSC11: Invalid actor names (not camelCase)."""
    text = """
system --> ACT_ADMIN : ieHello()
ACT_ADMIN -> system : oeAck()
"""
    res = audit_scenario(text)
    lsc11_violations = [v for v in res["violations"] if v["id"] == "LSC11-ACTOR-INSTANCE-FORMAT"]
    assert len(lsc11_violations) > 0


def test_lsc14_invalid_input_event():
    """Test LSC14: Input event name consistency."""
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
                        "event_name": "ieInvalidEvent",
                        "parameters": []
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    assert res["verdict"] is False
    assert any(v["id"] == "LSC14-INPUT-EVENT-NAME-CONSISTENCY" for v in res["violations"])


def test_lsc15_invalid_output_event():
    """Test LSC15: Output event name consistency."""
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
                        "event_name": "oeInvalidEvent",
                        "parameters": []
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    assert res["verdict"] is False
    assert any(v["id"] == "LSC15-OUTPUT-EVENT-NAME-CONSISTENCY" for v in res["violations"])


def test_lsc16_invalid_actor():
    """Test LSC16: Actor persistence."""
    op_model = get_valid_operation_model()
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {
                        "source": "system",
                        "target": "unknownActor",
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
    assert res["verdict"] is False
    assert any(v["id"] == "LSC16-ACTORS-PERSISTENCE" for v in res["violations"])


def test_lsc17_invalid_event():
    """Test LSC17: Event persistence."""
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
                        "event_name": "ieInventedEvent",
                        "parameters": []
                    }
                ]
            }
        },
        "errors": []
    }
    res = audit_scenario(json.dumps(scenario_json), operation_model=op_model)
    assert res["verdict"] is False
    assert any(v["id"] == "LSC17-EVENTS-PERSISTENCE" for v in res["violations"])


def test_lsc6_invalid_parameters():
    """Test LSC6: Parameter validation."""
    # Use default model (not file) to ensure consistent event names
    op_model = get_valid_operation_model(use_file=False)
    # Use "actOperator" which should be inferred as "ActOperator" type
    scenario_json = {
        "data": {
            "scenario": {
                "name": "test",
                "messages": [
                    {
                        "source": "system",
                        "target": "actOperator",
                        "event_type": "input_event",
                        "event_name": "ieWelcome",
                        "parameters": ["param1", "param2"]  # Should be only 1
                    },
                    {
                        "source": "actOperator",
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
    # Should have LSC6 violation (and possibly others, but LSC6 must be present)
    lsc6_violations = [v for v in res["violations"] if v["id"] == "LSC6-PARAMETERS-VALUE"]
    assert len(lsc6_violations) > 0, f"Expected LSC6 violation, got violations: {[v['id'] for v in res['violations']]}"


def test_fixtures():
    """Test all fixture files."""
    fixtures = [
        ("valid.scenario", True),
        ("system_system.scenario", False),
        ("actor_actor.scenario", False),
        ("wrong_ie_arrow.scenario", False),
        ("wrong_oe_arrow.scenario", False),
    ]
    
    for fixture_name, should_be_valid in fixtures:
        fixture_path = FIXTURES_DIR / fixture_name
        if fixture_path.exists():
            text = fixture_path.read_text(encoding="utf-8")
            res = audit_scenario(text)
            assert res["verdict"] == should_be_valid, f"Fixture {fixture_name}: expected valid={should_be_valid}, got {res['verdict']}"


def main():
    """Run all tests."""
    tests = [
        ("Valid scenario", test_valid_scenario),
        ("LSC7: System→System forbidden", test_system_system_forbidden),
        ("LSC8: Actor→Actor forbidden", test_actor_actor_forbidden),
        ("LSC9: Wrong IE arrow", test_wrong_ie_arrow),
        ("LSC10: Wrong OE arrow", test_wrong_oe_arrow),
        ("LSC2: Too many actors", test_lsc2_too_many_actors),
        ("LSC3: Missing input events", test_lsc3_missing_input_events),
        ("LSC4: Missing output events", test_lsc4_missing_output_events),
        ("LSC11: Valid camelCase", test_lsc11_camelcase_valid),
        ("LSC11: Invalid camelCase", test_lsc11_camelcase_invalid),
        ("LSC14: Invalid input event", test_lsc14_invalid_input_event),
        ("LSC15: Invalid output event", test_lsc15_invalid_output_event),
        ("LSC16: Invalid actor", test_lsc16_invalid_actor),
        ("LSC17: Invalid event", test_lsc17_invalid_event),
        ("LSC6: Invalid parameters", test_lsc6_invalid_parameters),
        ("All fixtures", test_fixtures),
    ]
    
    print("Running scenario audit tests...\n")
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        if run_test(name, test_func):
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

