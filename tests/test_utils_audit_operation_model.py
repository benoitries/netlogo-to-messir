import pytest
import sys
import pathlib

# Add project module root to path to allow importing modules in this folder
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from utils_audit_operation_model import audit_environment


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
    res = audit_environment(env)
    assert res["verdict"] is True
    assert res["violations"] == []


def test_environment_invalid_directions_and_formats():
    env = {
        "system": {"name": "Sys"},  # wrong system name
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
    res = audit_environment(env)
    assert res["verdict"] is False
    assert any(v["id"] == "AS1-SYS-UNIQUE" for v in res["violations"]) or any(v["id"] == "SS3-SYS-UNIQUE-IDENTITY" for v in res["violations"]) 
    assert any(v["id"] == "LEM2-ACT-INSTANCE-FORMAT" for v in res["violations"]) 
    assert any(v["id"] == "LEM1-ACT-TYPE-FORMAT" for v in res["violations"]) 
    assert any(v["id"] == "AS4-SYS-NO-SELF-LOOP" for v in res["violations"]) 
    assert any(v["id"] == "AS6-ACT-NO-ACT-ACT-EVENTS" for v in res["violations"]) 



