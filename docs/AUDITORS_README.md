# Deterministic LUCIM Auditors (no-LLM)

This folder documents three deterministic Python auditors and how they integrate into the v3-ADK workflow.

Note: The canonical reference orchestrator for the standard multi-agent workflow is `archive/orchestrator_persona_v3.py`. See `docs/ORCHESTRATOR_REFERENCE.md`.

## Modules
- `utils_audit_operation_model.py`: Step 1 — Operation model auditor
- `utils_audit_scenario.py`: Step 2 — Scenario textual auditor
- `utils_audit_diagram.py`: Step 3 — PlantUML diagram auditor
- `utils_audit_compare.py`: Comparison helpers (agent auditor vs deterministic Python)

## API
Each auditor exposes a single function returning a verdict and violations list.

```python
from utils_audit_operation_model import audit_environment
from utils_audit_scenario import audit_scenario
from utils_audit_diagram import audit_diagram

res_env = audit_environment(env_dict)
res_scn = audit_scenario(plantuml_text)
res_dia = audit_diagram(plantuml_text)
# => { "verdict": bool, "violations": [ { "id": str, "message": str, "location|line": str|int } ] }
```

## Integration (v3-ADK)
- Hooks are added in `utils_orchestrator_v3_process.py` right after each agent auditor step.
- Results are stored under `processed_results["python_audits"]` and comparisons under `processed_results["auditor_vs_python"]`.
- The run summary logs an aggregate MATCH/MISMATCH report.

## Tests
Minimal unit tests live under `code-netlogo-to-lucim-agentic-workflow/tests/`:
- `test_utils_audit_operation_model.py`
- `test_utils_audit_scenario.py`
- `test_utils_audit_diagram.py`

Run tests with:
```bash
pytest -q
```

## Notes
- Inputs are validated with pragmatic, text-oriented checks; they do not require any network calls.
- Violations report stable rule IDs drawn from the persona rule docs (AS*/SS*/TCS*/GCS*/NAM* in scope).
