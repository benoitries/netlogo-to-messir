# Orchestration Workflow Summary (Findings)

This document summarizes the current orchestration flow and highlights ambiguities and I/O inconsistencies identified across agents and the orchestrator. It is concise by design.

---

## Pipeline Overview
- Stages: 01 Syntax Parser + 02 Semantics Parser (parallel) → 03 Messir Mapper → 04 Scenario Writer → 05 PlantUML Writer → 06 PlantUML Messir Auditor → 07 PlantUML Messir Corrector → 08 Final Auditor
- Output root: `code-netlogo-to-messir/output/runs/<YYYY-MM-DD>/<HHMM>/<case>-<model>-reason-<X>-verb-<Y>/<NN-stage>/`
- Each stage writes standardized artifacts: `output-response.json`, `output-reasoning.md`, `output-data.json` (+ optional `.puml` for diagram stages).

---

## Per-Agent I/O

### 01 — Syntax Parser (`netlogo_syntax_parser_agent.py`)
- Agent-specific Input: NetLogo code (string); IL-SYN refs via `update_il_syn_inputs()` or defaults under `input-persona/DSL_IL_SYN-*.md`.
- Agent-specific Output: `output-data.json` (AST).
- Common Input: Persona instructions; configuration (model, reasoning, text verbosity).
- Common Output: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md`.

### 02 — Semantics Parser (`netlogo_semantics_parser_agent.py`)
- Agent-specific Input: IL-SEM mapping/description (absolute paths); two UI images (preferred). No AST/raw code accepted.
- Agent-specific Output: `output-data.json` (state machine).
- Common Input: Persona instructions; configuration (model, reasoning, text verbosity).
- Common Output: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md`.

### 03 — Messir Mapper (`netlogo_messir_mapper_agent.py`)
- Agent-specific Input: State machine (from Step 02); optional iCrash PDF extracts; Messir/UCI rules.
- Agent-specific Output: `output-data.json` (Messir concepts).
- Common Input: Persona instructions; configuration.
- Common Output: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md`.

### 04 — Scenario Writer (`netlogo_scenario_writer_agent.py`)
- Agent-specific Input: Messir concepts (from Step 03).
- Agent-specific Output: `output-data.json` (scenarios).
- Common Input: Persona instructions; configuration.
- Common Output: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md`.

### 05 — PlantUML Writer (`netlogo_plantuml_writer_agent.py`)
- Agent-specific Input: Scenarios (from Step 04); optionally non-compliant rules list.
- Agent-specific Output: `diagram.puml` (standalone); `output-data.json` (diagram payload incl. PlantUML text).
- Common Input: Persona instructions; Messir/UCI rules; configuration.
- Common Output: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md`.

### 06 — PlantUML Messir Auditor (`netlogo_plantuml_auditor_agent.py`)
- Agent-specific Input: PlantUML diagrams and scenarios.
- Agent-specific Output: `output-data.json` (audit with non-compliant rules and verdict).
- Common Input: Persona instructions; Messir/UCI rules; configuration.
- Common Output: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md`.

### 07 — PlantUML Messir Corrector (`netlogo_plantuml_messir_corrector_agent.py`)
- Agent-specific Input: Diagrams, scenarios, non-compliant rules (required to change output; empty list returns original).
- Agent-specific Output: `diagram.puml` (corrected standalone diagram); `output-data.json` (corrected diagram payload).
- Common Input: Persona instructions; Messir/UCI rules; configuration.
- Common Output: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md`.

### 08 — Final Auditor
- Agent-specific Input: Corrected diagrams (from Step 07) and prior artifacts as context.
- Agent-specific Output: `output-data.json` (final verdict).
- Common Input: Persona instructions; Messir/UCI rules; configuration.
- Common Output: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md`.

---

## Notes and Conditions
- Missing IL-SYN/IL-SEM reference files: warn-only; processing continues with reduced context.
- Semantics Parser forbids AST/raw code; deprecated AST paths raise `NotImplementedError`.
- PlantUML Writer falls back to extracting `@startuml...@enduml` if JSON payload lacks a clear diagram field.
- Auditor/Corrector currently use manual polling; others use a centralized helper; behavior is consistent but stylistically divergent.

---

## Recommendations
- Keep `.puml` naming divergence documented (Writer simple vs Corrector detailed) or unify across both stages.
- Standardize token usage extraction and polling style across agents for uniform logs and maintenance.
