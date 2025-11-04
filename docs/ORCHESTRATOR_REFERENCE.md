# Reference Orchestrator (Canonical)

This document declares the canonical reference implementation of the multi-agent workflow for the NetLogo to LUCIM pipeline.

## Canonical Source

- File: `code-netlogo-to-lucim-agentic-workflow/archive/orchestrator_persona_v3.py`
- Purpose: Persona v3 limited-agents, 6-stage pipeline starting with LUCIM Operation Synthesizer
- Status: Reference implementation for the multi-agent workflow

## Rationale

The repository contains legacy and ADK-based orchestrators. To avoid ambiguity, `orchestrator_persona_v3.py` is the single source of truth for:
- Stage ordering and conditional execution (v3 6-stage flow)
- Inputs/outputs per stage and artifact naming
- Logging and compliance summary structure

Other orchestrators may exist for experimentation or historical reasons, but this file is the authoritative reference for the standard multi-agent workflow.

## How to Run

The reference orchestrator can be executed directly (interactive flow):

```bash
python /Users/benoit.ries/Library/CloudStorage/OneDrive-UniversityofLuxembourg/cursor-workspace-individual/research.publi.reverse.engineering.netlogo.to.messir.ucid/code-netlogo-to-lucim-agentic-workflow/archive/orchestrator_persona_v3.py
```

Notes:
- Requires valid environment variables and `.env` for API keys (see project docs)
- Uses persona set: `persona-v3-limited-agents`
- Persists outputs under `code-netlogo-to-lucim-agentic-workflow/output/runs/<YYYY-MM-DD>/<HHMM>-<PERSONA_SET>/...`

## Cross-References

- Overview: `code-netlogo-to-lucim-agentic-workflow/docs/README.md`
- Orchestration flow details: `code-netlogo-to-lucim-agentic-workflow/docs/orchestration-flow.md`
- Workflow summary and known inconsistencies: `code-netlogo-to-lucim-agentic-workflow/docs/orchestrator_workflow_summary.md`

## Migration Guidance

- Prefer `orchestrator_persona_v3.py` for documentation, examples, and validations.
- Legacy orchestrators should be considered non-authoritative; align their behavior or docs with this reference when needed.


