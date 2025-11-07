#!/usr/bin/env python3
"""
Orchestrator V3 Agent Configuration Utility
Manages agent configuration updates (reasoning, verbosity, etc.).
"""

from typing import Dict, Any, Optional
try:
    # Late import to avoid circulars at module import time
    import utils_config_constants as _cfg
except Exception:  # pragma: no cover
    _cfg = None  # Fallback when imported by linters/tests


def update_agent_configs(orchestrator_instance,
                        reasoning_effort: Optional[str] = None,
                        reasoning_summary: Optional[str] = None,
                        text_verbosity: Optional[str] = None):
    """
    Update configuration for all agents.
    
    Args:
        orchestrator_instance: Orchestrator instance
        reasoning_effort: Reasoning effort level (low/medium/high)
        reasoning_summary: Reasoning summary mode (auto/manual)
        text_verbosity: Text verbosity level (low/medium/high)
    """
    # 0) Ensure global AGENT_CONFIGS uses the orchestrator-selected model
    #    This is required because agents call get_reasoning_config(), which reads
    #    from the module-level AGENT_CONFIGS in utils_config_constants.
    if _cfg is not None and hasattr(orchestrator_instance, "model") and orchestrator_instance.model:
        try:
            for agent_name in _cfg.AGENT_CONFIGS.keys():
                _cfg.AGENT_CONFIGS[agent_name]["model"] = orchestrator_instance.model
        except Exception:
            # Non-fatal: continue with local updates even if global sync fails
            pass

    # 1) Update orchestrator-local agent_configs dictionary
    for agent_name in orchestrator_instance.agent_configs:
        if reasoning_effort is not None:
            orchestrator_instance.agent_configs[agent_name]["reasoning_effort"] = reasoning_effort
        if reasoning_summary is not None:
            orchestrator_instance.agent_configs[agent_name]["reasoning_summary"] = reasoning_summary
        if text_verbosity is not None:
            orchestrator_instance.agent_configs[agent_name]["text_verbosity"] = text_verbosity
    
    # 1.5) Set orchestrator-level attributes for direct access
    if reasoning_effort is not None:
        orchestrator_instance.reasoning_effort = reasoning_effort
    elif not hasattr(orchestrator_instance, "reasoning_effort"):
        # Initialize with default from agent_configs if not set
        orchestrator_instance.reasoning_effort = orchestrator_instance.agent_configs.get(
            "lucim_operation_model_generator", {}
        ).get("reasoning_effort", "medium")
    
    if reasoning_summary is not None:
        orchestrator_instance.reasoning_summary = reasoning_summary
    elif not hasattr(orchestrator_instance, "reasoning_summary"):
        # Initialize with default from agent_configs if not set
        orchestrator_instance.reasoning_summary = orchestrator_instance.agent_configs.get(
            "lucim_operation_model_generator", {}
        ).get("reasoning_summary", "auto")
    
    if text_verbosity is not None:
        orchestrator_instance.text_verbosity = text_verbosity
    elif not hasattr(orchestrator_instance, "text_verbosity"):
        # Initialize with default from agent_configs if not set
        orchestrator_instance.text_verbosity = orchestrator_instance.agent_configs.get(
            "lucim_operation_model_generator", {}
        ).get("text_verbosity", "medium")
    
    agent_list = [
        ("lucim_operation_model_generator_agent", True),
        ("lucim_scenario_generator_agent", True),
        ("lucim_plantuml_diagram_generator_agent", True),
        ("lucim_plantuml_diagram_auditor_agent", True),
    ]
    
    # 2) Push updates down to live agent instances
    for agent_attr, supports_text in agent_list:
        agent = getattr(orchestrator_instance, agent_attr, None)
        if agent is not None:
            bundle = {}
            # Always keep agent.model aligned with orchestrator.model if possible
            try:
                if hasattr(agent, "update_model") and hasattr(orchestrator_instance, "model") and orchestrator_instance.model:
                    agent.update_model(orchestrator_instance.model)
                elif hasattr(agent, "model") and hasattr(orchestrator_instance, "model") and orchestrator_instance.model:
                    agent.model = orchestrator_instance.model  # best-effort alignment
            except Exception:
                pass
            if reasoning_effort is not None:
                bundle["reasoning_effort"] = reasoning_effort
            if reasoning_summary is not None:
                bundle["reasoning_summary"] = reasoning_summary
            if text_verbosity is not None:
                bundle["text_verbosity"] = text_verbosity
            
            if hasattr(agent, "apply_config") and bundle:
                try:
                    agent.apply_config(bundle)
                    continue
                except Exception as e:
                    if hasattr(orchestrator_instance, 'orchestrator_logger') and orchestrator_instance.orchestrator_logger:
                        orchestrator_instance.orchestrator_logger.log_config_warning(
                            f"apply_config failed on {agent_attr}: {e}"
                        )
            
            if reasoning_effort is not None and reasoning_summary is not None and hasattr(agent, "update_reasoning_config"):
                agent.update_reasoning_config(reasoning_effort, reasoning_summary)
            if text_verbosity is not None and hasattr(agent, "update_text_config"):
                agent.update_text_config(text_verbosity)

