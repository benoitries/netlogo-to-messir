# Orchestration Flow Documentation

This document provides a precise, concise description of the end-to-end orchestration flow, including per-agent inputs/outputs and conditional branches.

> Reference Orchestrator: The canonical implementation of the multi-agent workflow is `code-netlogo-to-lucim-agentic-workflow/archive/orchestrator_persona_v3.py`. See `docs/ORCHESTRATOR_REFERENCE.md` for details and run instructions.

## Pipeline Overview

The system implements an 8-stage pipeline with parallel execution for stages 01-02, followed by sequential processing from stage 03 onwards.

**Execution Order:**
1. **Stages 01-02**: Parallel execution (Syntax Parser + Behavior Extractor)
2. **Stages 03-08**: Sequential execution with conditional branches

**Output Structure:**
```
code-netlogo-to-lucim/output/runs/<YYYY-MM-DD>/<HHMM>-<PERSONA-SET>/<case>-<model>-reason-<X>-verb-<Y>/<NN-stage>/
```

## Per-Agent I/O and Conditions

### 01 — NetLogo Abstract Syntax Extractor (`agent_1_netlogo_abstract_syntax_extractor.py`)

**Inputs:**
- NetLogo code content (string from `input-netlogo/<case>-netlogo-code.md`)
- IL-SYN mapping file: `input-persona/<PERSONA-SET>/DSL_IL_SYN-mapping.md`
- IL-SYN description file: `input-persona/<PERSONA-SET>/DSL_IL_SYN-description.md`
- Persona instructions: `input-persona/<PERSONA-SET>/PSN_1_NetLogoAbstractSyntaxExtractor.md`

**Outputs:**
- `output-response.json` (agent response)
- `output-reasoning.md` (reasoning trace)
- `output-data.json` (AST structure)
- `output-raw_response.json` (raw API response)
- `input-instructions.md` (exact system prompt given to the AI model)

**Conditions:**
- If IL-SYN reference files are missing: warning logged, processing continues with reduced context
- Always executes in parallel with Behavior Extractor (stage 02)

### 02 — Behavior Extractor (`agent_2_netlogo_behavior_extractor.py`)

**Inputs:**
- IL-SEM mapping file: `input-persona/<PERSONA-SET>/DSL_IL_SEM-mapping.md`
- IL-SEM description file: `input-persona/<PERSONA-SET>/DSL_IL_SEM-description.md`
- UI interface images: `input-netlogo/<case>-netlogo-interface-1.png`, `input-netlogo/<case>-netlogo-interface-2.png`
- Persona instructions: `input-persona/<PERSONA-SET>/PSN_2b_NetlogoBehaviorExtractor.md`

**Outputs:**
- `output-response.json` (agent response)
- `output-reasoning.md` (reasoning trace)
- `output-data.json` (state machine)
- `output-raw_response.json` (raw API response)
- `input-instructions.md` (exact system prompt given to the AI model)

**Conditions:**
- Forbids AST/raw code input (deprecated paths raise `NotImplementedError`)
- Always executes in parallel with Syntax Parser (stage 01)
- If UI images are missing: processing continues with reduced context

### 03 — LUCIM Operation Synthesizer (`agent_lucim_operation_generator.py`)

**Inputs:**
- State machine from Stage 02: `../02-behavior_extractor/output-data.json`
- LUCIM/UCI rules: `input-persona/<PERSONA-SET>/DSL_Target_LUCIM-full-definition-for-compliance.md`
- Persona instructions: `input-persona/<PERSONA-SET>/PSN_3_LUCIMEnvironmentSynthesizer.md`

**Outputs:**
- `output-response.json` (agent response)
- `output-reasoning.md` (reasoning trace)
- `output-data.json` (LUCIM operation model)
- `output-raw_response.json` (raw API response)
- `input-instructions.md` (exact system prompt given to the AI model)

**Conditions:**
- Executes sequentially after stages 01-02 completion
- No iCrash references are required or expected

### 04 — LUCIM Scenario Synthesizer (`agent_4_lucim_scenario_synthesizer.py`)

