# NetLogo to LUCIM Multi-Agent Orchestration System

A sophisticated multi-agent AI system that automatically converts NetLogo agent-based models into LUCIM (Multi-Entity System Specification in Relational) diagrams through an orchestrated pipeline of specialized AI agents.

## 🚀 Overview

This project implements an ADK v3 3-stage iterative orchestration pipeline that transforms NetLogo simulation models into standardized LUCIM PlantUML diagrams. Each stage runs as Generator ↔ Auditor iterations with feedback until compliance or cap.

### Key Features

- **Multi-Agent Architecture**: specialized AI agents handling different aspects of the conversion
- **Multi-Persona Support**: Interactive selection of persona sets for different agent configurations
- **Automated Orchestration**: Parallel-first for steps 01–02, then sequential with error correction and compliance auditing
- **LUCIM Compliance**: Ensures generated diagrams follow LUCIM-UCI standards
- **Multiple AI Model Support**: Compatible with GPT-5, GPT-5-mini, and GPT-5-nano
- **Comprehensive Logging**: Detailed execution tracking and performance metrics
- **Cost Optimization**: Built-in cost analysis and token usage monitoring

### Workflow Summary

Single Source of Truth (SSOT) for the orchestration flow, per-agent inputs/outputs, and iteration logic:

- `code-netlogo-to-lucim-agentic-workflow/docs/orchestration-flow.md`

### Reference Orchestrator (Canonical)
The canonical reference implementation of the multi-agent workflow is:

- `code-netlogo-to-lucim-agentic-workflow/orchestrator_persona_v3_adk.py`

See `code-netlogo-to-lucim-agentic-workflow/docs/ORCHESTRATOR_REFERENCE.md` for rationale and run instructions.

### Canonical system_prompt order
All agents construct `system_prompt` using a single canonical order for determinism and auditability:

1) task_content
2) persona
3) agent-specific instructions (e.g., LUCIM rules)
4) agent-specific inputs (e.g., state_machine, scenarios, .puml)

This order is enforced across all agents and is reflected in saved `input-instructions.md` artifacts, which contain the exact system prompt given to the AI model.

## 🏗️ Architecture

### The Orchestration Pipeline (ADK v3 — 3 Stages, Iterative)

1. **LUCIM Operation Model (Generator ↔ Auditor)** — Iterative until compliant or cap
2. **LUCIM Scenario (Generator ↔ Auditor)** — Iterative until compliant or cap
3. **LUCIM PlantUML Diagram (Writer ↔ Auditor)** — Iterative until compliant or cap

### AI Agents

- LUCIM Operation Model Generator (`agent_lucim_operation_generator.py`)
- LUCIM Operation Model Auditor (`agent_lucim_operation_auditor.py`)
- LUCIM Scenario Generator (`agent_lucim_scenario_generator.py`)
- LUCIM Scenario Auditor (`agent_lucim_scenario_auditor.py`)
- LUCIM PlantUML Diagram Generator (`agent_lucim_plantuml_diagram_generator.py`)
- LUCIM PlantUML Diagram Auditor (`agent_lucim_plantuml_diagram_auditor.py`)

## 📁 Project Structure

Note: Persona directories under `input-persona/` are symbolic links to `experimentation/input/input-persona/`. The default persona set is `persona-v3-limited-agents`; you can change it at runtime via the interactive selection menu.

```
code-netlogo-to-lucim-agentic-workflow/
├── orchestrator_persona_v3_adk.py         # Main orchestration (ADK-integrated)
├── agent_lucim_operation_generator.py     # LUCIM Operation Model generator
├── agent_lucim_operation_auditor.py       # LUCIM Operation Model auditor
├── agent_lucim_scenario_generator.py      # LUCIM Scenario generator
├── agent_lucim_scenario_auditor.py        # LUCIM Scenario auditor
├── agent_lucim_plantuml_diagram_generator.py             # PlantUML generation agent
├── agent_lucim_plantuml_diagram_auditor.py            # PlantUML LUCIM auditor
├── utils_config_constants.py              # Configuration and paths
├── utils_openai_client.py                 # OpenAI Responses API helpers
├── scripts/                               # Run scripts (e.g., run_default_nano.py)
├── input-netlogo/                         # NetLogo case studies
├── input-persona/                         # Persona sets (symlinks to experimentation/input)
├── input-valid-examples/                  # Example diagrams and concepts
└── output/                                # Generated results (see Output Layout below)
```

