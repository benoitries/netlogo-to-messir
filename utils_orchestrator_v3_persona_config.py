#!/usr/bin/env python3
"""
Orchestrator V3 Persona Configuration Utility
Manages persona set initialization and path configuration for V3 orchestrator.
"""

import pathlib
from typing import Dict, Any
from utils_config_constants import INPUT_PERSONA_DIR


def initialize_v3_persona_set(orchestrator_instance, persona_set: str = "persona-v3-limited-agents") -> str:
    """
    Initialize persona set for v3 orchestrator.
    
    Args:
        orchestrator_instance: Orchestrator instance to configure
        persona_set: Persona set name (default: "persona-v3-limited-agents")
        
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
    """Update persona file paths for all agents based on persona-v3-limited-agents set."""
    persona_dir = INPUT_PERSONA_DIR / orchestrator_instance.selected_persona_set
    
    v3_persona_paths = {
        "lucim_operation_generator": persona_dir / "PSN_LUCIM_Operation_Model_Generator.md",
        "lucim_operation_auditor": persona_dir / "PSN_LUCIM_Operation_Model_Auditor.md",
        "lucim_scenario_generator": persona_dir / "PSN_LUCIM_Scenario_Generator.md",
        "lucim_scenario_auditor": persona_dir / "PSN_LUCIM_Scenario_Auditor.md",
        "lucim_plantuml_diagram_generator": persona_dir / "PSN_LUCIM_PlantUML_Diagram_Generator.md",
        "lucim_plantuml_diagram_auditor": persona_dir / "PSN_LUCIM_PlantUML_Diagram_Auditor.md",
        "mapping_netlogo_to_lucim_operation_model": persona_dir / "RULES_MAPPING_NETLOGO_TO_OPERATION_MODEL.md",
    }
    
    orchestrator_instance.netlogo_lucim_mapping_path = v3_persona_paths["mapping_netlogo_to_lucim_operation_model"]
    
    agents_with_paths = [
        (orchestrator_instance.lucim_operation_generator_agent, v3_persona_paths["lucim_operation_generator"]),
        (orchestrator_instance.lucim_operation_auditor_agent, v3_persona_paths["lucim_operation_auditor"]),
        (orchestrator_instance.lucim_scenario_generator_agent, v3_persona_paths["lucim_scenario_generator"]),
        (orchestrator_instance.lucim_scenario_auditor_agent, v3_persona_paths["lucim_scenario_auditor"]),
        (orchestrator_instance.lucim_plantuml_diagram_generator_agent, v3_persona_paths["lucim_plantuml_diagram_generator"]),
        (orchestrator_instance.lucim_plantuml_diagram_auditor_agent, v3_persona_paths["lucim_plantuml_diagram_auditor"]),
    ]
    
    for agent, path in agents_with_paths:
        if hasattr(agent, 'update_persona_path'):
            agent.update_persona_path(str(path))
    
    # Update LUCIM rules path
    for agent in [
        orchestrator_instance.lucim_operation_generator_agent,
        orchestrator_instance.lucim_operation_auditor_agent,
        orchestrator_instance.lucim_scenario_generator_agent,
        orchestrator_instance.lucim_scenario_auditor_agent,
        orchestrator_instance.lucim_plantuml_diagram_generator_agent,
        orchestrator_instance.lucim_plantuml_diagram_auditor_agent,
    ]:
        if hasattr(agent, 'update_lucim_rules_path'):
            agent.update_lucim_rules_path(str(v3_persona_paths["mapping_netlogo_to_lucim_operation_model"]))


def load_netlogo_lucim_mapping(orchestrator_instance) -> str:
    """Load NetLogo to LUCIM mapping file content."""
    if not hasattr(orchestrator_instance, 'netlogo_lucim_mapping_path'):
        persona_dir = INPUT_PERSONA_DIR / orchestrator_instance.selected_persona_set
        orchestrator_instance.netlogo_lucim_mapping_path = persona_dir / "RULES_MAPPING_NETLOGO_TO_OPERATION_MODEL.md"
    
    if not orchestrator_instance.netlogo_lucim_mapping_path.exists():
        raise FileNotFoundError(
            f"MANDATORY INPUT MISSING: NetLogo to LUCIM mapping file not found: "
            f"{orchestrator_instance.netlogo_lucim_mapping_path}"
        )
    
    return orchestrator_instance.netlogo_lucim_mapping_path.read_text(encoding="utf-8")

