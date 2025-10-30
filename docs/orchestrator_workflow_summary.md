# Orchestration Workflow Summary (Findings)

This document summarizes the current orchestration flow and highlights ambiguities and I/O inconsistencies identified across agents and the orchestrator. It is concise by design.

---

## Pipeline Overview
- Stages: 01 Syntax Parser + 02 Behavior Extractor (parallel) → 03 LUCIM Environment Synthesizer → 04 LUCIM Scenario Synthesizer → 05 PlantUML Writer → 06 PlantUML LUCIM Auditor → 07 PlantUML LUCIM Corrector → 08 Final Auditor
- Output root: `code-netlogo-to-lucim-agentic-workflow/output/runs/<YYYY-MM-DD>/<HHMM>-<PERSONA-SET>/<case>-<model>-reason-<X>-verb-<Y>/<NN-stage>/`
- Each stage writes standardized artifacts: `output-response.json`, `output-reasoning.md`, `output-data.json` (+ optional `.puml` for diagram stages).

---

## Per-Agent I/O

### 01 — NetLogo Abstract Syntax Extractor (`agent_1_netlogo_abstract_syntax_extractor.py`)
- Agent-specific Input: NetLogo code (string); IL-SYN refs via `update_il_syn_inputs()` or defaults under `input-persona/DSL_IL_SYN-*.md`.
- Agent-specific Output: `output-data.json` (AST).
- Common Input: Persona instructions; configuration (model, reasoning, text verbosity).
- Common Output: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md`.

### 02 — Behavior Extractor (`agent_2_netlogo_behavior_extractor.py`)
- Agent-specific Input: IL-SEM mapping/description (absolute paths); two UI images (preferred).
- Agent-specific Output: `output-data.json` (state machine).
- Common Input: Persona instructions; configuration (model, reasoning, text verbosity).
- Common Output: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md`.

### 03 — LUCIM Environment Synthesizer (`agent_3_lucim_environment_synthesizer.py`)
- Agent-specific Input: State machine (from Step 02); LUCIM rules.
- Agent-specific Output: `output-data.json` (LUCIM environment concepts).
- Common Input: Persona instructions; configuration.
- Common Output: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md`.

### 04 — LUCIM Scenario Synthesizer (`agent_4_lucim_scenario_synthesizer.py`)
- Agent-specific Input: Step 02 state machine + Step 03 LUCIM concepts + LUCIM DSL full definition.
- Agent-specific Output: `output-data.json` (scenarios).
- Common Input: Persona instructions; configuration.
- Common Output: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md`.

### 05 — PlantUML Writer (`agent_5_plantuml_writer.py`)
- Agent-specific Input: Scenarios (from Step 04).
- Agent-specific Output: `diagram.puml` (standalone); `output-data.json` (diagram payload incl. PlantUML text).
- Common Input: Persona instructions; LUCIM rules; configuration.
- Common Output: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md`.

### 06 — PlantUML LUCIM Auditor (`agent_6_plantuml_auditor.py`)
- Agent-specific Input: standalone .puml file (from Step 05) and LUCIM DSL full definition (both mandatory).
- Agent-specific Output: `output-data.json` (audit with non-compliant rules and verdict).
- Common Input: Persona instructions; configuration.
- Common Output: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md`.

### 07 — PlantUML LUCIM Corrector (`agent_7_plantuml_corrector.py`)
- Agent-specific Input: PlantUML diagrams (from Step 05), non-compliant rules (from Step 06), LUCIM DSL full definition. 
- Agent-specific Output: `diagram.puml` (corrected standalone diagram); `output-data.json` (corrected diagram payload).
- Common Input: Persona instructions; LUCIM rules; configuration.
- Common Output: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md`.

### 08 — Final Auditor
- Agent-specific Input: Persona Auditor file (`PSN_6_PlantUMLLUCIMAuditor.md`), corrected PlantUML `.puml` from Step 07, and the LUCIM DSL full definition file.
- Agent-specific Output: `output-data.json` (final verdict).
- Common Output: `output-response.json`, `output-reasoning.md`, `output-raw_response.json`, `input-instructions.md`.

---

## Notes and Conditions
- Missing IL-SYN/IL-SEM reference files: warn-only; processing continues with reduced context.
- Behavior Extractor forbids AST/raw code; deprecated AST paths raise `NotImplementedError`.
- PlantUML Writer falls back to extracting `@startuml...@enduml` if JSON payload lacks a clear diagram field.
- Auditor/Corrector currently use manual polling; others use a centralized helper; behavior is consistent but stylistically divergent.

---

## Recommendations
- Keep `.puml` naming divergence documented (Writer simple vs Corrector detailed) or unify across both stages.
- Standardize token usage extraction and polling style across agents for uniform logs and maintenance.
