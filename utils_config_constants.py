#!/usr/bin/env python3
"""
Configuration file for NetLogo to PlantUML pipeline
Centralizes all file and directory path constants
"""

import os
import pathlib
from pathlib import Path
from typing import Dict, Set

# Import API key utility for automatic .env loading
from utils_api_key import get_openai_api_key

# Base directory (parent of this file)
BASE_DIR = pathlib.Path(__file__).resolve().parent

# OpenAI API configuration - automatically loads from .env files
try:
    OPENAI_API_KEY = get_openai_api_key()
except ValueError as e:
    print(f"Warning: {e}")
    OPENAI_API_KEY = None

# Input directories - use environment variables if set, otherwise use default paths
INPUT_NETLOGO_DIR = Path(os.getenv("INPUT_NETLOGO_DIR", BASE_DIR / "input-netlogo"))
INPUT_VALID_EXAMPLES_DIR = Path(os.getenv("INPUT_VALID_EXAMPLES_DIR", BASE_DIR / "input-valid-examples"))
INPUT_PERSONA_DIR = Path(os.getenv("INPUT_PERSONA_DIR", BASE_DIR / "input-persona"))

# Output directory
OUTPUT_DIR = BASE_DIR / "output"

# Default persona set
DEFAULT_PERSONA_SET = "persona-v2-after-ng-meeting"

# Persona files (default to DEFAULT_PERSONA_SET)
PERSONA_NETLOGO_ABSTRACT_SYNTAX_EXTRACTOR = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "PSN_1_NetLogoAbstractSyntaxExtractor.md"
PERSONA_BEHAVIOR_EXTRACTOR = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "PSN_2b_NetlogoBehaviorExtractor.md"
PERSONA_LUCIM_ENVIRONMENT_SYNTHESIZER = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "PSN_3_LUCIMEnvironmentSynthesizer.md"
PERSONA_LUCIM_SCENARIO_SYNTHESIZER = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "PSN_4_LUCIMScenarioSynthesizer.md"
PERSONA_PLANTUML_WRITER = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "PSN_5_PlantUMLWriter.md"
PERSONA_PLANTUML_AUDITOR = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "PSN_6_PlantUMLLUCIMAuditor.md"
PERSONA_PLANTUML_CORRECTOR = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "PSN_7_PlantUMLLUCIMCorrector.md"

# Rules files (default to DEFAULT_PERSONA_SET)
LUCIM_RULES_FILE = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "DSL_Target_LUCIM-full-definition-for-compliance.md"

# File patterns
NETLOGO_CODE_PATTERN = "*-netlogo-code.md"
NETLOGO_INTERFACE_PATTERN = "*-netlogo-interface-*.png"


# Available AI models (single source of truth)
# Note: Only update model names here.
AVAILABLE_MODELS = ["gpt-5-nano-2025-08-07","gpt-5-mini-2025-08-07","gpt-5-2025-08-07"]

# Default model derived from AVAILABLE_MODELS
DEFAULT_MODEL = AVAILABLE_MODELS[0] if AVAILABLE_MODELS else ""

# Agent-specific configurations
# Each agent can be configured with:
# - model: The AI model to use (currently only "gpt-5" supported)
# - reasoning_effort: "minimal", "low", "medium", or "high"
# - reasoning_summary: "auto" or "manual"
# - text_verbosity: "low", "medium", or "high"
AGENT_CONFIGS = {
    "netlogo_abstract_syntax_extractor": {
        "model": DEFAULT_MODEL,
        "reasoning_effort": "medium",  # Increased for better parsing accuracy
        "reasoning_summary": "auto",
        "text_verbosity": "medium"
    },
    "netlogo_interface_image_analyzer": {
        "model": DEFAULT_MODEL,
        "reasoning_effort": "medium",
        "reasoning_summary": "auto",
        "text_verbosity": "medium"
    },
    "behavior_extractor": {
        "model": DEFAULT_MODEL,
        "reasoning_effort": "medium",  # Increased for better semantic analysis
        "reasoning_summary": "auto",
        "text_verbosity": "medium"
    },
    "lucim_environment_synthesizer": {
        "model": DEFAULT_MODEL,
        "reasoning_effort": "medium",
        "reasoning_summary": "auto",
        "text_verbosity": "medium"
    },
    "lucim_scenario_synthesizer": {
        "model": DEFAULT_MODEL,
        "reasoning_effort": "medium",
        "reasoning_summary": "auto",
        "text_verbosity": "medium"
    },
    "plantuml_writer": {
        "model": DEFAULT_MODEL,
        "reasoning_effort": "medium",
        "reasoning_summary": "auto",
        "text_verbosity": "medium"
    },
    "plantuml_auditor": {
        "model": DEFAULT_MODEL,
        "reasoning_effort": "medium",  # Default medium for consistency
        "reasoning_summary": "auto",
        "text_verbosity": "medium"
    },
    "plantuml_corrector": {
        "model": DEFAULT_MODEL,
        "reasoning_effort": "medium",
        "reasoning_summary": "auto",
        "text_verbosity": "medium"
    }
}

