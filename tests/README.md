# Auditor Tests and Coverage Guide

This folder contains fixtures and tests to validate the three deterministic auditors:

- Operation model: `utils_audit_operation_model.py`
- Scenario: `utils_audit_scenario.py`
- Diagram: `utils_audit_diagram.py`

## How to run

Run all tests:

```
pytest -q code-netlogo-to-lucim-agentic-workflow/tests
```

Run a specific area:

```
pytest -q code-netlogo-to-lucim-agentic-workflow/tests/test_operation_fixtures_coverage.py
pytest -q code-netlogo-to-lucim-agentic-workflow/tests/test_scenario_fixtures_coverage.py
pytest -q code-netlogo-to-lucim-agentic-workflow/tests/test_diagram_fixtures_coverage.py
```

## Structure

- `fixtures/operation/`: valid and rule-targeting JSON examples for operation model
- `fixtures/scenario/`: valid and rule-targeting textual scenarios
- `fixtures/diagram/`: valid and rule-targeting PlantUML diagrams

## Expected outcomes

- Valid fixtures must be COMPLIANT (no violations)
- Each noncompliant fixture must trigger a specific rule ID asserted in the corresponding test

## Keeping rules in sync

`tests/utils_rules_parser.py` provides a small helper to parse RULE IDs from `RULES_LUCIM_*.md` files. If rules change (added/removed/renamed), add or adjust fixtures/tests so that:

- Each RULE ID has at least one failing example asserting the exact `id`
- Valid baseline(s) still pass with zero violations


