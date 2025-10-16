# NetLogo to MESSIR Multi-Agent Orchestration System

A sophisticated multi-agent AI system that automatically converts NetLogo agent-based models into MESSIR (Multi-Entity System Specification in Relational) diagrams through an orchestrated pipeline of specialized AI agents.

## 🚀 Overview

This project implements an 8-step orchestration pipeline that transforms NetLogo simulation models into standardized MESSIR PlantUML diagrams. The system uses multiple specialized AI agents; steps 01 (Syntax) and 02 (Semantics) are always executed in parallel to optimize throughput, and the pipeline continues sequentially from step 03.

### Key Features

- **Multi-Agent Architecture**: 7 specialized AI agents handling different aspects of the conversion
- **Automated Orchestration**: Parallel-first for steps 01–02, then sequential with error correction and compliance auditing
- **MESSIR Compliance**: Ensures generated diagrams follow MESSIR-UCI standards
- **Multiple AI Model Support**: Compatible with GPT-5, GPT-5-mini, and GPT-5-nano
- **Comprehensive Logging**: Detailed execution tracking and performance metrics
- **Cost Optimization**: Built-in cost analysis and token usage monitoring

## 🏗️ Architecture

### The 8-Step Orchestration Pipeline

1. **Syntax Parser** - Extracts and structures NetLogo code components
2. **Semantics Parser** - Analyzes behavioral patterns and agent interactions
3. **MESSIR Mapper** - Maps NetLogo concepts to MESSIR entities and relationships
4. **Scenario Writer** - Generates MESSIR scenario descriptions
5. **PlantUML Writer** - Creates PlantUML diagram code
6. **Compliance Auditor** - Validates MESSIR rule compliance
7. **Corrector** - Fixes non-compliance issues (if needed)
8. **Final Audit** - Confirms final compliance

### AI Agents

- `NetLogoSyntaxParser` - Code structure analysis
- `NetLogoSemanticsParser` - Behavioral pattern extraction
- `MessirMapper` - Concept mapping and translation
- `ScenarioWriter` - MESSIR scenario generation
- `PlantUMLWriter` - Diagram code generation
- `PlantUMLAuditor` - Compliance validation
- `PlantUMLCorrector` - Error correction

## 📁 Project Structure

```
netlogo-to-messir/
├── config.py                              # Configuration and paths
├── netlogo_orchestrator.py                # Main orchestration engine
├── netlogo_syntax_parser_agent.py         # Syntax parsing agent
├── netlogo_semantics_parser_agent.py      # Semantics analysis agent
├── netlogo_messir_mapper_agent.py         # MESSIR mapping agent
├── netlogo_scenario_writer_agent.py       # Scenario writing agent
├── netlogo_plantuml_writer_agent.py       # PlantUML generation agent
├── netlogo_plantuml_auditor_agent.py      # Compliance auditing agent
├── netlogo_plantuml_messir_corrector_agent.py # Error correction agent
├── logging_utils.py                       # Logging utilities
├── parse_orchestrator_times.py            # Performance analysis
├── requirements.txt                       # Python dependencies
├── input-netlogo/                         # NetLogo case studies
│   ├── 3d-solids-netlogo-code.md
│   ├── altruism-netlogo-code.md
│   ├── ant-adaptation-netlogo-code.md
│   ├── artificial-nn-netlogo-code.md
│   ├── boiling-netlogo-code.md
│   ├── continental-divide-netlogo-code.md
│   ├── diffusion-network-netlogo-code.md
│   ├── frogger-netlogo-code.md
│   ├── piaget-vygotsky-netlogo-code.md
│   ├── signaling-game-netlogo-code.md
│   └── archive-initial-case-studies/
├── input-persona/                         # AI agent personas and rules
│   ├── PSN_1_NetLogoSyntaxParser-v5.md
│   ├── PSN_2_NetlogoSemanticsParser-v4.md
│   ├── PSN_3_MessirUCIConceptsMapper-v3.md
│   ├── PSN_4_MessirUCIScenarioWriter-v2.md
│   ├── PSN_5_PlantUMLWriter-v2.md
│   ├── PSN_6_PlantUMLMessirAuditor-v6.md
│   ├── PSN_7_PlantUMLMessirCorrector-v2.md
│   └── messir-uci-compliance-rules-v2.md
├── input-icrash/                          # Reference materials
├── input-images/                          # Supporting images
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
   git clone https://github.com/YOUR_USERNAME/netlogo-to-messir.git
   cd netlogo-to-messir
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API keys:**
   Set your OpenAI API key as an environment variable:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

## 🚀 Usage

### Quick Start: Default Nano Model (Parallel)

Run the orchestrator with a single command using the default nano model, the first case study (3d-solids), medium reasoning effort and medium text verbosity. Steps 01–02 always run in parallel:

```bash
export OPENAI_API_KEY="<YOUR_API_KEY>" && \
python3 /Users/benoit.ries/Library/CloudStorage/OneDrive-UniversityofLuxembourg/cursor-workspace-individual/research.publi.reverse.engineering.netlogo.to.messir.ucid/code-netlogo-to-messir/scripts/run_default_nano.py | cat
```

This will persist outputs under the canonical structure in `code-netlogo-to-messir/output/runs/<YYYY-MM-DD>/<HHMM>/<case>/`.

### Experimentation parameters

- Reasoning: `reasoning: { effort: "minimal" | "low" | "medium" | "high" }` (default: `medium`)
- Text: `text: { verbosity: "low" | "medium" | "high" }` (default: `medium`)

These parameters are supported through:
- Direct programmatic calls: use `orchestrator.update_reasoning_config(effort, summary)` and `orchestrator.update_text_config(verbosity)`
- Terminal interactive flow: select reasoning effort (now including "minimal") and text verbosity when prompted

### OpenAI API Usage

This project uses the OpenAI Responses API for all model inferences. There are no remaining usages of the legacy Chat Completions API.

- Client: `from openai import OpenAI` with `client.responses.create(...)`
- Reference: `https://platform.openai.com/docs/guides/latest-model#migrating-from-chat-completions-to-responses-api`