# Timeouts and heartbeat (in seconds)
# Agent-level polling timeouts for OpenAI Responses API
# Default: None (no timeout) for all agents; CLI can override via presets
AGENT_TIMEOUTS = {
    "netlogo_abstract_syntax_extractor": None,
    "netlogo_interface_image_analyzer": None,
    "behavior_extractor": None,
    "lucim_environment_synthesizer": None,
    "lucim_scenario_synthesizer": None,
    "plantuml_writer": None,
    "plantuml_auditor": None,
    "plantuml_corrector": None,
    "plantuml_final_auditor": None,
}

# Orchestrator watchdog for parallel first stage (syntax + semantics)
# Default: None (no watchdog); CLI can override via presets
ORCHESTRATOR_PARALLEL_TIMEOUT = None
HEARTBEAT_SECONDS = 30  # periodic log while waiting


def ensure_directories():
    """Ensure all required directories exist"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    INPUT_NETLOGO_DIR.mkdir(exist_ok=True)
    INPUT_PERSONA_DIR.mkdir(exist_ok=True)
    # INPUT_VALID_EXAMPLES_DIR is a symlink, don't try to create it


def get_agent_config(agent_name: str) -> dict:
    """Get the complete configuration for a specific agent"""
    return AGENT_CONFIGS.get(agent_name, AGENT_CONFIGS["netlogo_abstract_syntax_extractor"])

def get_reasoning_config(agent_name: str) -> dict:
    """Get the complete API configuration for an agent including reasoning, text and model"""
    agent_config = get_agent_config(agent_name)
    model_name = agent_config["model"]

    api_config = {
        "model": model_name
    }

    api_config["reasoning"] = {
        "effort": agent_config["reasoning_effort"],
        "summary": agent_config["reasoning_summary"]
    }

    api_config["text"] = {
        "verbosity": agent_config.get("text_verbosity", "medium")
    }

    return api_config



 

# Unified Agent Response Schema (common fields only; agent-specific structures live in persona/DSL files)
AGENT_RESPONSE_SCHEMA = {
    "common_fields": {
        "agent_type": str,
        "model": str,
        "timestamp": str,
        "base_name": str,
        # Accept integer or string step numbers, and allow None during early wiring
        "step_number": (int, str, type(None)),
        "reasoning_summary": str,
        "errors": list,
        # Allow data to be absent/None when upstream returns empty content
        "data": (dict, type(None))
    }
}

def validate_agent_response(agent_type: str, response: dict) -> list:
    """Validate that response contains required common fields with correct types.

    Agent-specific data structure requirements are defined in input-persona files and are
    not duplicated here to avoid drift. Downstream agents should validate content based on
    those authoritative references when needed.
    """
    errors = []

    for field, field_type in AGENT_RESPONSE_SCHEMA["common_fields"].items():
        if field not in response:
            errors.append(f"Missing required field: {field}")
        # Special case: agent 2a (netlogo_interface_image_analyzer) returns data as array
        elif field == "data" and agent_type == "netlogo_interface_image_analyzer":
            if not isinstance(response[field], (list, dict, type(None))):
                errors.append(f"Field {field} must be of type (list, dict, NoneType) for {agent_type}")
        # If schema permits multiple types, isinstance handles tuple typing
        elif not isinstance(response[field], field_type):
            errors.append(f"Field {field} must be of type {field_type}")

    return errors


# Response Schema Constants (moved from response_schema_expected.py)
# Expected top-level key sets for each agent's response.json.
# These sets enforce exact presence: not less, not more.

COMMON_KEYS = {
    "agent_type",
    "model",
    "timestamp",
    "base_name",
    "step_number",
    "reasoning_summary",
    "data",
    "errors",
    "tokens_used",
    "input_tokens",
    "visible_output_tokens",
    "reasoning_tokens",
    "total_output_tokens",
    # Include raw_usage as existing agents store it in reasoning payload, not in response.json
}

# Some agents might include raw_response dump for auditing
OPTIONAL_KEYS = {"raw_response"}

AGENT_KEYS: Dict[str, Set[str]] = {
    "netlogo_abstract_syntax_extractor": COMMON_KEYS | OPTIONAL_KEYS,
    "netlogo_interface_image_analyzer": COMMON_KEYS | OPTIONAL_KEYS,
    "behavior_extractor": COMMON_KEYS | OPTIONAL_KEYS,
    "lucim_environment_synthesizer": COMMON_KEYS | OPTIONAL_KEYS,
    "lucim_scenario_synthesizer": COMMON_KEYS | OPTIONAL_KEYS,
    "plantuml_writer": COMMON_KEYS | OPTIONAL_KEYS,
    "plantuml_auditor": COMMON_KEYS | OPTIONAL_KEYS,
    "plantuml_corrector": COMMON_KEYS | OPTIONAL_KEYS,
    "plantuml_final_auditor": COMMON_KEYS | OPTIONAL_KEYS,
}


def expected_keys_for_agent(agent_type: str) -> Set[str]:
    """Get expected keys for a specific agent type."""
    return AGENT_KEYS.get(agent_type, COMMON_KEYS | OPTIONAL_KEYS)


def get_persona_file_paths(persona_set: str = DEFAULT_PERSONA_SET) -> Dict[str, Path]:
    """
    Get persona file paths for a specific persona set.
    
    Args:
        persona_set: Name of the persona set (subfolder in input-persona)
        
    Returns:
        Dictionary mapping persona file names to their paths
    """
    persona_dir = INPUT_PERSONA_DIR / persona_set
    
    return {
        "netlogo_abstract_syntax_extractor": persona_dir / "PSN_1_NetLogoAbstractSyntaxExtractor.md",
        "netlogo_interface_image_analyzer": persona_dir / "PSN_2a_NetlogoInterfaceImageAnalyzer.md",
        "behavior_extractor": persona_dir / "PSN_2b_NetlogoBehaviorExtractor.md",
        "lucim_environment_synthesizer": persona_dir / "PSN_3_LUCIMEnvironmentSynthesizer.md",
        "lucim_scenario_synthesizer": persona_dir / "PSN_4_LUCIMScenarioSynthesizer.md",
        "plantuml_writer": persona_dir / "PSN_5_PlantUMLWriter.md",
        "plantuml_auditor": persona_dir / "PSN_6_PlantUMLLUCIMAuditor.md",
        # Final auditor reuses the same persona as the initial auditor
        "plantuml_final_auditor": persona_dir / "PSN_6_PlantUMLLUCIMAuditor.md",
        "plantuml_corrector": persona_dir / "PSN_7_PlantUMLLUCIMCorrector.md",
        "lucim_rules": persona_dir / "DSL_Target_LUCIM-full-definition-for-compliance.md",
        "dsl_il_syn_description": persona_dir / "DSL_IL_SYN-description.md",
        "dsl_il_syn_mapping": persona_dir / "DSL_IL_SYN-mapping.md",
        "dsl_il_sem_description": persona_dir / "DSL_IL_SEM-description.md",
        "dsl_il_sem_mapping": persona_dir / "DSL_IL_SEM-mapping.md"
    }


def get_persona_file_path(persona_set: str, file_type: str) -> Path:
    """
    Get a specific persona file path for a persona set.
    
    Args:
        persona_set: Name of the persona set
        file_type: Type of persona file (e.g., 'syntax_parser', 'lucim_rules')
        
    Returns:
        Path to the requested persona file
    """
    persona_paths = get_persona_file_paths(persona_set)
    return persona_paths.get(file_type, Path())
