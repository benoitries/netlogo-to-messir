import pytest
import sys
import pathlib

# Add project module root to path to allow importing modules in this folder
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from utils_audit_operation_model import audit_operation_model


def test_environment_valid_minimal():
    env = {
        "system": {"name": "System"},
        "actors": [
            {"name": "bill", "type": "ActAdministrator"}
        ],
        "events": [
            {"kind": "oe", "sender": "bill", "receiver": "system"},
            {"kind": "ie", "sender": "system", "receiver": "bill"}
        ]
    }
    res = audit_operation_model(env)
    assert res["verdict"] is True
    assert res["violations"] == []


def test_environment_invalid_directions_and_formats():
    env = {
        "system": {"name": "System"},
        "actors": [
            {"name": "Bill", "type": "Administrator"}  # wrong formats
        ],
        "events": [
            {"kind": "oe", "sender": "system", "receiver": "bill"},  # wrong for oe
            {"kind": "ie", "sender": "bill", "receiver": "system"},  # wrong for ie
            {"kind": "ie", "sender": "system", "receiver": "system"},  # sys->sys
            {"kind": "oe", "sender": "bill", "receiver": "bill"},  # act->act
        ]
    }
    res = audit_operation_model(env)
    assert res["verdict"] is False
    # Note: LEM2-ACT-INSTANCE-FORMAT is no longer a LOM rule, but we check instance format if provided
    # The test case has "Bill" which is not camelCase, but this is not enforced as a LOM rule anymore
    assert any(v["id"] == "LOM1-ACT-TYPE-FORMAT" for v in res["violations"]) 
    assert any(v["id"] == "LOM4-IE-EVENT-DIRECTION" for v in res["violations"]) 
    assert any(v["id"] == "LOM5-OE-EVENT-DIRECTION" for v in res["violations"]) 


def test_new_format_dict_actors_params_invalid():
    # Actors provided as dict keyed by type; parameters invalid (not list of strings)
    env = {
        "system": {"name": "System"},
        "actors": {
            "ActAdministrator": {
                "description": "admin actor",
                "input_events": {
                    "login": {"source": "System", "target": "ActAdministrator", "parameters": ["user", 123]}
                },
                "output_events": {
                    "report": {"source": "ActAdministrator", "target": "System", "parameters": "not-a-list"}
                }
            }
        }
    }
    res = audit_operation_model(env)
    assert res["verdict"] is False
    assert any(v["id"] == "FORMAT-PARAMS-ARRAY-OF-STR" for v in res["violations"]) 


def test_new_format_explicit_direction_mismatch():
    # Explicit wrong directions inside input_events/output_events blocks
    env = {
        "system": {"name": "System"},
        "actors": {
            "ActOperator": {
                "input_events": {
                    "hello": {"source": "actor", "target": "System"}
                },
                "output_events": {
                    "notify": {"source": "ActOperator", "target": "user"}
                }
            }
        }
    }
    res = audit_operation_model(env)
    assert res["verdict"] is False
    # LOM4 for input_events wrong direction, LOM5 for output_events wrong direction
    assert any(v["id"] == "LOM4-IE-EVENT-DIRECTION" for v in res["violations"]) 
    assert any(v["id"] == "LOM5-OE-EVENT-DIRECTION" for v in res["violations"]) 


def test_new_format_valid_compliant():
    # Valid case with actors as dict keyed by type and proper fields
    env = {
        "system": {"name": "System"},
        "actors": {
            "ActOperator": {
                "name": "mainOperator",
                "description": "primary operator",
                "input_events": {
                    "hello": {"source": "System", "target": "ActOperator", "parameters": [], "postF": []}
                },
                "output_events": {
                    "reportReady": {"source": "ActOperator", "target": "System", "parameters": ["summary"], "postF": []}
                }
            }
        }
    }
    res = audit_operation_model(env)
    assert res["verdict"] is True
    assert res["violations"] == []


