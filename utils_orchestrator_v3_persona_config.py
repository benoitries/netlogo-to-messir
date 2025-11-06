#!/usr/bin/env python3
"""
Orchestrator V3 Persona Configuration Utility
Manages persona set initialization and path configuration for V3 orchestrator.
"""

import pathlib
from typing import Dict, Any
from utils_config_constants import INPUT_PERSONA_DIR
from utils_config_constants import (
    RULES_LUCIM_OPERATION_MODEL,
    RULES_LUCIM_SCENARIO,
    RULES_LUCIM_PLANTUML_DIAGRAM,
    RULES_MAPPING_NETLOGO_TO_OPERATION_MODEL,
)


from utils_config_constants import DEFAULT_PERSONA_SET

def initialize_v3_persona_set(orchestrator_instance, persona_set: str = DEFAULT_PERSONA_SET) -> str:
    """
    Initialize persona set for v3 orchestrator.
    
    Args:
        orchestrator_instance: Orchestrator instance to configure
        persona_set: Persona set name (default: DEFAULT_PERSONA_SET)
        
    Returns:
        Selected persona set name
    """
    orchestrator_instance.selected_persona_set = persona_set
    update_agent_persona_paths(orchestrator_instance)
    
    if hasattr(orchestrator_instance, 'logger') and orchestrator_instance.logger:
        orchestrator_instance.logger.info(f"✅ Initialized persona set: {persona_set}")
    else:
        print(f"✅ Initialized persona set: {persona_set}")
    
    return persona_set


def update_agent_persona_paths(orchestrator_instance):
    """Update persona file paths for all agents based on DEFAULT_PERSONA_SET."""
    persona_dir = INPUT_PERSONA_DIR / orchestrator_instance.selected_persona_set
    
    v3_persona_paths = {
        "lucim_operation_model_generator": persona_dir / "PSN_LUCIM_Operation_Model_Generator.md",
        "lucim_operation_model_auditor": persona_dir / "PSN_LUCIM_Operation_Model_Auditor.md",
        "lucim_scenario_generator": persona_dir / "PSN_LUCIM_Scenario_Generator.md",
        "lucim_scenario_auditor": persona_dir / "PSN_LUCIM_Scenario_Auditor.md",
        "lucim_plantuml_diagram_generator": persona_dir / "PSN_LUCIM_PlantUML_Diagram_Generator.md",
        "lucim_plantuml_diagram_auditor": persona_dir / "PSN_LUCIM_PlantUML_Diagram_Auditor.md",
        # Centralized rule/mapping constants
        "mapping_netlogo_to_lucim_operation_model": RULES_MAPPING_NETLOGO_TO_OPERATION_MODEL,
        "rules_operation_model": RULES_LUCIM_OPERATION_MODEL,
        "rules_scenario": RULES_LUCIM_SCENARIO,
        "rules_plantuml": RULES_LUCIM_PLANTUML_DIAGRAM,
    }
    
    orchestrator_instance.netlogo_lucim_mapping_path = v3_persona_paths["mapping_netlogo_to_lucim_operation_model"]
    
    # Update persona paths for agents that exist on the orchestrator instance
    agent_name_to_path_key = [
        ("lucim_operation_model_generator_agent", "lucim_operation_model_generator"),
        ("lucim_operation_model_auditor_agent", "lucim_operation_model_auditor"),
        ("lucim_scenario_generator_agent", "lucim_scenario_generator"),
        ("lucim_scenario_auditor_agent", "lucim_scenario_auditor"),
        ("lucim_plantuml_diagram_generator_agent", "lucim_plantuml_diagram_generator"),
        ("lucim_plantuml_diagram_auditor_agent", "lucim_plantuml_diagram_auditor"),
    ]

    for agent_attr, path_key in agent_name_to_path_key:
        agent = getattr(orchestrator_instance, agent_attr, None)
        if agent is not None and hasattr(agent, 'update_persona_path'):
            agent.update_persona_path(str(v3_persona_paths[path_key]))

    # Update rule file paths per agent when supported
    rules_by_agent = {
        "lucim_operation_model_generator_agent": v3_persona_paths.get("rules_operation_model"),
        "lucim_operation_model_auditor_agent": v3_persona_paths.get("rules_operation_model"),
        "lucim_scenario_generator_agent": v3_persona_paths.get("rules_scenario"),
        "lucim_scenario_auditor_agent": v3_persona_paths.get("rules_scenario"),
        "lucim_plantuml_diagram_generator_agent": v3_persona_paths.get("rules_plantuml"),
        "lucim_plantuml_diagram_auditor_agent": v3_persona_paths.get("rules_plantuml"),
    }
    for agent_attr, rules_path in rules_by_agent.items():
        agent = getattr(orchestrator_instance, agent_attr, None)
        if rules_path is not None and agent is not None and hasattr(agent, 'update_lucim_rules_path'):
            agent.update_lucim_rules_path(str(rules_path))


def load_netlogo_lucim_mapping(orchestrator_instance) -> str:
    """Load NetLogo to LUCIM mapping file content."""
    if not hasattr(orchestrator_instance, 'netlogo_lucim_mapping_path'):
        # Use centralized constant for mapping
        orchestrator_instance.netlogo_lucim_mapping_path = RULES_MAPPING_NETLOGO_TO_OPERATION_MODEL
    
    if not orchestrator_instance.netlogo_lucim_mapping_path.exists():
        raise FileNotFoundError(
            f"MANDATORY INPUT MISSING: NetLogo to LUCIM mapping file not found: "
            f"{orchestrator_instance.netlogo_lucim_mapping_path}"
        )
    
    return orchestrator_instance.netlogo_lucim_mapping_path.read_text(encoding="utf-8")

