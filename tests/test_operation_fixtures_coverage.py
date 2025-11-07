import json
from pathlib import Path
import sys

# Add project root for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

from utils_audit_operation_model import audit_operation_model


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "operation"


def test_fixture_valid_is_compliant():
    p = FIXTURES_DIR / "valid.json"
    env = json.loads(p.read_text(encoding="utf-8"))
    res = audit_operation_model(env)
    assert res["verdict"] is True
    assert res["violations"] == []


def _load(path: str) -> dict:
    return json.loads((FIXTURES_DIR / path).read_text(encoding="utf-8"))


def test_lom1_bad_type_triggers_type_format():
    env = _load("lom1_bad_type.json")
    res = audit_operation_model(env)
    assert res["verdict"] is False
    assert any(v["id"] == "LEM1-ACT-TYPE-FORMAT" for v in res["violations"])  # mapping: LOM1 → LEM1


def test_lom2_bad_instance_triggers_instance_format():
    env = _load("lom2_bad_instance.json")
    res = audit_operation_model(env)
    assert res["verdict"] is False
    assert any(v["id"] == "LEM2-ACT-INSTANCE-FORMAT" for v in res["violations"])  # mapping: LOM2 → LEM2


def test_lom4_ie_wrong_direction():
    env = _load("lom4_ie_wrong.json")
    res = audit_operation_model(env)
    assert res["verdict"] is False
    assert any(v["id"] == "LEM4-IE-EVENT-DIRECTION" for v in res["violations"])  # mapping: LOM4 → LEM4


def test_lom5_oe_wrong_direction():
    env = _load("lom5_oe_wrong.json")
    res = audit_operation_model(env)
    assert res["verdict"] is False
    assert any(v["id"] == "LEM5-OE-EVENT-DIRECTION" for v in res["violations"])  # mapping: LOM5 → LEM5


def test_lom7_postF_missing():
    env = _load("lom7_postF_missing.json")
    res = audit_operation_model(env)
    assert res["verdict"] is False
    assert any(v["id"] == "LOM7-CONDITIONS-VALIDATION" for v in res["violations"])  # direct match


