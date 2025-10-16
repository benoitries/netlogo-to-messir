# Orchestration Workflow Summary (Findings)

This document summarizes the current orchestration flow and highlights ambiguities and I/O inconsistencies identified across agents and the orchestrator. It is concise by design.

---

## Pipeline Overview
- Stages: 01 Syntax Parser + 02 Semantics Parser (parallel) → 03 Messir Mapper → 04 Scenario Writer → 05 PlantUML Writer → 06 PlantUML Messir Auditor → 07 PlantUML Messir Corrector → 08 Final Auditor
- Output root: `code-netlogo-to-messir/output/runs/<YYYY-MM-DD>/<HHMM>/<case>-<model>-reason-<X>-verb-<Y>/<NN-stage>/`
- Each stage writes standardized artifacts: `output-response.json`, `output-reasoning.md`, `output-data.json` (+ optional `.puml` for diagram stages).

---

## Per-Agent I/O and Notes

### 01 — Syntax Parser (`netlogo_syntax_parser_agent.py`)
- Inputs: NetLogo code (string), optional filename; IL-SYN references via `update_il_syn_inputs()` or defaults to `input-persona/DSL_IL_SYN-*.md`.
- Outputs: `output-response.json`, `output-reasoning.md`, `output-data.json` (AST); minimal artifacts via helper.
- Conditions: Proceeds even if IL-SYN files are missing (warn-only).

### 02 — Semantics Parser (`netlogo_semantics_parser_agent.py`)
- Inputs: IL-SEM mapping/description (absolute paths); two UI images (preferred). No AST/raw code accepted.
- Outputs: `output-response.json`, `output-reasoning.md`, `output-data.json` (state machine); minimal artifacts.
- Conditions: Deprecated methods for AST/raw code raise `NotImplementedError`.

### 03 — Messir Mapper (`netlogo_messir_mapper_agent.py`)
- Inputs: State machine (dict); optional iCrash PDF extracts (inline text).
- Outputs: `output-response.json`, `output-reasoning.md`, `output-data.json` (Messir concepts); minimal artifacts.
- Notes: Token usage extraction slightly differs but end fields remain usable.

### 04 — Scenario Writer (`netlogo_scenario_writer_agent.py`)
- Inputs: Messir concepts (dict).
- Outputs: `output-response.json`, `output-reasoning.md`, `output-data.json` (scenarios); minimal artifacts.

### 05 — PlantUML Writer (`netlogo_plantuml_writer_agent.py`)
- Inputs: Scenarios (dict); optionally non-compliant rules list.
- Outputs: `output-response.json`, `output-reasoning.md`, `output-data.json`; standalone `diagram.puml` when extractable.
- Conditions: If JSON shape varies, falls back to extracting `@startuml...@enduml` from raw content.

### 06 — PlantUML Messir Auditor (`netlogo_plantuml_auditor_agent.py`)
- Inputs: PlantUML diagrams (dict), scenarios (dict).
- Outputs: `output-response.json`, `output-reasoning.md`, `output-data.json`; minimal artifacts.
- Notes: Uses manual polling for Responses API instead of centralized helper; reasoning MD is more verbose than other agents.

### 07 — PlantUML Messir Corrector (`netlogo_plantuml_messir_corrector_agent.py`)
- Inputs: Diagrams (dict), scenarios (dict), non-compliant rules (list). If rules list is empty → returns original diagrams unchanged.
- Outputs: `output-response.json`, `output-reasoning.md`, `output-data.json`; corrected `*_diagram.puml` (detailed filename).

### 08 — Final Auditor
- Implementation: Reuses the PlantUML Auditor class instance for the final pass.
- Outputs: Same trio under the final stage folder.

---

## Ambiguities and I/O Inconsistencies
- `.puml` naming divergence:
  - Writer emits `diagram.puml` (simple, canonical name).
  - Corrector emits `<base>_<timestamp>_<model>_plantuml_corrector_diagram.puml` (detailed).
  - Recommendation: Document as intentional or unify naming for consistency.
- Token usage extraction differences:
  - Some agents use a centralized helper (`get_usage_tokens`), others partially read `response.usage` directly.
  - Outcome fields converge (`visible_output_tokens`, `reasoning_tokens`, `total_output_tokens`); behavior acceptable but could be standardized.
- Auditor polling style:
  - Auditor/Corrector implement manual polling; other agents rely on `create_and_wait()` helper. Consider unifying for consistency.
- Missing reference files behavior:
  - IL-SYN/IL-SEM rule files missing trigger warnings but do not hard-fail. This is intentional and documented; acceptable.
- Stage 2 input constraints:
  - Semantics Parser forbids AST/raw code. Ensure orchestrator never invokes deprecated entry points.

---

## Orchestrator Highlights (`netlogo_orchestrator.py`)
- Initializes all agents with absolute reference paths for IL-SYN/IL-SEM.
- Runs 01–02 in parallel; downstream stages sequential.
- Tracks execution times and token usage per stage (no caps).
- Uses distinct per-stage folders, avoiding overlap even when Auditor class is reused for the final audit.

---

## Recommendations
- Decide on a unified `.puml` naming scheme or explicitly document the current difference (Writer vs Corrector).
- Standardize token usage extraction via the existing helper across all agents for uniform logs.
- Consider moving Auditor/Corrector to the centralized `create_and_wait()` helper for consistency.