#### Migration to OpenAI 2.x (Notes)
- The project migrated from legacy Chat Completions to the unified Responses API.
- Redundant polling/extraction code was centralized into `openai_client_utils.py`.
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
from openai_client_utils import create_and_wait, get_output_text

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

## 📂 Output Layout

All artifacts are organized per run, case, and agent step to improve traceability and avoid collisions:

```
code-netlogo-to-messir/
  output/
    runs/
      YYYY-MM-DD/
        HHMM/
          <case-name>/
            01-syntax_parser/
            02-semantics_parser/
            03-messir_mapper/
            04-scenario_writer/
            05-plantuml_writer/
            06-plantuml_messir_auditor/
            07-plantuml_messir_corrector/
            08-plantuml_messir_final_auditor/
          <another-case>/
            ...
```

Each subfolder contains the agent’s files named with the existing prefix format. Orchestrator logs are stored per case under the same run folder.

> Deprecation: The legacy `output/runs-<YYYYMMDD_HHMM>/` structure is no longer used for new runs. Historical runs remain as-is for reference.

### Validation

Layout validated on 2025-09-24 16:58 (timestamp tag `20250924_1658`).
Validation script: `code-netlogo-to-messir/validate_output_layout.py` (simulated structure + checks for all step folders and orchestrator log presence).

Success Criteria rule validation executed on 2025-09-25 09:45 (local time).
Validation script: `code-netlogo-to-messir/validate_task_success_criteria.py` (checks checked criteria have end-of-line timestamps and unchecked ones do not).

### Reference: Messir/UCI Rules Path (Consistency Check)

The canonical Messir/UCI compliance rules file is referenced through the `MESSIR_RULES_FILE` constant in `config.py` and must point to:

`code-netlogo-to-messir/input-persona/DSL_Target_MUCIM-full-definition-for-compliance.md`

Quick verification commands:

```bash
rg -n "MESSIR_RULES_FILE" code-netlogo-to-messir
rg -n "DSL_Target_MUCIM-full-definition-for-compliance.md" .
```

If either command shows mismatches, update the references in Python agents and Markdown docs accordingly.

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
- MESSIR-UCI specification contributors
- PlantUML project for diagram generation capabilities

## 📚 Citation

If you use this work in your research, please cite:

```bibtex
@software{netlogo_to_messir_2025,
  title={NetLogo to MESSIR Multi-Agent Orchestration System},
  author={Ries, Benoit},
  year={2025},
  url={https://github.com/benoitries/netlogo-to-messir}
}
```

---

*This project was vibe-coded with ❤️ using Cursor and Claude-4-Sonnet.*

### Validation — 2025-10-15 00:02 (local time)
- Removed all output token caps and legacy references across orchestrator and agents.
- Ran `validate_task_success_criteria.py` — OK.
- Layout validator points to historical archived runs only; current code paths unaffected.