**Inputs:**
- State machine from Stage 02: `../02-behavior_extractor/output-data.json`
- LUCIM operation model from Stage 03: `../03-lucim_operation_synthesizer/output-data.json`
- LUCIM DSL definition: `input-persona/<PERSONA-SET>/DSL_Target_LUCIM-full-definition-for-compliance.md`
- iCrash references: removed
- Persona instructions: `input-persona/<PERSONA-SET>/PSN_4_LUCIMScenarioSynthesizer.md`

**Outputs:**
- `output-response.json` (agent response)
- `output-reasoning.md` (reasoning trace)
- `output-data.json` (scenarios)
- `output-raw_response.json` (raw API response)
- `input-instructions.md` (exact system prompt given to the AI model)

**Conditions:**
- All inputs are MANDATORY; failure if any are missing
- Executes sequentially after stage 03 completion

Note on Correctors:
- There is no LLM-based corrector for Operation Model or Scenarios in this pipeline. Audit steps may report issues; corrections must be handled via deterministic tools or manual iteration. Do not add `agent_lucim_operation_corrector.py` or `agent_lucim_scenario_corrector.py`.

### 05 —LUCIM PlantUML Diagram Generator (`agent_lucim_plantuml_diagram_generator.py`)

**Inputs:**
- Scenarios from Stage 04: `../04-lucim_scenario_synthesizer/output-data.json`
- LUCIM/UCI rules: `input-persona/<PERSONA-SET>/DSL_Target_LUCIM-full-definition-for-compliance.md`
- Persona instructions: `input-persona/<PERSONA-SET>/PSN_5_PlantUMLWriter.md`

**Outputs:**
- `output-response.json` (agent response)
- `output-reasoning.md` (reasoning trace)
- `output-data.json` (diagram payload including PlantUML text)
- `diagram.puml` (standalone PlantUML diagram)
- `output-raw_response.json` (raw API response)
- `input-instructions.md` (exact system prompt given to the AI model)

**Conditions:**
- If JSON payload lacks clear diagram field: falls back to extracting `@startuml...@enduml` blocks
- Executes sequentially after stage 04 completion

### 06 — LUCIM PlantUML Diagram Auditor (`agent_lucim_plantuml_diagram_auditor.py`)

**Inputs:**
- Standalone PlantUML file from Stage 05: `../05-plantuml_writer/diagram.puml` (MANDATORY)
- LUCIM DSL definition: `input-persona/<PERSONA-SET>/DSL_Target_LUCIM-full-definition-for-compliance.md` (MANDATORY)
- Persona instructions: `input-persona/<PERSONA-SET>/PSN_6_PlantUMLLUCIMAuditor.md`

**Outputs:**
- `output-response.json` (agent response)
- `output-reasoning.md` (reasoning trace)
- `output-data.json` (audit results with non-compliant rules and verdict)
- `output-raw_response.json` (raw API response)
- `input-instructions.md` (exact system prompt given to the AI model)

**Conditions:**
- Both inputs are MANDATORY; failure if either is missing
- Executes sequentially after stage 05 completion
- Uses manual polling style (divergent from centralized helper used by other agents)



## Conditional Branching Logic

### Parallel Execution (Stages 01-02)
- **Condition**: Always parallel for optimal throughput
- **Timeout**: Configurable via `ORCHESTRATOR_PARALLEL_TIMEOUT` (default: no timeout)
- **Heartbeat**: Optional heartbeat logging every `HEARTBEAT_SECONDS` seconds
- **Error Handling**: If either stage fails, the other continues; both results are processed

### Sequential Execution (Stages 03-08)
- **Condition**: Always sequential after parallel stages complete
- **Dependencies**: Each stage depends on outputs from previous stages
- **Error Propagation**: If any stage fails, subsequent stages may be skipped or use fallback data

### Correction Branching (Stage 07)
- **Condition**: Only executes if Stage 06 audit finds non-compliance
- **Skip Condition**: If Stage 06 passes compliance, Stage 07 is skipped entirely
- **Fallback**: If Stage 07 fails, Stage 08 still executes with original diagrams

## File Naming Patterns

### Standard Artifacts (All Stages)
- `output-response.json`: Structured agent response
- `output-reasoning.md`: Human-readable reasoning trace
- `output-data.json`: Stage-specific data payload
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

*Generated on 2025-01-27. For authoritative findings and detailed inconsistencies, see `orchestrator_workflow_summary.md`.*
