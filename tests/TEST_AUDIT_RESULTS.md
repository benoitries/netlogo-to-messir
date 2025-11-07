# Test Results - Python Auditors

## Summary

✅ **All tests passed!** Both Scenario and Diagram auditors correctly detect all expected violations.

## Test Files

1. **test_scenario_non_compliant.scenario** - Intentionally violates all scenario rules
2. **test_diagram_non_compliant.puml** - Intentionally violates all diagram rules

## Scenario Auditor Results

**Status**: ✅ PASS  
**Violations Detected**: 14 (7 unique rule types)

### Rules Tested and Detected:

1. ✅ **SS1-MESSAGE-DIRECTIONALITY** - Messages must connect exactly one Actor and System
2. ✅ **AS4-SYS-NO-SELF-LOOP** - System→System message forbidden
3. ✅ **AS6-ACT-NO-ACT-ACT-EVENTS** - Actor→Actor message forbidden
4. ✅ **TCS4-IE-SYNTAX** - ie events must use dashed arrow (-->) from system to actor
5. ✅ **TCS5-OE-SYNTAX** - oe events must use solid arrow (->) from actor to system
6. ✅ **AS8-IE-EVENT-DIRECTION** - ie* events must be System → Actor
7. ✅ **AS9-OE-EVENT-DIRECTION** - oe* events must be Actor → System

## Diagram Auditor Results

**Status**: ✅ PASS  
**Violations Detected**: 11 (9 unique rule types + 1 redundant)

### Rules Tested and Detected:

1. ✅ **AS2-SYS-DECLARED-FIRST** - System must be declared before all actors
2. ✅ **SS3-SYS-UNIQUE-IDENTITY** - System participant must be unique
3. ✅ **AS5-ACT-DECLARED-AFTER-SYS** - Actors must be declared after System
4. ✅ **AS4-SYS-NO-SELF-LOOP** - System→System message forbidden
5. ✅ **AS6-ACT-NO-ACT-ACT-EVENTS** - Actor→Actor message forbidden
6. ✅ **TCS10-AB-NO-ACTIVATION-BAR-ON-SYSTEM** - System must never be activated
7. ✅ **TCS9-AB-SEQUENCE** - Activation/deactivation must follow a message
8. ✅ **AS8-IE-EVENT-DIRECTION** - ie* events should be System → Actor
9. ✅ **AS9-OE-EVENT-DIRECTION** - oe* events should be Actor → System
10. ✅ **SS1-MESSAGE-DIRECTIONALITY** - Messages must connect exactly one Actor and System (redundant with AS4/AS6 but correctly detected)

## Notes

- **SS1-MESSAGE-DIRECTIONALITY** is detected redundantly with AS4 and AS6, which is correct behavior as it provides additional validation.
- All violations include complete line content and line numbers for easy debugging.
- The auditors correctly identify the exact location and content of each violation.

## Running the Tests

```bash
cd code-netlogo-to-lucim-agentic-workflow
python3 tests/test_audit_all_rules.py
```

