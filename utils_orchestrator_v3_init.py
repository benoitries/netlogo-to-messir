#!/usr/bin/env python3
"""
Orchestrator V3 Initialization Utility
Initializes orchestrator components (agents, monitoring, tools, etc.).
"""

import datetime
from typing import Dict

from agent_lucim_operation_generator import LucimOperationModelGeneratorAgent
from agent_lucim_scenario_generator import LUCIMScenarioGeneratorAgent
from agent_lucim_plantuml_diagram_generator import LUCIMPlantUMLDiagramGeneratorAgent
from agent_lucim_plantuml_diagram_auditor import LUCIMPlantUMLDiagramAuditorAgent
from utils_config_constants import AGENT_CONFIGS, DEFAULT_PERSONA_SET
from utils_adk_tools import configure_agent_with_adk_tools
from utils_adk_retry import RetryConfig, DEFAULT_MAX_RETRIES
from utils_orchestrator_v3_persona_config import initialize_v3_persona_set


def initialize_v3_orchestrator_components(orchestrator_instance, model_name: str):
    """
    Initialize all orchestrator components (agents, configs, monitoring).
    
    Args:
        orchestrator_instance: Orchestrator instance to initialize
        model_name: AI model name
    """
    orchestrator_instance.model = model_name
    orchestrator_instance.persona_set = DEFAULT_PERSONA_SET
    orchestrator_instance.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    orchestrator_instance.selected_persona_set = DEFAULT_PERSONA_SET
    orchestrator_instance.agent_configs = AGENT_CONFIGS.copy()
    orchestrator_instance.processed_results = {}
    
    # Initialize reasoning and verbosity attributes with defaults from agent_configs
    orchestrator_instance.reasoning_effort = orchestrator_instance.agent_configs.get(
        "lucim_operation_model_generator", {}
    ).get("reasoning_effort", "medium")
    orchestrator_instance.reasoning_summary = orchestrator_instance.agent_configs.get(
        "lucim_operation_model_generator", {}
    ).get("reasoning_summary", "auto")
    orchestrator_instance.text_verbosity = orchestrator_instance.agent_configs.get(
        "lucim_operation_model_generator", {}
    ).get("text_verbosity", "medium")
    
    # Initialize agents
    orchestrator_instance.lucim_operation_model_generator_agent = LucimOperationModelGeneratorAgent(model_name, orchestrator_instance.timestamp)
    orchestrator_instance.lucim_scenario_generator_agent = LUCIMScenarioGeneratorAgent(model_name, orchestrator_instance.timestamp)
    orchestrator_instance.lucim_plantuml_diagram_generator_agent = LUCIMPlantUMLDiagramGeneratorAgent(model_name, orchestrator_instance.timestamp)
    orchestrator_instance.lucim_plantuml_diagram_auditor_agent = LUCIMPlantUMLDiagramAuditorAgent(model_name, orchestrator_instance.timestamp)

    # Initialize persona set
    initialize_v3_persona_set(orchestrator_instance)
    
    # Initialize retry configuration
    orchestrator_instance.retry_config = RetryConfig(
        max_retries=DEFAULT_MAX_RETRIES,
        backoff_factor=1.5,
        initial_delay=1.0,
        max_delay=60.0
    )
    
    # Initialize timing and token tracking structures
    orchestrator_instance.execution_times = {
        "total_orchestration": 0,
        "lucim_operation_model_generator": 0,
        "lucim_scenario_generator": 0,
        "lucim_plantuml_diagram_generator": 0,
        "lucim_plantuml_diagram_auditor": 0
    }
    
    orchestrator_instance.token_usage = {
        "lucim_operation_model_generator": {"used": 0},
        "lucim_scenario_generator": {"used": 0},
        "lucim_plantuml_diagram_generator": {"used": 0},
        "lucim_plantuml_diagram_auditor": {"used": 0}
    }
    
    orchestrator_instance.detailed_timing = {
        "lucim_operation_model_generator": {"start": 0, "end": 0, "duration": 0},
        "lucim_scenario_generator": {"start": 0, "end": 0, "duration": 0},
        "lucim_plantuml_diagram_generator": {"start": 0, "end": 0, "duration": 0},
        "lucim_plantuml_diagram_auditor": {"start": 0, "end": 0, "duration": 0}
    }
    
    # Configure ADK tools (after logger is set)
    if hasattr(orchestrator_instance, 'logger') and orchestrator_instance.logger:
        orchestrator_instance.logger.info("[ADK] Initializing Google ADK integration")
        orchestrator_instance.logger.info("[ADK] Using BaseAgent from google.adk.agents")
        orchestrator_instance.logger.info(
            f"[ADK] Retry configuration: max_retries={orchestrator_instance.retry_config.max_retries}, "
            f"backoff_factor={orchestrator_instance.retry_config.backoff_factor}, "
            f"initial_delay={orchestrator_instance.retry_config.initial_delay}s, "
            f"max_delay={orchestrator_instance.retry_config.max_delay}s"
        )
        orchestrator_instance.logger.info("[ADK] Configuring agents with ADK tools...")
    
    tool_added = configure_agent_with_adk_tools(
        orchestrator_instance.lucim_operation_model_generator_agent,
        "lucim_operation_model_generator"
    )
    
    if hasattr(orchestrator_instance, 'logger') and orchestrator_instance.logger:
        if tool_added:
            orchestrator_instance.logger.info("[ADK] GoogleSearchTool successfully configured for lucim_operation_model_generator")
        else:
            orchestrator_instance.logger.info("[ADK] No ADK tools configured for lucim_operation_model_generator (tool not available or not needed)")

