# Orchestration Workflow Summary (Findings)

This document summarizes the current orchestration flow and highlights ambiguities and I/O inconsistencies identified across agents and the orchestrator. It is concise by design.

---

## Pipeline Overview
- Agents (in order): LUCIM Operation Model Generator → LUCIM Operation Model Auditor → LUCIM Scenario Generator → LUCIM Scenario Auditor → LUCIM PlantUML Diagram Generator → LUCIM PlantUML Diagram Auditor.
- Generators auto-correct when their paired Auditor flags non-compliance (no separate Corrector agent).
- Output root: `code-netlogo-to-lucim-agentic-workflow/output/runs/<YYYY-MM-DD>/<HHMM>-<PSvX>[-<version>]/<case>-<model>-<RXX>-<VXX>/<NN-stage>/`.
  Where `<PSvX>` is persona set short code (e.g., PSv3), `<RXX>` is reasoning effort short code (RMI/RLO/RME/RHI) and `<VXX>` is verbosity short code (VLO/VME/VHI).
- Each stage writes standardized artifacts: `output-response.json`, `output-reasoning.md`, `output-data.json` (raw LLM text content, plain text), `output-raw_response.json` (+ optional `.puml` for diagram stages), and `input-instructions.md` (contains the exact system prompt given to the AI model).

---

## Per-Agent I/O

### LUCIM Operation Model Generator (`agent_lucim_operation_generator.py`)
- Inputs: NetLogo source code and `RULES_MAPPING_NETLOGO_TO_OPERATION_MODEL`.
- Outputs: `output-data.json` (raw LLM text content containing operation model, plain text).
- Notes: Performs exhaustive and complete corrections when the paired Auditor reports non-compliance.
- Common artifacts: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md` (exact system prompt given to the AI model).

### LUCIM Operation Model Auditor (`agent_lucim_operation_auditor.py`)
- Inputs: Operation model raw text (from `output-data.json`) and `RULES_LUCIM_Operation_model.md` (LUCIM Operation Model Rules).
- Outputs: `output-data.json` (raw LLM audit text content, plain text; orchestrator derives verdict + non-compliant rules via `utils_audit_core.extract_audit_core`).
- Common artifacts: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md` (exact system prompt given to the AI model).

### LUCIM Scenario Generator (`agent_lucim_scenario_generator.py`)
- Inputs: Operation model raw text (from `output-data.json`) only.
- Outputs: `output-data.json` (raw LLM text content containing scenarios, plain text).
- Notes: Performs minimal auto-corrections if the paired Auditor reports non-compliance.
- Common artifacts: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md` (exact system prompt given to the AI model).

### LUCIM Scenario Auditor (`agent_lucim_scenario_auditor.py`)
- Inputs: Scenario raw text (from `output-data.json`) and `RULES_LUCIM_Scenario.md` (LUCIM Scenario Rules).
- Outputs: `output-data.json` (raw LLM audit text content, plain text; orchestrator derives verdict + non-compliant rules via `utils_audit_core.extract_audit_core`).
- Common artifacts: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md` (exact system prompt given to the AI model).

### LUCIM PlantUML Diagram Generator (`agent_lucim_plantuml_diagram_generator.py`)
- Inputs: Scenarios raw text (from `output-data.json`) and `RULES_LUCIM_PlantUML_Diagram.md` (LUCIM Diagram Rules).
- Outputs: `diagram.puml` (standalone); `output-data.json` (raw LLM text content containing diagram payload incl. PlantUML text, plain text).
- Notes: Performs minimal auto-corrections if the paired Auditor reports non-compliance.
- Common artifacts: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md` (exact system prompt given to the AI model).

### LUCIM PlantUML Diagram Auditor (`agent_lucim_plantuml_diagram_auditor.py`)
- Inputs (mandatory): standalone `.puml` and the LUCIM DSL full definition.
- Outputs: `output-data.json` (raw LLM audit text content, plain text; orchestrator derives verdict + non-compliant rules via `utils_audit_core.extract_audit_core`).
- Common artifacts: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md` (exact system prompt given to the AI model).

---

## Notes and Conditions
- Missing IL-SYN/IL-SEM reference files: warn-only; processing continues with reduced context.
- Deprecated AST ingestion paths remain unsupported.
- PlantUML Generator falls back to extracting `@startuml...@enduml` if JSON payload lacks a clear diagram field.
- Auditors and Generators may use different polling styles; standardization is ongoing.

---

## Recommendations
- Keep `.puml` naming conventions documented and consistent across runs.
- Standardize token usage extraction and polling style across agents for uniform logs and maintenance.
