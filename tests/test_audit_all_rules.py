#!/usr/bin/env python3
"""
Test script to verify that all Python auditors detect all violations correctly.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils_audit_scenario import audit_scenario
from utils_audit_diagram import audit_diagram

# Expected violations for scenario
EXPECTED_SCENARIO_VIOLATIONS = {
    "SS1-MESSAGE-DIRECTIONALITY",  # invalidMessage line
    "AS4-SYS-NO-SELF-LOOP",  # system -> system
    "AS6-ACT-NO-ACT-ACT-EVENTS",  # bill -> alice
    "TCS4-IE-SYNTAX",  # system -> bill : ieHello() (wrong arrow)
    "TCS4-IE-SYNTAX",  # bill --> system : ieWrongDirection() (wrong direction)
    "TCS5-OE-SYNTAX",  # alice --> system : oeLogin() (wrong arrow)
    "TCS5-OE-SYNTAX",  # system -> alice : oeWrongDirection() (wrong direction)
    "AS8-IE-EVENT-DIRECTION",  # bill -> system : ieInvalid()
    "AS9-OE-EVENT-DIRECTION",  # system --> bill : oeInvalid()
}

# Expected violations for diagram
# Note: SS1-MESSAGE-DIRECTIONALITY is also detected (redundant with AS4/AS6 but correct)
EXPECTED_DIAGRAM_VIOLATIONS = {
    "AS2-SYS-DECLARED-FIRST",  # Actor before System
    "SS3-SYS-UNIQUE-IDENTITY",  # Duplicate System
    "AS5-ACT-DECLARED-AFTER-SYS",  # Actor before System (alice)
    "AS4-SYS-NO-SELF-LOOP",  # system -> system
    "AS6-ACT-NO-ACT-ACT-EVENTS",  # bill -> alice
    "TCS10-AB-NO-ACTIVATION-BAR-ON-SYSTEM",  # activate system
    "TCS9-AB-SEQUENCE",  # activate charlie before message
    "AS8-IE-EVENT-DIRECTION",  # bill -> system : ieInvalid()
    "AS9-OE-EVENT-DIRECTION",  # system --> alice : oeInvalid()
}


def test_scenario_auditor():
    """Test scenario auditor with non-compliant file."""
    print("=" * 80)
    print("TESTING SCENARIO AUDITOR")
    print("=" * 80)
    
    scenario_file = Path(__file__).parent / "test_scenario_non_compliant.scenario"
    if not scenario_file.exists():
        print(f"❌ ERROR: Test file not found: {scenario_file}")
        return False
    
    scenario_text = scenario_file.read_text(encoding="utf-8")
    result = audit_scenario(scenario_text)
    
    print(f"\nVerdict: {'✅ COMPLIANT' if result['verdict'] else '❌ NON-COMPLIANT'}")
    print(f"Violations found: {len(result['violations'])}")
    
    detected_violations = set()
    for v in result['violations']:
        rule_id = v.get('id', 'UNKNOWN')
        detected_violations.add(rule_id)
        line = v.get('line', '?')
        message = v.get('message', '')
        print(f"  - Line {line}: {rule_id} - {message}")
    
    print(f"\nExpected violations: {len(EXPECTED_SCENARIO_VIOLATIONS)}")
    print(f"Detected violations: {len(detected_violations)}")
    
    # Check coverage
    missing = EXPECTED_SCENARIO_VIOLATIONS - detected_violations
    extra = detected_violations - EXPECTED_SCENARIO_VIOLATIONS
    
    success = True
    if missing:
        print(f"\n❌ MISSING VIOLATIONS ({len(missing)}):")
        for rule in sorted(missing):
            print(f"   - {rule}")
        success = False
    
    if extra:
        print(f"\n⚠️  EXTRA VIOLATIONS DETECTED ({len(extra)}):")
        for rule in sorted(extra):
            print(f"   - {rule}")
        # Extra violations are OK, they might be legitimate
    
    if success and not missing:
        print("\n✅ All expected violations detected!")
    
    return success and not missing


def test_diagram_auditor():
    """Test diagram auditor with non-compliant file."""
    print("\n" + "=" * 80)
    print("TESTING DIAGRAM AUDITOR")
    print("=" * 80)
    
    diagram_file = Path(__file__).parent / "test_diagram_non_compliant.puml"
    if not diagram_file.exists():
        print(f"❌ ERROR: Test file not found: {diagram_file}")
        return False
    
    diagram_text = diagram_file.read_text(encoding="utf-8")
    result = audit_diagram(diagram_text)
    
    print(f"\nVerdict: {'✅ COMPLIANT' if result['verdict'] else '❌ NON-COMPLIANT'}")
    print(f"Violations found: {len(result['violations'])}")
    
    detected_violations = set()
    for v in result['violations']:
        rule_id = v.get('id', 'UNKNOWN')
        detected_violations.add(rule_id)
        line = v.get('line', '?')
        message = v.get('message', '')
        line_content = v.get('extracted_values', {}).get('line_content', '')
        print(f"  - Line {line}: {rule_id} - {message}")
        if line_content:
            print(f"    Content: {line_content[:60]}...")
    
    print(f"\nExpected violations: {len(EXPECTED_DIAGRAM_VIOLATIONS)}")
    print(f"Detected violations: {len(detected_violations)}")
    
    # Check coverage
    missing = EXPECTED_DIAGRAM_VIOLATIONS - detected_violations
    extra = detected_violations - EXPECTED_DIAGRAM_VIOLATIONS
    
    success = True
    if missing:
        print(f"\n❌ MISSING VIOLATIONS ({len(missing)}):")
        for rule in sorted(missing):
            print(f"   - {rule}")
        success = False
    
    if extra:
        print(f"\n⚠️  EXTRA VIOLATIONS DETECTED ({len(extra)}):")
        for rule in sorted(extra):
            print(f"   - {rule}")
        # Extra violations are OK, they might be legitimate
    
    if success and not missing:
        print("\n✅ All expected violations detected!")
    
    return success and not missing


def main():
    """Run all tests."""
    print("Python Auditor Test Suite")
    print("Testing all rules with intentionally non-compliant files\n")
    
    scenario_ok = test_scenario_auditor()
    diagram_ok = test_diagram_auditor()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Scenario Auditor: {'✅ PASS' if scenario_ok else '❌ FAIL'}")
    print(f"Diagram Auditor: {'✅ PASS' if diagram_ok else '❌ FAIL'}")
    
    if scenario_ok and diagram_ok:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())

