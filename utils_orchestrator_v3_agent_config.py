#!/usr/bin/env python3
"""
Orchestrator V3 Agent Configuration Utility
Manages agent configuration updates (reasoning, verbosity, etc.).
"""

from typing import Dict, Any, Optional


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
    # Update agent_configs dictionary
    for agent_name in orchestrator_instance.agent_configs:
        if reasoning_effort is not None:
            orchestrator_instance.agent_configs[agent_name]["reasoning_effort"] = reasoning_effort
        if reasoning_summary is not None:
            orchestrator_instance.agent_configs[agent_name]["reasoning_summary"] = reasoning_summary
        if text_verbosity is not None:
            orchestrator_instance.agent_configs[agent_name]["text_verbosity"] = text_verbosity
    
    agent_list = [
        ("lucim_operation_synthesizer_agent", True),
        ("lucim_scenario_synthesizer_agent", True),
        ("plantuml_writer_agent", True),
        ("plantuml_lucim_auditor_agent", True),
        ("plantuml_lucim_corrector_agent", True),
        ("plantuml_lucim_final_auditor_agent", True),
    ]
    
    for agent_attr, supports_text in agent_list:
        agent = getattr(orchestrator_instance, agent_attr, None)
        if agent is not None:
            bundle = {}
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

