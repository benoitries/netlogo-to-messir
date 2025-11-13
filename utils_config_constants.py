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
from utils_api_key import get_api_key_for_model

# Base directory (parent of this file)
BASE_DIR = pathlib.Path(__file__).resolve().parent

# OpenAI/Gemini/Router API key is selected based on the chosen model (set after DEFAULT_MODEL)

# Input directories
INPUT_NETLOGO_DIR = Path(BASE_DIR / "input-netlogo")
INPUT_VALID_EXAMPLES_DIR = Path(BASE_DIR / "input-valid-examples")
INPUT_PERSONA_DIR = Path(BASE_DIR / "input-persona")

# Output directory
OUTPUT_DIR = BASE_DIR / "output"

# Default persona set
DEFAULT_PERSONA_SET = "persona-v3-limited-agents"

# Persona files (default to DEFAULT_PERSONA_SET)
PERSONA_LUCIM_OPERATION_MODEL_GENERATOR = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "PSN_LUCIM_Operation_Model_Generator.md"
PERSONA_LUCIM_OPERATION_MODEL_AUDITOR = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "PSN_LUCIM_Operation_Model_Auditor.md"
PERSONA_LUCIM_SCENARIO_GENERATOR = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "PSN_LUCIM_Scenario_Generator.md"
PERSONA_LUCIM_SCENARIO_AUDITOR = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "PSN_LUCIM_Scenario_Auditor.md"
PERSONA_LUCIM_PLANTUML_DIAGRAM_GENERATOR = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "PSN_LUCIM_PlantUML_Diagram_Generator.md"
PERSONA_LUCIM_PLANTUML_DIAGRAM_AUDITOR = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "PSN_LUCIM_PlantUML_Diagram_Auditor.md"

# Rules files (default to DEFAULT_PERSONA_SET)
RULES_LUCIM_OPERATION_MODEL = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "RULES_LUCIM_Operation_model.md"
RULES_LUCIM_SCENARIO = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "RULES_LUCIM_Scenario.md"
RULES_LUCIM_PLANTUML_DIAGRAM = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "RULES_LUCIM_PlantUML_Diagram.md"
RULES_MAPPING_NETLOGO_TO_OPERATION_MODEL = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "RULES_MAPPING_NETLOGO_TO_OPERATION_MODEL.md"
REVERSE_ENGINEERING_DRIVERS = INPUT_PERSONA_DIR / DEFAULT_PERSONA_SET / "REVERSE_ENGINEERING_DRIVERS.md"

# File patterns
NETLOGO_CODE_PATTERN = "*-netlogo-code.md"
NETLOGO_INTERFACE_PATTERN = "*-netlogo-interface-*.png"


# Available AI models (single source of truth)
# Note: Only update model names here.
# legacy models used wrongly in early experiments
# "mistralai/mistral-small-3.2-24b-instruct"
# "mistralai/Mistral-Small-24B-Instruct-2501"
# "meta-llama/llama-3.3-70b-instruct"
AVAILABLE_MODELS = [
    "gpt-5-nano-2025-08-07",
    "gpt-5-mini-2025-08-07",
    "gpt-5-2025-08-07",
    "gemini-2.5-flash",          
    "gemini-2.5-pro",            
    "mistralai/codestral-2508",
    "meta-llama/llama-4-scout-17b-16e-instruct"
]

# Default model derived from AVAILABLE_MODELS
DEFAULT_MODEL = AVAILABLE_MODELS[6]

# API key selected dynamically based on the default model/provider
OPENAI_API_KEY = get_api_key_for_model(DEFAULT_MODEL)

# OpenRouter max_tokens default (SSOT - Single Source of Truth)
# Value: 100,000 tokens (updated 2025-11-12 for new models with larger context windows)
# Analysis based on:
#   - Maximum prompt_tokens observed: 107,647 tokens (from curated-set analysis)
#   - Active models context windows: 256k-327k tokens (codestral-2508, llama-4-scout)
#   - Safety margin: ~20k tokens even with maximum prompt
#   - Compatible with all active models while allowing better utilization
# This prevents litellm from auto-calculating negative values with long prompts
DEFAULT_MAX_TOKENS_OPENROUTER = 100000