## 🛠️ Installation

### Prerequisites

- Python 3.11+
- OpenAI API key
- Google ADK credentials (if using Google models)

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/netlogo-to-lucim.git
   cd netlogo-to-lucim
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API keys:**
   
   The system automatically loads OpenAI API keys from `.env` files. Create a `.env` file in the project root:
   
   ```bash
   # Create .env file in project root
   echo "OPENAI_API_KEY=your-api-key-here" > .env
   ```
   
   The system will automatically search for `.env` files in multiple locations:
   - Project root directory
   - Code directory (`code-netlogo-to-lucim/`)
   - Parent directories
   
   **Alternative methods:**
   - Set environment variable: `export OPENAI_API_KEY="your-api-key-here"`
   - Use the validation script: `python test_api_key_setup.py`
   
   **Validation:**
   ```bash
   # Test API key setup
   python test_api_key_setup.py
   
   # Or validate from within the code directory
   cd code-netlogo-to-lucim-agentic-workflow
   python utils_api_key.py validate
   ```

## 🚀 Usage

### Quick Start: Default Nano Model (Parallel)

Run the orchestrator with a single command using the default nano model, the first case study (3d-solids), medium reasoning effort and medium text verbosity. Steps 01–02 always run in parallel:

```bash
export OPENAI_API_KEY="<YOUR-API-KEY>" && \
python3 code-netlogo-to-lucim-agentic-workflow/scripts/run_default_nano.py | cat
```

This will persist outputs under the canonical structure in `code-netlogo-to-lucim-agentic-workflow/output/runs/<YYYY-MM-DD>/<HHMM>-<PSvX>[-<version>]/<case>/`.
Where `<PSvX>` is persona set short code (e.g., PSv3 for persona-v3-limited-agents-v3-adk).

### Experimentation parameters

- Reasoning: `reasoning: { effort: "minimal" | "low" | "medium" | "high" }` (default: `medium`)
- Text: `text: { verbosity: "low" | "medium" | "high" }` (default: `medium`)
- Persona Set: Interactive selection from available persona sets in `input-persona/` (default: `persona-v3-limited-agents`)

These parameters are supported through:
- Direct programmatic calls: use `update_agent_configs(orchestrator, reasoning_effort=..., reasoning_summary=..., text_verbosity=...)` from `utils_orchestrator_v3_agent_config`
- Terminal interactive flow: select reasoning effort (now including "minimal") and text verbosity when prompted
- Persona set selection: Interactive menu listing all available persona sets, with `persona-v3-limited-agents` as default

### OpenAI API Usage

This project uses a provider-aware routing strategy:

- OpenAI and Gemini models → OpenAI Responses API with polling.
- OpenRouter models (e.g., Mistral, Llama) → Chat Completions endpoint.

Rationale: Many OpenRouter-provided models (notably Mistral/Llama) do not expose the Responses API path and would return HTTP 404 when called there. Chat Completions is the canonical, widely supported endpoint for those models.

Defaults for OpenRouter Chat Completions calls:
- `max_tokens = 50000` 
- `temperature = 0.2`
- `top_p` left as provider default

Required OpenRouter headers are passed per call:
- `HTTP-Referer` (from `OPENROUTER_HTTP_REFERER`, fallback to repository URL)
- `X-Title` (from `OPENROUTER_X_TITLE`, fallback to a project name)

#### Automatic API Key Management

The system includes automatic API key management with the following features:

- **Automatic .env loading**: Searches for `.env` files in multiple locations
- **Validation**: Tests API keys with meaningful error messages
- **Centralized management**: Single utility (`utils_api_key.py`) for all API key operations
- **Cursor rule integration**: Automatic guidance for developers

**Key utilities:**
- `utils_api_key.get_openai_api_key()`: Loads API key from .env files
- `utils_api_key.validate_openai_key()`: Validates API key with test call
- `utils_api_key.create_openai_client()`: Creates configured OpenAI client
- `utils_openai_client.validate_openai_setup()`: Validates setup before operations

**Error handling:**
The system provides clear error messages when API keys are missing or invalid, including instructions for creating `.env` files.

