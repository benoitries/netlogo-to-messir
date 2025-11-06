# Orchestrator Persona V3 ADK Integration

## Overview

This document describes the Google ADK integration for the Persona V3 orchestrator. The ADK-integrated orchestrator (`orchestrator_persona_v3_adk.py`) provides enhanced workflow orchestration using Google ADK's SequentialAgent and tool ecosystem while maintaining full backward compatibility with the existing implementation.

## Architecture

### Components

1. **`orchestrator_persona_v3_adk.py`** - Main orchestrator with ADK integration
2. **`utils_adk_v3_workflow.py`** - Workflow utilities and adapters
3. **`utils_adk_tools.py`** - ADK tools integration utilities

### Key Classes

- **`NetLogoOrchestratorPersonaV3ADK`** - Main orchestrator class
- **`AgentStepAdapter`** - Adapter wrapping agent methods for workflow execution
- **`ADKStepAgent`** - Custom ADK agent that wraps AgentStepAdapter

## Features

### 1. ADK Sequential Workflow

The orchestrator uses ADK's `SequentialAgent` to orchestrate the 6-stage pipeline:
1. LUCIM Environment Synthesizer
2. LUCIM Scenario Synthesizer
3. PlantUML Writer
4. PlantUML LUCIM Auditor
5. PlantUML LUCIM Corrector (conditional)
6. PlantUML LUCIM Final Auditor (conditional)

### 2. Tool Integration

- **GoogleSearchTool**: Integrated with LUCIM Environment Synthesizer for enhanced context understanding
- **BigQueryToolset**: Helper functions available for analytics integration (optional, see `utils_adk_tools.py`)
- Extensible architecture for adding more tools as needed

### 3. Retry Mechanisms

- **Automatic Retries**: Built-in retry logic with exponential backoff for all agent executions
- **Configurable**: Customizable retry counts, backoff factors, and delay limits
- **Error Tracking**: Retry attempts are tracked and logged for observability
- **Exception Handling**: Smart exception classification and retryable error detection

### 4. Monitoring and Observability

- **Performance Metrics**: Tracks execution times, success rates, and durations for each agent
- **Error Tracking**: Comprehensive error counting and categorization
- **Retry Statistics**: Monitors retry patterns and success after retries
- **Summary Reports**: Automatic generation of monitoring summaries at end of pipeline

### 5. Execution Architecture

The orchestrator uses a hybrid approach:
- **ADK Agents**: Uses `ADKStepAgent` (inheriting from ADK's `BaseAgent`) for each pipeline step
- **Manual Execution**: Executes agents manually via `AgentStepAdapter` for fine-grained control over arguments, conditional logic, and error handling
- **Why not full SequentialAgent.run_async()?**: Using `SequentialAgent.run_async()` directly requires creating a full `InvocationContext` with `SessionService`, `ArtifactService`, and other infrastructure components that are designed for conversational/chat-based agents. Our file-processing pipeline needs direct control over step arguments and conditional execution, making manual execution more appropriate while still leveraging ADK's agent structure and monitoring capabilities.

### 6. Backward Compatibility

- Maintains exact same output structure
- All timing and token tracking preserved
- Same logging and error handling
- Compatible with existing validation tools

## Usage

### Basic Usage

```python
from orchestrator_persona_v3_adk import NetLogoOrchestratorPersonaV3ADK
from utils_orchestrator_v3_agent_config import update_agent_configs

# Create orchestrator (ADK enabled by default if available)
orchestrator = NetLogoOrchestratorPersonaV3ADK(model_name="gpt-5-mini")

# Configure reasoning and verbosity
update_agent_configs(orchestrator, reasoning_effort="high", reasoning_summary="auto", text_verbosity="medium")

# Run pipeline
results = await orchestrator.run("base_name")
```

### Disable ADK

```python
# Force custom execution (no ADK)
orchestrator = NetLogoOrchestratorPersonaV3ADK(
    model_name="gpt-5-mini", 
    use_adk=False
)
```

## Testing

Run the test script to verify the orchestrator:

```bash
python3 test_orchestrator_persona_v3_adk.py
```

**Note**: Full functionality requires:
- All Python dependencies installed (tiktoken, openai, etc.)
- Google ADK installed (`pip install google-adk`)
- Valid OpenAI API key
- All persona files in place

## Current Status

### ✅ Completed

- [x] Modular workflow structure with `AgentStepAdapter`
- [x] ADK SequentialAgent integration (structure ready)
- [x] Conditional step execution (steps 5-6)
- [x] GoogleSearchTool integration
- [x] Retry mechanisms with exponential backoff
- [x] Monitoring and observability features
- [x] Fallback to custom execution
- [x] Full backward compatibility
- [x] Test script created
- [x] Documentation created

### 🔄 In Progress / TODO

- [ ] Full ADK SequentialAgent execution with InvocationContext (structure ready, requires runtime testing)
- [ ] BigQueryToolset integration (optional, for analytics)
- [ ] Performance comparison with original orchestrator
- [ ] Production deployment and testing

## Differences from Original Orchestrator

### Structure Improvements

1. **Modular Steps**: Each pipeline step is wrapped in `AgentStepAdapter` for better separation of concerns
2. **ADK Integration**: Ready for ADK SequentialAgent workflow orchestration
3. **Tool Support**: Built-in support for ADK tools
4. **Cleaner Code**: Reduced code complexity through adapter pattern

### Backward Compatibility

- **Same Output Structure**: All output files in same locations with same formats
- **Same Interfaces**: All public methods have same signatures
- **Same Configuration**: Uses same config system and persona paths
- **Same Logging**: Compatible with existing logging infrastructure

## Migration Notes

The ADK orchestrator can be used as a drop-in replacement for `orchestrator_persona_v3.py`:

```python
# Before
from orchestrator_persona_v3 import NetLogoOrchestratorPersonaV3

# After
from orchestrator_persona_v3_adk import NetLogoOrchestratorPersonaV3ADK as NetLogoOrchestratorPersonaV3
```

All existing code should work without modification.

## Future Enhancements

1. **Full ADK Workflow Execution**: Complete integration with ADK's InvocationContext
2. **Parallel Execution**: Use ADK ParallelAgent for independent steps
3. **Advanced Tools**: Integrate more ADK tools (BigQuery, computer use tools)
4. **Monitoring**: ADK observability and performance metrics
5. **Retry Mechanisms**: Leverage ADK's built-in retry and error recovery

## Troubleshooting

### ADK Not Available

If you see the warning "Google ADK not available", the orchestrator will automatically use custom sequential execution. This is expected behavior and does not affect functionality.

### Tool Integration Issues

If tools fail to initialize, check:
1. ADK is properly installed: `pip install google-adk`
2. Required credentials are configured (for Google Search, etc.)
3. Tool-specific dependencies are installed

## References

- [Google ADK Documentation](https://google.github.io/adk-docs)
- [ADK Python Examples](https://github.com/google/adk-python)
- Original orchestrator: `orchestrator_persona_v3.py`

