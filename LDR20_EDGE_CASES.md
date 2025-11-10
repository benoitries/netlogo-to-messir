# LDR20 Activation Bar Sequence - Edge Cases and Limitations

## Overview

LDR20 requires a strict sequence: (1) event declaration, (2) activate the participant, (3) deactivate the participant.

The current implementation in `utils_audit_diagram.py` uses a greedy matching algorithm that pairs each event with the first available activation that follows it. While this works well for well-formed diagrams, there are several edge cases that may not be fully covered.

## Identified Edge Cases

### 1. Multiple Events for Same Participant

**Problem**: When multiple events exist for the same participant without activations between them, the activation should be associated with the last event (most recent), not the first. The issue is that earlier events are missing their activation bars.

**Example**:
```plantuml
actor -> system : oeEvent1()
actor -> system : oeEvent2()
activate actor
deactivate actor
```

In this case, the activation at line 3 should be associated with `oeEvent2` (the last/most recent event). The real issue is that `oeEvent1` is missing its activation bars, making LDR20 non-compliant.

**Current Behavior**: The logic correctly associates the activation with `oeEvent2` (last event) and flags that `oeEvent1` is missing its activation sequence.

**Status**: ✅ Correctly handled - activations are paired with the last event, and earlier events without activations are flagged as violations.

### 2. Missing Activation Detection with Multiple Events

**Problem**: If an event has no activation immediately following it, but a later activation exists, the logic flags LDR20 violation but may not correctly identify which event is missing its activation when multiple events exist.

**Example**:
```plantuml
actor -> system : oeEvent1()
actor -> system : oeEvent2()
activate actor  # This activation belongs to oeEvent2, but oeEvent1 has no activation
deactivate actor
```

**Current Behavior**: The logic will flag that `oeEvent1` has no activation, but may also incorrectly flag that the activation doesn't immediately follow `oeEvent1`.

**Limitation**: The logic may report multiple violations for a single underlying issue.

### 3. Activation Reuse

**Problem**: The logic doesn't track which activations have been "used" for previous events, so if two events share the same activation line (invalid case), only one violation may be reported.

**Example**:
```plantuml
actor -> system : oeEvent1()
actor -> system : oeEvent2()
activate actor  # This activation should be associated with only one event
deactivate actor
```

**Current Behavior**: With the improved logic (using `used_activations` set), each activation can only be used once. However, if the diagram is malformed, the logic may not correctly identify which event is missing its activation.

**Improvement**: The current implementation now tracks used activations to avoid double-counting.

### 4. Deactivation Pairing

**Problem**: Similar to activation pairing, deactivations are paired with the first activation that precedes them, which may not be correct if multiple activations exist.

**Example**:
```plantuml
actor -> system : oeEvent1()
activate actor
actor -> system : oeEvent2()
activate actor
deactivate actor  # Which activation does this deactivate?
deactivate actor
```

**Current Behavior**: The logic pairs the first deactivation with the first activation, and the second deactivation with the second activation. This works correctly in this case.

**Limitation**: If deactivations are out of order or missing, the pairing may be incorrect.

### 5. Interleaved Events from Different Participants

**Problem**: If events from different participants are interleaved, the line-based matching should work correctly, but the logic doesn't verify that activations belong to the correct participant's events.

**Example**:
```plantuml
actor1 -> system : oeEvent1()
activate actor1
actor2 -> system : oeEvent2()
activate actor2
deactivate actor1
deactivate actor2
```

**Current Behavior**: The logic correctly handles this case because it tracks activations per participant.

**Status**: ✅ This case is handled correctly.

### 6. Gaps Between Event and Activation

**Status**: ✅ NOT A VIOLATION - This is correctly handled.

**Clarification**: According to LDR19, blank lines and comments are allowed and must be ignored in PlantUML diagrams. Therefore, having blank lines or comments between an event and its activation is perfectly valid.

**Example**:
```plantuml
actor -> system : oeEvent1()
// comment
activate actor
deactivate actor
```

**Current Behavior**: The logic correctly ignores blank lines and comments when checking the sequence. The activation is considered to immediately follow the event, even if there are blank lines or comments in between.

**Status**: ✅ Correctly handled - blank lines and comments are ignored per LDR19. The `_find_next_non_empty_line()` helper function ensures that blank lines and comments are properly skipped when validating the sequence.

### 7. Missing Deactivation

**Problem**: If an activation exists but has no corresponding deactivation, the logic flags this, but may not correctly identify which activation is missing its deactivation when multiple activations exist.

**Example**:
```plantuml
actor -> system : oeEvent1()
activate actor
deactivate actor
actor -> system : oeEvent2()
activate actor
// Missing deactivate for second activation
```

**Current Behavior**: The logic flags that the second activation is missing its deactivation.

**Status**: ✅ This case is handled correctly with the improved logic.

## Improvements Made

1. **Activation Tracking**: Added `used_activations` and `used_deactivations` sets to track which activations/deactivations have been paired with events, preventing double-counting.

2. **Gap Information**: Added gap information to violation details to help identify the exact spacing issue.

3. **Sorted Event Processing**: Events are now processed in sorted order to ensure consistent pairing.

4. **Missing Deactivation Detection**: Improved detection of missing deactivations with clear violation messages.

## Remaining Limitations

1. **Ambiguous Pairing**: When multiple events exist for the same participant and activations are not immediately following, the logic may not correctly identify which event-activation pair is problematic.

2. **Complex Malformed Diagrams**: For severely malformed diagrams with multiple issues, the logic may report multiple violations that are actually symptoms of a single underlying problem.

3. **No Semantic Validation**: The logic doesn't verify that activations semantically belong to their associated events (e.g., checking that the activation is on the correct participant's lifeline).

## Recommendations

1. **Enhanced Pairing Algorithm**: Consider implementing a more sophisticated pairing algorithm that tries to find the best match for each event-activation pair, potentially using a constraint satisfaction approach.

2. **Violation Grouping**: Group related violations to help users understand that multiple violations may stem from a single issue.

3. **Semantic Validation**: Add validation to ensure activations are on the correct participant's lifeline (though this is partially covered by LDR7).

4. **Test Coverage**: Add comprehensive test cases for each identified edge case to ensure the logic handles them correctly.

## Test Cases Needed

1. Multiple events for same participant with correct activations
2. Multiple events for same participant with missing activations
3. Interleaved events from different participants
4. Gaps between events and activations
5. Missing deactivations
6. Out-of-order deactivations
7. Duplicate activations for same event
8. Activation on wrong participant (covered by LDR7/LDR10)