- Client: `from openai import OpenAI` with `client.responses.create(...)`
- Reference: `https://platform.openai.com/docs/guides/latest-model#migrating-from-chat-completions-to-responses-api`

#### Migration to OpenAI 2.x (Notes)
- The project migrated from legacy Chat Completions to the unified Responses API.
- Redundant polling/extraction code was centralized into `utils_openai_client.py`.
- Environment: pinned `openai>=2,<3` in `requirements.txt`. Removed unused `openai-agents` if present.

Before (1.x style):
```python
resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
)
text = resp.choices[0].message.content
```

After (2.x Responses):
```python
from openai import OpenAI
from utils_openai_client import create_and_wait, get_output_text

client = OpenAI()
response = create_and_wait(client, {
    "model": "gpt-4o-mini",
    "instructions": "You are a helpful assistant.",
    "input": [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
})
text = get_output_text(response)
```

Helper functions:
- `create_and_wait(client, api_config)`: create a response job and poll until completed (raises on failure/timeout).
- `get_output_text(response)`: best-effort plain text extraction (uses `response.output_text` when available).
- `get_reasoning_summary(response)`: tolerant extraction of reasoning summary when present.

#### Token usage semantics (logging)
- The Responses API enforces `max_output_tokens` (cap applies to model output only). All configuration keys and code paths use `max_output_tokens` consistently.
- Logged metrics per agent:
  - Input tokens: tokens sent to the model.
  - Reasoning tokens: subset of output used for chain-of-thought style reasoning (when available from `output_tokens_details`).
  - Output tokens: model completion tokens; this is the value compared to the cap.
  - Total tokens: Input + Output. This field is informational and is not capped.
- Example log lines:
  - `Input tokens: X, Reasoning tokens: R, Output tokens: Y (cap Z)`
  - `Output cap usage: P%`
  - `Total tokens: T (informational; not capped)`

#### Standardized token usage fields (single source of truth)

All agents now extract token usage through the centralized helper and emit harmonized fields in their results and artifacts:

- `visible_output_tokens`: output tokens excluding reasoning tokens
- `reasoning_tokens`: output tokens reported under `response.usage.output_tokens_details.reasoning_tokens` (0 if missing)
- `total_output_tokens`: output tokens reported under `response.usage.output_tokens` (0 if missing)

Single source of truth for extraction:

- Function: `utils_openai_client.get_usage_tokens(response, exact_input_tokens=None)`
  - Returns: `{ total_tokens, input_tokens, output_tokens, reasoning_tokens }`
  - Agents must derive `visible_output_tokens = max(output_tokens - reasoning_tokens, 0)`; `total_output_tokens` equals API `output_tokens` when available, otherwise fallback to `visible + reasoning`.

Compatibility notes:

- Historical artifacts may contain `output_tokens`; tooling derives `visible_output_tokens` when needed.
- Validators check consistency of `total_output_tokens == visible_output_tokens + reasoning_tokens`.

### Verdict extraction for Auditor artifacts

For Auditor agents, `output-data.json` stores the verbatim LLM `data` block (unaltered). The orchestrator extracts only the decision fields it needs for logging/branching using the helper:

```python
from utils_audit_core import extract_audit_core
core = extract_audit_core(llm_payload)
# core => { "data", "verdict", "non_compliant_rules", "coverage", "errors" }
```

This preserves rich auditor information (e.g., `fix_suggestions`) in artifacts while keeping orchestration decisions deterministic.

## 📂 Output Layout

All artifacts are organized per run, case, and agent step to improve traceability and avoid collisions:

