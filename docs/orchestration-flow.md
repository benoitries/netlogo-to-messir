# Orchestration Flow Documentation

This document provides a precise, concise description of the end-to-end orchestration flow, including per-agent inputs/outputs and conditional branches.

> Reference Orchestrator: The canonical implementation of the multi-agent workflow is `code-netlogo-to-lucim-agentic-workflow/archive/orchestrator_persona_v3.py`. See `docs/ORCHESTRATOR_REFERENCE.md` for details and run instructions.

## Pipeline Overview

The system implements a 3-stage sequential pipeline in ADK v3 mode. Each stage runs iteratively as a pair "Generator ↔ Auditor" with feedback until compliance or a maximum number of iterations is reached.

**Execution Order (sequential, each with audit-driven iterations):**
1. Operation Model Generator (iterative with audit feedback)
2. Scenario Generator (iterative with audit feedback)
3. PlantUML Diagram Generator (iterative with audit feedback)

**Output Structure:**
```
code-netlogo-to-lucim/output/runs/<YYYY-MM-DD>/<HHMM>-<PSvX>[-<version>]/<case>-<model>-<RXX>-<VXX>/<NN-stage>/
```
Where `<PSvX>` is persona set short code (e.g., PSv3 for persona-v3-limited-agents-v3-adk), `<RXX>` is reasoning effort short code (RMI=minimal, RLO=low, RME=medium, RHI=high) and `<VXX>` is verbosity short code (VLO=low, VME=medium, VHI=high).

## Per-Agent I/O and Conditions

### 01 — LUCIM Operation Model (Generator ↔ Auditor iterations)

Generator: `agent_lucim_operation_generator.py`

**Inputs:**
- NetLogo source code: `experimentation/input/input-netlogo/<case>-netlogo-code.md`
- NetLogo→LUCIM mapping: loaded via orchestrator (`load_netlogo_lucim_mapping`)
- Persona instructions: `input-persona/<PERSONA-SET>/PSN_LUCIM_Operation_Model_Generator.md`
- LUCIM/UCI rules: `input-persona/<PERSONA-SET>/DSL_Target_LUCIM-full-definition-for-compliance.md`

**Outputs:**
- `output-response.json` (agent response)
- `output-reasoning.md` (reasoning trace)
- `output-data.json` (raw LLM text content containing LUCIM operation model, plain text)
- `output-raw_response.json` (raw API response)
- `input-instructions.md` (exact system prompt given to the AI model)

**Conditions:**
- Executes first; mandatory inputs must be present
- No iCrash references are required or expected

Audit sub-step (per iteration):
- Auditor (LLM) function: `agent_lucim_operation_auditor.audit_operation_model`
- Python deterministic audit: `utils_audit_operation_model.audit_environment`
 - Outputs stored under `1_lucim_operation_model/iter-<k>/2-auditor/` (raw audit text content in `output-data.json` verbatim from LLM as plain text, `output-reasoning.md`, raw response). Orchestrator derives `verdict` and `non-compliant-rules` for logs/branching via `utils_audit_core.extract_audit_core`.

### 02 — LUCIM Scenario (Generator ↔ Auditor iterations)

Generator: `agent_lucim_scenario_generator.py`

**Inputs:**
- LUCIM operation model raw text from Stage 01: `../lucim_operation_model_generator/output-data.json` (plain text)
- Persona instructions: `input-persona/<PERSONA-SET>/PSN_LUCIM_Scenario_Generator.md`
- Scenario rules (mandatory): `input-persona/<PERSONA-SET>/RULES_LUCIM_Scenario.md`
- Scenario rules (mandatory): `input-persona/<PERSONA-SET>/RULES_LUCIM_Scenario.md`

**Outputs:**
- `output-response.json` (agent response)
- `output-reasoning.md` (reasoning trace)
- `output-data.json` (raw LLM text content containing scenarios, plain text)
- `output-raw_response.json` (raw API response)
- `input-instructions.md` (exact system prompt given to the AI model)

**Conditions:**
- All inputs are MANDATORY; failure if any are missing
- No agent consumes `LUCIM-DSL-DESCRIPTION`; Scenario Generator relies on persona + scenario rules only.
- Executes sequentially after stage 01 completion

Audit sub-step (per iteration):
- Auditor (LLM) function: `agent_lucim_scenario_auditor.audit_scenario_text`
- Python deterministic audit: `utils_audit_scenario.audit_scenario`
- Inputs for audit include a textual rendering of scenario messages and scenario rules
 - Outputs stored under `2_lucim_scenario/iter-<k>/2-auditor/` (raw audit text content in `output-data.json` verbatim from LLM as plain text, `output-reasoning.md`, raw response). Orchestrator derives `verdict` and `non-compliant-rules` via `utils_audit_core.extract_audit_core`.

Note on Correctors:
- There is no LLM-based corrector for Operation Model or Scenarios in this pipeline. Audit steps may report issues; corrections must be handled via deterministic tools or manual iteration. Do not add `agent_lucim_operation_corrector.py` or `agent_lucim_scenario_corrector.py`.

