# Orchestrator V3-ADK: Design Decisions & Google ADK Integration

## Table of Contents
1. [High-Level Architectural Decisions](#high-level-architectural-decisions)
2. [Detailed Design Decisions](#detailed-design-decisions)
3. [Google ADK API Concepts Used](#google-adk-api-concepts-used)

---

## High-Level Architectural Decisions

### 1. Hybrid ADK Integration Architecture

**Decision**: Use a hybrid approach combining ADK agent structure with manual execution control, rather than full ADK SequentialAgent workflow execution.

**Rationale**:
- **Fine-grained control**: Our file-processing pipeline requires direct control over step arguments (dynamic per step, not conversation-based)
- **Conditional execution**: Steps 5-6 need conditional logic based on audit results, which is easier with manual execution
- **Argument passing**: Steps receive complex, structured arguments (file paths, parsed JSON, etc.) that don't map well to ADK's conversation-based InvocationContext
- **Infrastructure complexity**: Full `SequentialAgent.run_async()` requires `SessionService`, `ArtifactService`, and `InvocationContext` designed for conversational agents, which is overkill for our use case

**Implementation**:
```python
# ADK agents are created for structure, but executed manually
adk_agent = ADKStepAgent(step_adapter, name=f"step_{idx}", ...)
result = await adk_agent.step_adapter.execute(*args)  # Manual execution
```

**Trade-offs**:
- ✅ Full control over execution flow
- ✅ Simplified infrastructure (no SessionService needed)
- ✅ Direct argument passing
- ✅ Conditional logic support
- ❌ Not using full ADK workflow capabilities
- ❌ Manual orchestration code needed

---

### 2. Adapter Pattern for Agent Integration

**Decision**: Use `AgentStepAdapter` to wrap existing agent methods and bridge them with ADK's agent structure.

**Rationale**:
- **Backward compatibility**: Existing agent methods don't need modification
- **Separation of concerns**: Adapter handles workflow concerns (timing, logging, retries) while agents handle domain logic
- **Reusability**: Same adapter pattern can wrap any agent method
- **Maintainability**: Changes to workflow logic don't affect agent implementations

**Structure**:
```
AgentStepAdapter
  ├── Wraps existing agent method
  ├── Handles timing and token tracking
  ├── Manages file I/O operations
  ├── Implements retry logic
  └── Records monitoring metrics
```

---

### 3. Custom ADK Agent Wrapper (ADKStepAgent)

**Decision**: Create `ADKStepAgent` inheriting from ADK's `BaseAgent` to wrap `AgentStepAdapter` instances.

**Rationale**:
- **ADK compatibility**: Allows adapters to be treated as ADK agents
- **Future extensibility**: Can be integrated into full ADK workflows later
- **Type safety**: Inherits from `BaseAgent` for proper typing
- **Pydantic bypass**: Uses `object.__setattr__` to store custom attributes (step_adapter, args) without declaring them as Pydantic fields

**Key Implementation Detail**:
```python
class ADKStepAgent(BaseAgent):
    def __init__(self, step_adapter, ...):
        super().__init__(name=name, description=description)
        # Bypass Pydantic validation for custom attributes
        object.__setattr__(self, 'step_adapter', step_adapter)
        object.__setattr__(self, '_args', None)
```

---

### 4. Strict ADK Requirement (No Fallback)

**Decision**: Require Google ADK to be installed; fail-fast if not available (removed all fallback code).

**Rationale**:
- **Clarity**: Clear requirement makes dependencies explicit
- **Maintenance**: Single code path is easier to maintain
- **ADK features**: Ensures all ADK features (monitoring, retries, tools) are available
- **Error handling**: Clear error messages guide users to install dependencies

**Implementation**:
```python
try:
    from google.adk.agents import BaseAgent
except ImportError as e:
    raise RuntimeError(
        f"Google ADK is required but not available: {e}\n"
        f"Please install it with: pip install \"google-adk>=1.12.0\""
    ) from e
```

---

### 5. Modular Utility Structure

**Decision**: Separate ADK-related utilities into dedicated modules (`utils_adk_*.py`).

**Rationale**:
- **Separation of concerns**: Each module has a single responsibility
- **Maintainability**: Easier to update individual components
- **Testability**: Utilities can be tested independently
- **Reusability**: Utilities can be used by other components

**Modules**:
- `utils_adk_v3_workflow.py`: Workflow adapters and conditional checks
- `utils_adk_tools.py`: Tool integration (GoogleSearch, BigQuery)
- `utils_adk_monitoring.py`: Monitoring and observability
- `utils_adk_retry.py`: Retry mechanisms with exponential backoff

---

### 6. Global Monitoring Instance

**Decision**: Use a singleton global monitor (`get_global_monitor()`) shared across orchestrator instances.

**Rationale**:
- **Shared state**: Metrics accumulate across multiple runs
- **Performance**: Single instance reduces overhead
- **Observability**: Centralized metrics collection

**Implementation**:
```python
_global_monitor = None

def get_global_monitor() -> ADKMonitor:
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = ADKMonitor()
    return _global_monitor
```

---

## Detailed Design Decisions

### 1. Argument Passing via Indexed Lists

**Decision**: Use indexed lists (`step_args_functions`) instead of dictionaries keyed by agent instances.

**Problem**: `ADKStepAgent` instances are Pydantic models and not hashable, so they can't be dictionary keys.

**Solution**:
```python
adk_agents = []
step_args_functions = []  # Index-aligned with adk_agents

for idx, (step_adapter, ...) in enumerate(steps):
    adk_agent = ADKStepAgent(...)
    adk_agents.append(adk_agent)
    step_args_functions.append(lambda captured=static_args: captured)

# During execution
for idx, adk_agent in enumerate(adk_agents):
    args_fn = step_args_functions[idx]
    args = args_fn()
```

**Rationale**: Lists maintain order and alignment, avoiding hashability issues.

---

### 2. Conditional Execution via Callable Functions

**Decision**: Pass conditional check functions (`conditional_check`) to `AgentStepAdapter`.

**Implementation**:
```python
conditional_check = lambda results: condition_check_audit_result(results)

step_adapter = AgentStepAdapter(
    ...,
    conditional_check=conditional_check
)

# In execute():
if self.conditional_check and not self.conditional_check(self.orchestrator.processed_results):
    return None  # Skip step
```

**Rationale**:
- **Flexibility**: Different steps can have different conditions
- **Separation**: Conditional logic is separate from execution logic
- **Testability**: Conditions can be tested independently

---

### 3. Retry Logic Integration in Adapter

**Decision**: Integrate retry logic directly in `AgentStepAdapter.execute()` rather than wrapping the entire adapter.

**Implementation**:
```python
async def execute(self, *args, **kwargs):
    # ...
    result = await execute_with_retry(
        self.method,
        *args,
        retry_config=self.orchestrator.retry_config,
        ...
    )
```

**Rationale**:
- **Transparency**: Retries are part of the adapter's responsibility
- **Error handling**: Consistent retry behavior across all steps
- **Monitoring**: Retry attempts are tracked in monitoring metrics

---

### 4. Timing and Token Tracking Preservation

**Decision**: Maintain exact same timing and token tracking structure as original orchestrator.

**Rationale**:
- **Backward compatibility**: Existing validation tools expect this structure
- **Consistency**: Same metrics format across orchestrator versions
- **Observability**: Historical data comparison is possible

**Structure Preserved**:
```python
self.execution_times = {
    "total_orchestration": 0,
    "lucim_operation_model_generator": 0,
    # ... per-agent timing
}

self.token_usage = {
    "lucim_operation_model_generator": {"used": 0, ...},
    # ... per-agent token usage
}
```

---

### 5. Dynamic Arguments via Lambda Functions

**Decision**: Use lambda functions with captured closures for dynamic arguments.

**Implementation**:
```python
# Dynamic args: depend on previous step results
dynamic_args = lambda: (
    self.processed_results["lucim_scenario_synthesizer"]["data"],
    # ... other dynamic values
)

# Static args: captured at definition time
captured_args = static_args or []
step_args_functions.append(lambda captured=captured_args: captured)
```

**Rationale**:
- **Late evaluation**: Arguments computed at execution time, not definition time
- **Access to results**: Can reference `processed_results` from previous steps
- **Type safety**: Maintains argument structure

**Important**: Use default parameter (`captured=captured_args`) to avoid late binding issues with static args.

---

### 6. Tool Configuration via Utility Functions

**Decision**: Centralize tool configuration in `utils_adk_tools.py` with helper functions.

**Implementation**:
```python
def configure_agent_with_adk_tools(agent_instance, agent_name: str) -> bool:
    tools = get_adk_tools_for_agent(agent_name)
    if hasattr(agent_instance, 'tools'):
        agent_instance.tools.extend(tools)
```

**Rationale**:
- **Centralized logic**: All tool configuration in one place
- **Flexibility**: Easy to add new tools or change tool assignments
- **Agent-agnostic**: Works with any agent instance

---

### 7. Monitoring Metrics Collection

**Decision**: Collect metrics at multiple levels (adapter, orchestrator, global monitor).

**Implementation**:
```python
# In AgentStepAdapter.execute():
self.orchestrator.adk_monitor.record_agent_execution(
    agent_name=self.agent_name,
    duration=duration,
    success=success,
    retry_count=retry_count
)

# In orchestrator:
self.processed_results["adk_metrics"] = self.adk_monitor.get_metrics_summary()
```

**Rationale**:
- **Comprehensive tracking**: Multiple metrics at different levels
- **Integration**: ADK metrics alongside existing timing/token metrics
- **Debugging**: Rich observability for troubleshooting

---

### 8. Error Handling Strategy

**Decision**: Handle errors at adapter level, propagate to orchestrator, and record in monitoring.

**Implementation**:
```python
try:
    result = await execute_with_retry(...)
except Exception as e:
    # Log error
    self.orchestrator.logger.error(...)
    
    # Record in monitoring
    self.orchestrator.adk_monitor.record_error(...)
    
    # Return error result (don't crash pipeline)
    return error_result
```

**Rationale**:
- **Resilience**: Pipeline continues even if one step fails
- **Observability**: All errors are logged and tracked
- **User experience**: Clear error messages in results

---

## Google ADK API Concepts Used

### 1. BaseAgent

**Concept**: Base class for all ADK agents, providing core agent structure and lifecycle.

**Usage in our code**:
```python
from google.adk.agents import BaseAgent

class ADKStepAgent(BaseAgent):
    def __init__(self, step_adapter, name: str, description: str, **kwargs):
        super().__init__(name=name, description=description, **kwargs)
```

**Rationale**:
- **Type compatibility**: Ensures our agents are recognized as ADK agents
- **Structure**: Provides standard agent interface (name, description, etc.)
- **Extensibility**: Can integrate with full ADK workflows in the future

**Example from ADK**:
```python
# ADK's BaseAgent provides:
# - name: str
# - description: str
# - sub_agents: List[BaseAgent]
# - run_async() method signature
```

---

### 2. Pydantic Model Inheritance

**Concept**: ADK agents inherit from Pydantic `BaseModel`, requiring field declaration for all attributes.

**Challenge**: We need to store custom attributes (`step_adapter`, `_args`) that aren't part of ADK's model.

**Solution**:
```python
class ADKStepAgent(BaseAgent):
    def __init__(self, step_adapter, ...):
        super().__init__(name=name, description=description)
        # Bypass Pydantic validation using object.__setattr__
        object.__setattr__(self, 'step_adapter', step_adapter)
        object.__setattr__(self, '_args', None)
    
    async def _run_async_impl(self, ctx):
        # Access using getattr for safety
        step_adapter = getattr(self, 'step_adapter', None)
```

**Rationale**:
- **Pydantic restriction**: BaseAgent doesn't allow arbitrary fields by default
- **Workaround**: `object.__setattr__` bypasses validation
- **Safety**: Use `getattr` when accessing to handle missing attributes gracefully

**Why not use `model_config = ConfigDict(extra='allow')`?**
- Would require modifying BaseAgent's configuration, which we can't do
- Using `object.__setattr__` is the standard Python way to add attributes to objects with restricted `__setattr__`

---

### 3. Tool Integration Pattern

**Concept**: ADK agents can have tools attached to them for extended capabilities.

**Usage in our code**:
```python
from utils_adk_tools import configure_agent_with_adk_tools

# In orchestrator initialization
configure_agent_with_adk_tools(
    self.lucim_operation_model_generator_agent,
    "lucim_operation_model_generator"
)
```

**Tools integrated**:
- **GoogleSearchTool**: For LUCIM Environment Synthesizer to enhance context understanding
- **BigQueryToolset**: Helper available for analytics (optional)

**Rationale**:
- **Enhanced capabilities**: Tools provide additional functionality (search, data access)
- **Agent-specific**: Different agents can have different tools
- **Extensibility**: Easy to add more tools as needed

**ADK Pattern**:
```python
# ADK agents support tools via:
agent.tools = [tool1, tool2, ...]
# or
agent.tools.append(tool)
```

---

### 4. Async Execution Pattern

**Concept**: ADK agents use async methods (`run_async`, `_run_async_impl`) for non-blocking execution.

**Usage in our code**:
```python
class ADKStepAgent(BaseAgent):
    async def _run_async_impl(self, ctx) -> Any:
        # Execute adapter asynchronously
        result = await self.step_adapter.execute(*args, **kwargs)
        return result
```

**Rationale**:
- **ADK requirement**: BaseAgent's `_run_async_impl` is async
- **Compatibility**: Our adapter's `execute()` is async
- **Non-blocking**: Allows concurrent execution potential in future

**ADK Pattern**:
```python
# ADK's async execution pattern:
async def _run_async_impl(self, ctx: InvocationContext):
    # Agent logic here
    yield Event(...)
```

---

### 5. Sequential Workflow Concept (Structure Only)

**Concept**: ADK's `SequentialAgent` executes sub-agents in sequence.

**Our usage**: We don't use `SequentialAgent.run_async()` directly, but we structure our agents similarly.

**Why not use SequentialAgent directly?**:
```python
# Would require:
invocation_context = InvocationContext(
    session_service=SessionService(...),  # Complex setup
    artifact_service=ArtifactService(...),
    session=Session(...),
    agent=root_agent,
    ...
)

# Our simpler approach:
for adk_agent in adk_agents:
    result = await adk_agent.step_adapter.execute(*args)
```

**Rationale**:
- **Complexity**: InvocationContext requires session/artifact services
- **Overhead**: Conversation-based infrastructure for file processing is excessive
- **Control**: Manual execution gives us direct control over arguments and flow

**What we gain from SequentialAgent concept**:
- **Structure**: Our agents follow sequential execution pattern
- **Future-ready**: Can migrate to full SequentialAgent later if needed
- **ADK compatibility**: Agents are structured as ADK agents

---

### 6. Monitoring and Observability Concept

**Concept**: ADK provides observability features for tracking agent execution.

**Our implementation**: Custom `ADKMonitor` class inspired by ADK's observability patterns.

**Usage**:
```python
from utils_adk_monitoring import get_global_monitor

self.adk_monitor = get_global_monitor()
self.adk_monitor.start_monitoring()
self.adk_monitor.record_agent_execution(...)
self.adk_monitor.stop_monitoring()
```

**Metrics tracked**:
- Agent execution counts
- Success/failure rates
- Execution durations
- Retry counts
- Error categorization

**Rationale**:
- **ADK-inspired**: Follows ADK's observability patterns
- **Custom implementation**: Tailored to our pipeline's needs
- **Integration**: Complements existing timing/token tracking

---

### 7. Retry Mechanism Pattern

**Concept**: ADK provides retry capabilities for resilient agent execution.

**Our implementation**: Custom retry logic with exponential backoff, inspired by ADK patterns.

**Usage**:
```python
from utils_adk_retry import execute_with_retry, RetryConfig

result = await execute_with_retry(
    self.method,
    *args,
    max_retries=self.retry_config.max_retries,
    backoff_factor=self.retry_config.backoff_factor,
    initial_delay=self.retry_config.initial_delay,
    max_delay=self.retry_config.max_delay,
)
```

**Features**:
- Exponential backoff (1s → 1.5s → 2.25s → ...)
- Configurable retry counts
- Exception filtering
- Retry callback support
- Async/sync support

**Rationale**:
- **Resilience**: Network/API calls can fail transiently
- **ADK-inspired**: Follows ADK's retry patterns
- **Configurable**: Different retry strategies per agent if needed

---

### 8. Tool Ecosystem Integration

**Concept**: ADK provides a tool ecosystem (GoogleSearch, BigQuery, etc.) for agent capabilities.

**Tools used**:

#### GoogleSearchTool
```python
from google.adk.tools import google_search

# In utils_adk_tools.py:
def get_google_search_tool():
    return google_search  # ADK's built-in search tool

# Configured for LUCIM Environment Synthesizer
if agent_name == "lucim_operation_model_generator":
    tools.append(get_google_search_tool())
```

**Rationale**:
- **Context enhancement**: Search provides additional context for synthesis
- **ADK native**: Uses ADK's built-in tool
- **Agent-specific**: Only added to agents that benefit from it

#### BigQueryToolset (Optional)
```python
from google.adk.tools.bigquery import BigQueryToolset

def get_bigquery_toolset(project_id=None, dataset_id=None, location=None):
    return BigQueryToolset(project_id=project_id, ...)
```

**Rationale**:
- **Analytics**: Can be used for data analysis in future
- **Optional**: Not currently enabled, but infrastructure ready
- **Extensibility**: Easy to add when needed

---

### 9. Import Structure and Dependency Management

**Concept**: ADK uses structured imports with clear separation of concerns.

**Our imports**:
```python
# Core ADK
from google.adk.agents import BaseAgent

# Tools (conditionally imported)
try:
    from google.adk.tools import google_search
    ADK_TOOLS_AVAILABLE = True
except ImportError:
    ADK_TOOLS_AVAILABLE = False

try:
    from google.adk.tools.bigquery import BigQueryToolset
    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
```

**Rationale**:
- **Graceful degradation**: Optional tools don't break if unavailable
- **Clear dependencies**: Explicit about what's required vs optional
- **Error handling**: Fail-fast for required components (BaseAgent)

---

### 10. Type Hints and Pydantic Validation

**Concept**: ADK uses Pydantic for type validation and type hints throughout.

**Our usage**:
```python
from typing import Dict, Any, Optional, List

class ADKStepAgent(BaseAgent):
    def set_args(self, *args, **kwargs):
        object.__setattr__(self, '_args', args)
        object.__setattr__(self, '_kwargs', kwargs)
    
    async def _run_async_impl(self, ctx) -> Any:
        # Type hints for clarity
        result = await self.step_adapter.execute(*args, **kwargs)
        return result
```

**Rationale**:
- **Type safety**: Catches errors at development time
- **Documentation**: Type hints serve as inline documentation
- **ADK compatibility**: Aligns with ADK's typing patterns

---

## Summary: Key Takeaways

### Architectural Patterns
1. **Hybrid ADK Integration**: ADK structure + manual execution
2. **Adapter Pattern**: Bridge existing code with ADK
3. **Modular Utilities**: Separated concerns across modules
4. **Global Monitoring**: Singleton for metrics collection

### ADK Concepts Used
1. **BaseAgent**: Core agent structure
2. **Pydantic Inheritance**: Type-safe models (with workarounds)
3. **Tool Integration**: GoogleSearch, BigQuery helpers
4. **Async Execution**: Non-blocking agent execution
5. **Monitoring Patterns**: ADK-inspired observability
6. **Retry Patterns**: Resilient execution with backoff

### Design Principles
- **Backward Compatibility**: Same output structure and interfaces
- **Fail-Fast**: Clear errors when ADK unavailable
- **Extensibility**: Easy to add tools, agents, or features
- **Observability**: Comprehensive monitoring and logging
- **Resilience**: Retry logic and error handling

---

## Policy: No LLM Correctors for Operation/Scenario

Decision: Do not introduce LLM-based corrector agents for Operation Model or Scenarios.

Rationale:
- Corrections for these stages should be handled via deterministic validators/tools or manual iteration to avoid duplicated responsibilities and agent proliferation.

Implications:
- Do not create files/classes: `agent_lucim_operation_corrector.py`, `NetLogoLUCIMOperationCorrectorAgent`, `agent_lucim_scenario_corrector.py`, `NetLogoLUCIMScenarioCorrectorAgent`.
- Orchestrator flows may include audits for these stages but skip LLM correction steps.

---

## References

- Google ADK Documentation: https://google.github.io/adk-docs
- ADK Python Examples: https://github.com/google/adk-python
- Original Orchestrator: `orchestrator_persona_v3.py`
- Integration Documentation: `docs/ORCHESTRATOR_ADK_INTEGRATION.md`