def test_conditions_missing_postF_should_violate():
    # postF is required and must be non-empty array (LOM7)
    env = {
        "system": {"name": "System"},
        "actors": {
            "ActOperator": {
                "name": "mainOperator",
                "input_events": {
                    "hello": {"source": "System", "target": "ActOperator", "parameters": []}
                },
                "output_events": {
                    # Missing postF entirely
                    "reportReady": {"source": "ActOperator", "target": "System"}
                }
            }
        }
    }
    res = audit_environment(env)
    assert res["verdict"] is False
    assert any(v["id"] == "LOM7-CONDITIONS-VALIDATION" for v in res["violations"]) 


def test_conditions_pref_prep_types_and_postF_non_empty():
    # preF/preP optional but if present must be arrays; postF required non-empty
    env_bad_types = {
        "system": {"name": "System"},
        "actors": {
            "ActOperator": {
                "name": "mainOperator",
                "input_events": {
                    "hello": {"source": "System", "target": "ActOperator", "preF": "not-a-list", "postF": []}
                },
                "output_events": {
                    "notify": {"source": "ActOperator", "target": "System", "preP": {"x": 1}, "postF": "wrong"}
                }
            }
        }
    }
    res1 = audit_environment(env_bad_types)
    assert res1["verdict"] is False
    ids = {v["id"] for v in res1["violations"]}
    assert "LOM7-CONDITIONS-VALIDATION" in ids

    # Correct types: preF/preP lists (may be empty), postF non-empty
    env_ok = {
        "system": {"name": "System"},
        "actors": {
            "ActOperator": {
                "name": "mainOperator",
                "input_events": {
                    "hello": {"source": "System", "target": "ActOperator", "preF": [], "preP": ["auth"], "postF": ["done"]}
                },
                "output_events": {
                    "notify": {"source": "ActOperator", "target": "System", "preP": [], "postF": ["queued"]}
                }
            }
        }
    }
    res2 = audit_environment(env_ok)
    assert res2["verdict"] is True
    assert res2["violations"] == []



def test_conditions_valid_present():
    env = {
        "system": {"name": "System"},
        "actors": {
            "ActOperator": {
                "name": "mainOperator",
                "input_events": {
                    "hello": {
                        "source": "System",
                        "target": "ActOperator",
                        "parameters": [],
                        "preF": [{"id": "C1", "text": "Operator exists", "severity": "must"}],
                        "preP": [{"text": "Authenticated", "severity": "should", "refs": ["SEC-1"]}],
                        "postF": [{"text": "State updated"}]
                    }
                }
            }
        }
    }
    res = audit_operation_model(env)
    assert res["verdict"] is True


def test_missing_postf_triggers_violation():
    env = {
        "system": {"name": "System"},
        "actors": {
            "ActOperator": {
                "name": "mainOperator",
                "input_events": {
                    "hello": {"source": "System", "target": "ActOperator", "parameters": []}
                }
            }
        }
    }
    res = audit_operation_model(env)
    assert res["verdict"] is False
    assert any(v["id"] == "FORMAT-POSTF-REQUIRED" for v in res["violations"]) 


def test_conditions_invalid_shapes_and_severity_and_duplicate_ids():
    env = {
        "system": {"name": "System"},
        "actors": {
            "ActOperator": {
                "name": "mainOperator",
                "output_events": {
                    "notify": {
                        "source": "ActOperator",
                        "target": "System",
                        "parameters": [],
                        "preF": "not-an-array",
                        "preP": [{"text": "", "severity": "must"}],
                        "postF": [
                            {"id": "DUP", "text": "ok", "severity": "invalid"},
                            {"id": "DUP", "text": "another"}
                        ]
                    }
                }
            }
        }
    }
    res = audit_operation_model(env)
    assert res["verdict"] is False
    ids = [v["id"] for v in res["violations"]]
    assert "FORMAT-CONDITIONS-ARRAY" in ids
    assert "FORMAT-CONDITION-TEXT" in ids
    assert "FORMAT-CONDITION-SEVERITY" in ids
    assert "FORMAT-CONDITION-ID-UNIQUE" in ids