# OpenRouter max_tokens upper limit (SSOT - Single Source of Truth)
# Maximum allowed value for max_tokens to prevent excessive token usage
# Based on actual context windows:
# - mistralai/codestral-2508: 256,000 tokens (https://openrouter.ai/mistralai/codestral-2508)
# - meta-llama/llama-4-scout-17b-16e-instruct: 327,680 tokens (https://openrouter.ai/meta-llama/llama-4-scout)
# Values above this threshold will be capped to DEFAULT_MAX_TOKENS_OPENROUTER
MAX_MAX_TOKENS_OPENROUTER = 250000

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
    "lucim_operation_model_generator": {
        "model": DEFAULT_MODEL,
        "reasoning_effort": "medium",
        "reasoning_summary": "auto",
        "text_verbosity": "medium"
    },
    "lucim_operation_model_auditor": {
        "model": DEFAULT_MODEL,
        "reasoning_effort": "medium",
        "reasoning_summary": "auto",
        "text_verbosity": "medium"
    },
    "lucim_scenario_generator": {
        "model": DEFAULT_MODEL,
        "reasoning_effort": "medium",
        "reasoning_summary": "auto",
        "text_verbosity": "medium"
    },
    "lucim_scenario_auditor": {
        "model": DEFAULT_MODEL,
        "reasoning_effort": "medium",
        "reasoning_summary": "auto",
        "text_verbosity": "medium"
    },
    "lucim_plantuml_diagram_generator": {
        "model": DEFAULT_MODEL,
        "reasoning_effort": "medium",
        "reasoning_summary": "auto",
        "text_verbosity": "medium"
    },
    "lucim_plantuml_diagram_auditor": {
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
    "lucim_operation_model_generator": None,
    "lucim_operation_model_auditor": None,
    "lucim_scenario_generator": None,
    "lucim_scenario_auditor": None,
    "lucim_plantuml_diagram_generator": None,
    "lucim_plantuml_diagram_auditor": None,
    "plantuml_corrector": None,
    "plantuml_final_auditor": None,
}

# Orchestrator watchdog for parallel first stage (syntax + semantics)
# Default: None (no watchdog); CLI can override via presets
ORCHESTRATOR_PARALLEL_TIMEOUT = None
HEARTBEAT_SECONDS = 30  # periodic log while waiting


def ensure_directories():
    """Ensure all required directories exist"""
    for path in (OUTPUT_DIR, INPUT_NETLOGO_DIR, INPUT_PERSONA_DIR):
        try:
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
        except FileExistsError:
            # Path may be an existing symlink or file; do not attempt to mkdir
            pass
    # INPUT_VALID_EXAMPLES_DIR is a symlink, don't try to create it


def get_agent_config(agent_name: str) -> dict:
    """Get the complete configuration for a specific agent"""
    return AGENT_CONFIGS[agent_name]

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
        # Standardized structure: errors is None on success, list on failure
        "errors": (list, type(None)),
        # Allow data to be dict, list, string (raw LLM response), or None when upstream returns empty content
        "data": (dict, list, str, type(None))
    }
}

def validate_agent_response(agent_type: str, response: dict) -> list:
    """Validate that response contains required common fields with correct types.

    Agent-specific data structure requirements are defined in input-persona files and are
    not duplicated here to avoid drift. Downstream agents should validate content based on
    those authoritative references when needed.
    
    Note: The 'data' field can now be a string (raw LLM response), dict, list, or None.
    """
    errors = []

    for field, field_type in AGENT_RESPONSE_SCHEMA["common_fields"].items():
        if field not in response:
            errors.append(f"Missing required field: {field}")
        # Special case: agent 2a (netlogo_interface_image_analyzer) returns data as array
        elif field == "data" and agent_type == "netlogo_interface_image_analyzer":
            if not isinstance(response[field], (list, dict, type(None))):
                errors.append(f"Field {field} must be of type (list, dict, NoneType) for {agent_type}")
        # All generator agents now store raw LLM response text (string) in data field
        # Accept string, dict, list, or None for data field
        elif field == "data":
            if not isinstance(response[field], (str, dict, list, type(None))):
                errors.append(f"Field {field} must be of type (str, list, dict, NoneType) for {agent_type}")
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

# raw_response is part of the complete response
OPTIONAL_KEYS = {"raw_response"}

AGENT_KEYS: Dict[str, Set[str]] = {
    "lucim_operation_model_generator": COMMON_KEYS | OPTIONAL_KEYS,
    "lucim_operation_model_auditor": COMMON_KEYS | OPTIONAL_KEYS,
    "lucim_scenario_generator": COMMON_KEYS | OPTIONAL_KEYS,
    "lucim_scenario_auditor": COMMON_KEYS | OPTIONAL_KEYS,
    "lucim_plantuml_diagram_generator": COMMON_KEYS | OPTIONAL_KEYS,
    "lucim_plantuml_diagram_auditor": COMMON_KEYS | OPTIONAL_KEYS,
}


def expected_keys_for_agent(agent_type: str) -> Set[str]:
    """Get expected keys for a specific agent type."""
    return AGENT_KEYS[agent_type]


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
        "lucim_operation_model_generator": persona_dir / "PSN_LUCIM_Operation_Model_Generator.md",
        "lucim_operation_model_auditor": persona_dir / "PSN_LUCIM_Operation_Model_Auditor.md",
        "lucim_scenario_generator": persona_dir / "PSN_LUCIM_Scenario_Generator.md",
        "lucim_plantuml_diagram_generator": persona_dir / "PSN_LUCIM_PlantUML_Diagram_Generator.md",
        "lucim_plantuml_diagram_auditor": persona_dir / "PSN_LUCIM_PlantUML_Diagram_Auditor.md",
        "netlogo_lucim_mapping": persona_dir / "RULES_MAPPING_NETLOGO_TO_OPERATION_MODEL.md",
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
    return persona_paths[file_type]