### 03 — LUCIM PlantUML Diagram (Writer ↔ Auditor iterations)

Generator/Writer: `agent_lucim_plantuml_diagram_generator.py`

**Inputs:**
- Scenarios raw text from Stage 02: `../lucim_scenario_generator/output-data.json` (plain text)
- Persona instructions: `input-persona/<PERSONA-SET>/PSN_LUCIM_PlantUML_Diagram_Generator.md`

**Outputs:**
- `output-response.json` (agent response)
- `output-reasoning.md` (reasoning trace)
- `output-data.json` (raw LLM text content containing diagram payload including PlantUML text, plain text)
- `diagram.puml` (standalone PlantUML diagram)
- `output-raw_response.json` (raw API response)
- `input-instructions.md` (exact system prompt given to the AI model)

**Conditions:**
- If JSON payload lacks clear diagram field: falls back to extracting `@startuml...@enduml` blocks
- Executes sequentially after stage 02 completion

Audit sub-step (per iteration):
- Auditor (LLM) method: `lucim_plantuml_diagram_auditor_agent.audit_plantuml_diagrams`
- Python deterministic audit: `utils_audit_diagram.audit_diagram`
- Inputs: standalone `diagram.puml` produced by the writer
 - Outputs stored under `3_lucim_plantuml_diagram/iter-<k>/2-auditor/` (raw audit text content in `output-data.json` verbatim from LLM as plain text, `output-reasoning.md`, raw response). Orchestrator derives `verdict` and `non-compliant-rules` via `utils_audit_core.extract_audit_core`.

### 04 — LUCIM PlantUML Diagram Auditor (`agent_lucim_plantuml_diagram_auditor.py`)

**Inputs:**
- Standalone PlantUML file from Stage 05: `../lucim_plantuml_diagram_generator/diagram.puml` (MANDATORY)
- Persona instructions: `input-persona/<PERSONA-SET>/PSN_LUCIM_Scenario_Auditor.md`

**Outputs:**
- `output-response.json` (agent response)
- `output-reasoning.md` (reasoning trace)
- `output-data.json` (raw LLM audit text content, plain text; orchestrator extracts verdict and non-compliant rules)
- `output-raw_response.json` (raw API response)
- `input-instructions.md` (exact system prompt given to the AI model)

**Conditions:**
- Both inputs are MANDATORY; failure if either is missing
- Executes sequentially after stage 05 completion
- Uses manual polling style (divergent from centralized helper used by other agents)



## Iteration & Branching Logic

- Each stage runs in a loop up to `MAX_AUDIT` iterations.
- After each Generator run, the corresponding Auditor evaluates compliance.
- If compliant: proceed to the next stage immediately.
- If non-compliant and iteration < `MAX_AUDIT`: feed back the audit report into the next Generator attempt.
- If non-compliant at `MAX_AUDIT`: proceed to the next stage with the latest artifact.

## File Naming Patterns

### Standard Artifacts (All Stages)
- `output-response.json`: Structured agent response
- `output-reasoning.md`: Human-readable reasoning trace
 - `output-data.json`: Stage-specific raw LLM text content (plain text, not JSON-encoded). For Auditor steps this is the verbatim LLM response text; the orchestrator extracts `verdict` and rules with `utils_audit_core.extract_audit_core` for logging/decisions.
- `output-raw_response.json`: Raw OpenAI API response
- `input-instructions.md`: Exact system prompt given to the AI model

### Stage-Specific Artifacts
- **Stage 05**: `diagram.puml` (standalone PlantUML)
<!-- Stage 07 corrected diagram naming removed -->

## Known Inconsistencies

1. **Polling Style Divergence**: Stages 06-08 use manual polling while stages 01-05 use centralized helper
2. **Diagram Naming**: Stage 05 uses simple `diagram.puml` while Stage 07 uses detailed timestamped naming
3. **Token Usage Extraction**: Inconsistent extraction methods across agents (centralized vs manual)

## Compliance Metrics in Logs

When both Stage 06 (PlantUML LUCIM Auditor) and Stage 08 (Final Auditor) produce outputs, the orchestrator appends a metrics section at the end of the run logs:

- Labeling convention: positive = compliant
- Metrics: TP, FP, TN, FN and Precision, Recall, Specificity, Accuracy, F1
- Where to find: console logs and the final orchestration summary output (same stream as other end-of-run summaries)

If only a single auditor output is available, a compact audit summary (final verdict, number of non-compliant rules, coverage counts) is printed instead.

## Validation

This flow has been validated against:
- `validate_output_layout.py`: Confirms directory structure and file patterns
- `validate_task_success_criteria.py`: Ensures task completion tracking
- Live orchestration runs: Verified with actual execution logs

---

*Generated on 2025-01-27. This document is the Single Source of Truth (SSOT) for the orchestrated workflow; other docs must reference this file.*
