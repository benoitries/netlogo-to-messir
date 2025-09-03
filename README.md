# NetLogo to MESSIR Multi-Agent Orchestration System

A sophisticated multi-agent AI system that automatically converts NetLogo agent-based models into MESSIR (Multi-Entity System Specification in Relational) diagrams through an orchestrated pipeline of specialized AI agents.

## 🚀 Overview

This project implements an 8-step orchestration pipeline that transforms NetLogo simulation models into standardized MESSIR PlantUML diagrams. The system uses multiple specialized AI agents working in sequence to parse, analyze, map, and generate compliant MESSIR representations.

### Key Features

- **Multi-Agent Architecture**: 7 specialized AI agents handling different aspects of the conversion
- **Automated Orchestration**: Sequential pipeline with error correction and compliance auditing
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
│   ├── PSN_1_NetLogoSyntaxParser-v4.md
│   ├── PSN_2_NetlogoSemanticsParser-v3.md
│   ├── PSN_3_MessirUCIConceptsMapper-v3.md
│   ├── PSN_4_MessirUCIScenarioWriter-v2.md
│   ├── PSN_5_PlantUMLWriter-v2.md
│   ├── PSN_6_PlantUMLMessirAuditor-v6.md
│   ├── PSN_7_PlantUMLMessirCorrector-v2.md
│   └── messir-uci-compliance-rules-v2.md
├── input-icrash/                          # Reference materials
├── input-images/                          # Supporting images
└── output/                                # Generated results
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

### Basic Usage

Run the orchestrator on a specific NetLogo case study:

```python
from netlogo_orchestrator import NetLogoOrchestrator

# Initialize orchestrator
orchestrator = NetLogoOrchestrator()

# Process a case study
result = orchestrator.process_case_study(
    case_study_name="3d-solids",
    ai_model="gpt-5-nano",
    reasoning_level="low"
)
```

### Available Models

- `gpt-5` - Highest quality, highest cost
- `gpt-5-mini` - Balanced quality/cost
- `gpt-5-nano` - Most cost-effective

### Reasoning Levels

- `low` - Basic reasoning (recommended)
- `medium` - Enhanced reasoning
- `high` - Maximum reasoning depth

## 📊 Performance Metrics

The system tracks comprehensive metrics:

- **Cost Analysis**: Token usage and pricing
- **Execution Time**: Per-step and total duration
- **Compliance Rate**: MESSIR rule adherence
- **Success Rate**: Pipeline completion rate

### Cost Comparison (per conversion)

| Model | Input Cost | Output Cost | Total Cost |
|-------|------------|-------------|------------|
| gpt-5 | $1.25/1M tokens | $10.00/1M tokens | $0.189-$0.201 |
| gpt-5-mini | $0.25/1M tokens | $2.00/1M tokens | $0.036-$0.039 |
| gpt-5-nano | $0.05/1M tokens | $0.40/1M tokens | $0.007-$0.009 |

## 📈 Experimental Results

Based on comprehensive testing across 10 NetLogo case studies:

- **100% Success Rate** - All orchestrations completed successfully
- **100% Compliance** - All final diagrams achieved MESSIR compliance
- **22-27x Cost Reduction** - Using gpt-5-nano vs gpt-5
- **Consistent Performance** - Stable across different model sizes

## 🔧 Configuration

Key configuration options in `config.py`:

```python
# Available AI models
AVAILABLE_MODELS = ["gpt-5", "gpt-5-mini", "gpt-5-nano"]

# Reasoning levels
REASONING_LEVELS = ["low", "medium", "high"]

# File patterns
NETLOGO_CODE_PATTERN = "*-netlogo-code.md"
NETLOGO_INTERFACE_PATTERN = "*-netlogo-interface-*.png"
```

## 📝 Case Studies

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
