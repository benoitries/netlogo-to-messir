#!/usr/bin/env python3
"""
Configuration file for NetLogo to PlantUML pipeline
Centralizes all file and directory path constants
"""

import os
import pathlib
from pathlib import Path
from typing import Dict, Set

# Base directory (parent of this file)
BASE_DIR = pathlib.Path(__file__).resolve().parent

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Input directories
INPUT_NETLOGO_DIR = BASE_DIR / "input-netlogo"
INPUT_ICRASH_DIR = BASE_DIR / "input-icrash"
INPUT_IMAGES_DIR = BASE_DIR / "input-images"
INPUT_PERSONA_DIR = BASE_DIR / "input-persona"

# Output directory
OUTPUT_DIR = BASE_DIR / "output"

# Persona files (default to persona-v1)
PERSONA_SYNTAX_PARSER = INPUT_PERSONA_DIR / "persona-v1" / "PSN_1_NetLogoSyntaxParser.md"
PERSONA_SEMANTICS_PARSER = INPUT_PERSONA_DIR / "persona-v1" / "PSN_2_NetlogoSemanticsParser.md"
PERSONA_MESSIR_MAPPER = INPUT_PERSONA_DIR / "persona-v1" / "PSN_3_MessirUCIConceptsMapper.md"
PERSONA_SCENARIO_WRITER = INPUT_PERSONA_DIR / "persona-v1" / "PSN_4_MessirUCIScenarioWriter.md"
PERSONA_PLANTUML_WRITER = INPUT_PERSONA_DIR / "persona-v1" / "PSN_5_PlantUMLWriter.md"
PERSONA_PLANTUML_AUDITOR = INPUT_PERSONA_DIR / "persona-v1" / "PSN_6_PlantUMLMessirAuditor.md"
PERSONA_PLANTUML_CORRECTOR = INPUT_PERSONA_DIR / "persona-v1" / "PSN_7_PlantUMLMessirCorrector.md"

# Rules files (default to persona-v1)
MESSIR_RULES_FILE = INPUT_PERSONA_DIR / "persona-v1" / "DSL_Target_MUCIM-full-definition-for-compliance.md"

# Default persona set
DEFAULT_PERSONA_SET = "persona-v1"

# File patterns
NETLOGO_CODE_PATTERN = "*-netlogo-code.md"
NETLOGO_INTERFACE_PATTERN = "*-netlogo-interface-*.png"
ICRASH_PATTERN = "*.pdf"

# Agent versions
AGENT_VERSION_SYNTAX_PARSER = "v5"
AGENT_VERSION_SEMANTICS_PARSER = "v4"
AGENT_VERSION_MESSIR_MAPPER = "v3"
AGENT_VERSION_SCENARIO_WRITER = "v2"
AGENT_VERSION_PLANTUML_WRITER = "v2"
AGENT_VERSION_PLANTUML_AUDITOR = "v6"
AGENT_VERSION_PLANTUML_CORRECTOR = "v2"

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
    "syntax_parser": {
        "model": DEFAULT_MODEL,
        "reasoning_effort": "medium",  # Increased for better parsing accuracy
        "reasoning_summary": "auto",
        "text_verbosity": "medium"
    },
    "semantics_parser": {
        "model": DEFAULT_MODEL,
        "reasoning_effort": "medium",  # Increased for better semantic analysis
        "reasoning_summary": "auto",
        "text_verbosity": "medium"
    },
    "messir_mapper": {
        "model": DEFAULT_MODEL,
        "reasoning_effort": "medium",
        "reasoning_summary": "auto",
        "text_verbosity": "medium"
    },
    "scenario_writer": {
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
    "syntax_parser": None,
    "semantics_parser": None,
    "messir_mapper": None,
    "scenario_writer": None,
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
    INPUT_ICRASH_DIR.mkdir(exist_ok=True)
    INPUT_IMAGES_DIR.mkdir(exist_ok=True)
    INPUT_PERSONA_DIR.mkdir(exist_ok=True)


def get_agent_config(agent_name: str) -> dict:
    """Get the complete configuration for a specific agent"""
    return AGENT_CONFIGS.get(agent_name, AGENT_CONFIGS["syntax_parser"])

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
    "syntax_parser": COMMON_KEYS | OPTIONAL_KEYS,
    "semantics_parser": COMMON_KEYS | OPTIONAL_KEYS,
    "messir_mapper": COMMON_KEYS | OPTIONAL_KEYS,
    "scenario_writer": COMMON_KEYS | OPTIONAL_KEYS,
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
        "syntax_parser": persona_dir / "PSN_1_NetLogoSyntaxParser.md",
        "semantics_parser": persona_dir / "PSN_2_NetlogoSemanticsParser.md",
        "messir_mapper": persona_dir / "PSN_3_MessirUCIConceptsMapper.md",
        "scenario_writer": persona_dir / "PSN_4_MessirUCIScenarioWriter.md",
        "plantuml_writer": persona_dir / "PSN_5_PlantUMLWriter.md",
        "plantuml_auditor": persona_dir / "PSN_6_PlantUMLMessirAuditor.md",
        "plantuml_corrector": persona_dir / "PSN_7_PlantUMLMessirCorrector.md",
        "messir_rules": persona_dir / "DSL_Target_MUCIM-full-definition-for-compliance.md",
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
        file_type: Type of persona file (e.g., 'syntax_parser', 'messir_rules')
        
    Returns:
        Path to the requested persona file
    """
    persona_paths = get_persona_file_paths(persona_set)
    return persona_paths.get(file_type, Path())