```
code-netlogo-to-lucim-agentic-workflow/
  output/
    runs/
      YYYY-MM-DD/
        HHMM-<PSvX>[-<version>]/
          <case>-<model>-<RXX>-<VXX>/
          (PSvX: persona set short code, e.g., PSv3; RXX: RMI/RLO/RME/RHI for reasoning, VXX: VLO/VME/VHI for verbosity)
            <case>_<YYYYMMDD>_<HHMM>_<model>_orchestrator.log
            lucim_environment/
              0_synthesizer/          # Operation Model Generator
                input-instructions.md
                output-data.json
                output-raw_response.json
                output-reasoning.md
                output-response.json
              iter-1/                 # Iteration 1 (if corrections needed)
                1-generator/
                2-auditor/            # Operation Model Auditor
                  input-instructions.md
                  output-data.json     # raw LLM audit data (verbatim)
                  ...
                iter-1-corrector/     # Corrector (optional)
                  output-data.json
                  ...
                output_python_environment.md
              2_iter/                 # Iteration 2 (if needed)
                ...
            lucim_scenario/
              0_synthesizer/          # Scenario Generator
                input-instructions.md
                output-data.json
                ...
              iter-1/                 # Iteration 1 (if corrections needed)
                1-generator/
                2-auditor/            # Scenario Auditor
                  ...
                output_python_scenario.md
            plantuml/
              0_writer/               # PlantUML Diagram Generator
                diagram.puml
                input-instructions.md
                output-data.json
                ...
              iter-1/                 # Iteration 1 (if corrections needed)
                1-generator/
                2-auditor/            # PlantUML Diagram Auditor
                  output_python_diagram.md
                  ...
          <another-case>-<model>-<RXX>-<VXX>/
            ...
```

Each subfolder contains the agent's files named with the existing prefix format. Orchestrator logs are stored at the case level with the format `<case>_<YYYYMMDD>_<HHMM>_<model>_orchestrator.log`.

> Deprecation: The legacy `output/runs-<YYYYMMDD-HHMM>/` structure is no longer used for new runs. Historical runs remain as-is for reference.

### Validation

Layout validated on 2025-09-24 16:58 (timestamp tag `20250924_1658`).
Validation script: `code-netlogo-to-lucim/validate_output_layout.py` (simulated structure + checks for all step folders and orchestrator log presence).

Success Criteria rule validation executed on 2025-09-25 09:45 (local time).
Validation script: `code-netlogo-to-lucim/validate_task_success_criteria.py` (checks checked criteria have end-of-line timestamps and unchecked ones do not).

### Reference: LUCIM/UCI Rules Files (per agent)

New code paths use explicit rules files per stage under the active persona set (single source of truth in `utils_config_constants.py`):

- Operation Model rules: `RULES_LUCIM_OPERATION_MODEL`
- Scenario rules: `RULES_LUCIM_SCENARIO`
- Diagram rules: `RULES_LUCIM_PLANTUML_DIAGRAM`
- NetLogo→Operation mapping: `RULES_MAPPING_NETLOGO_TO_OPERATION_MODEL`

Quick verification commands:

```bash
rg -n "RULES_LUCIM_" code-netlogo-to-lucim-agentic-workflow
```

Cursor Rules validation executed on 2025-09-25 10:15 (local time).
Created rules:
- `.cursor/rules/000-core-project.mdc` (always applied)
- `.cursor/rules/100-orchestration-workflows.mdc` (manual workflows)
- `.cursor/rules/200-python-agents-patterns.mdc` (auto-attached to Python files)
- `.cursor/rules/210-latex-publication.mdc` (auto-attached to LaTeX files)
Templates added under `.cursor/rules/templates/`.

The system has been tested on diverse NetLogo models:

1. **3D Solids** - 3D visualization and manipulation
2. **Altruism** - Social behavior modeling
3. **Ant Adaptation** - Swarm intelligence
4. **Artificial Neural Network** - Machine learning simulation
5. **Boiling** - Physical process modeling
6. **Continental Divide** - Geographic simulation
7. **Diffusion Network** - Information spread
8. **Frogger** - Game mechanics modeling
9. **Piaget-Vygotsky** - Educational theory simulation
10. **Signaling Game** - Game theory implementation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- NetLogo community for providing diverse simulation models
- LUCIM-UCI specification contributors
- PlantUML project for diagram generation capabilities

## 📚 Citation

If you use this work in your research, please cite:

```bibtex
@software{netlogo_to_lucim_2025,
  title={NetLogo to LUCIM Multi-Agent Orchestration System},
  author={Ries, Benoit},
  year={2025},
  url={https://github.com/benoitries/netlogo-to-lucim}
}
```

---

*This project was vibe-coded with ❤️ using Cursor and Claude-4-Sonnet.*

### Validation — 2025-10-15 00:02 (local time)
- Removed all output token caps and legacy references across orchestrator and agents.
- Ran `validate_task_success_criteria.py` — OK.
- Layout validator points to historical archived runs only; current code paths unaffected.
