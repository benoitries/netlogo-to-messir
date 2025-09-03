#!/usr/bin/env python3
"""
Configuration file for NetLogo to PlantUML pipeline
Centralizes all file and directory path constants
"""

import pathlib

# Base directory (parent of this file)
BASE_DIR = pathlib.Path(__file__).resolve().parent

# Input directories
INPUT_NETLOGO_DIR = BASE_DIR / "input-netlogo"
INPUT_ICRASH_DIR = BASE_DIR / "input-icrash"
INPUT_IMAGES_DIR = BASE_DIR / "input-images"
INPUT_PERSONA_DIR = BASE_DIR / "input-persona"

# Output directory
OUTPUT_DIR = BASE_DIR / "output"

# Persona files
PERSONA_SYNTAX_PARSER = INPUT_PERSONA_DIR / "PSN_1_NetLogoSyntaxParser-v4.md"
PERSONA_SEMANTICS_PARSER = INPUT_PERSONA_DIR / "PSN_2_NetlogoSemanticsParser-v3.md"
PERSONA_MESSIR_MAPPER = INPUT_PERSONA_DIR / "PSN_3_MessirUCIConceptsMapper-v3.md"
PERSONA_SCENARIO_WRITER = INPUT_PERSONA_DIR / "PSN_4_MessirUCIScenarioWriter-v2.md"
PERSONA_PLANTUML_WRITER = INPUT_PERSONA_DIR / "PSN_5_PlantUMLWriter-v2.md"
PERSONA_PLANTUML_AUDITOR = INPUT_PERSONA_DIR / "PSN_6_PlantUMLMessirAuditor-v6.md"
PERSONA_PLANTUML_CORRECTOR = INPUT_PERSONA_DIR / "PSN_7_PlantUMLMessirCorrector-v2.md"

# Rules files
MESSIR_RULES_FILE = INPUT_PERSONA_DIR / "messir-uci-compliance-rules-v2.md"

# File patterns
NETLOGO_CODE_PATTERN = "*-netlogo-code.md"
NETLOGO_INTERFACE_PATTERN = "*-netlogo-interface-*.png"
ICRASH_PATTERN = "*.pdf"

# Agent versions
AGENT_VERSION_SYNTAX_PARSER = "v4"
AGENT_VERSION_SEMANTICS_PARSER = "v3"
AGENT_VERSION_MESSIR_MAPPER = "v3"
AGENT_VERSION_SCENARIO_WRITER = "v2"
AGENT_VERSION_PLANTUML_WRITER = "v2"
AGENT_VERSION_PLANTUML_AUDITOR = "v6"
AGENT_VERSION_PLANTUML_CORRECTOR = "v2"

# Available AI models
#AVAILABLE_MODELS = ["gpt-5","gpt-5-mini","gpt-5-nano", "o3", "o4-mini"]
AVAILABLE_MODELS = ["gpt-5","gpt-5-mini","gpt-5-nano"]

# Agent-specific configurations
# Each agent can be configured with:
# - model: The AI model to use (currently only "gpt-5" supported)
# - max_completion_tokens: Token limit (stored for reference, not used in API calls)
# - reasoning_effort: "low", "medium", or "high"
# - reasoning_summary: "auto" or "manual"
AGENT_CONFIGS = {
    "syntax_parser": {
        "model": "gpt-5",
        "max_completion_tokens": 16000,
        "reasoning_effort": "medium",  # Increased for better parsing accuracy
        "reasoning_summary": "auto"
    },
    "semantics_parser": {
        "model": "gpt-5",
        "max_completion_tokens": 16000,
        "reasoning_effort": "medium",  # Increased for better semantic analysis
        "reasoning_summary": "auto"
    },
    "messir_mapper": {
        "model": "gpt-5",
        "max_completion_tokens": 16000,
        "reasoning_effort": "low",
        "reasoning_summary": "auto"
    },
    "scenario_writer": {
        "model": "gpt-5",
        "max_completion_tokens": 16000,
        "reasoning_effort": "low",
        "reasoning_summary": "auto"
    },
    "plantuml_writer": {
        "model": "gpt-5",
        "max_completion_tokens": 8000,
        "reasoning_effort": "low",
        "reasoning_summary": "auto"
    },
    "plantuml_auditor": {
        "model": "gpt-5",
        "max_completion_tokens": 8000,
        "reasoning_effort": "high",  # High effort for thorough compliance checking
        "reasoning_summary": "auto"
    },
    "plantuml_corrector": {
        "model": "gpt-5",
        "max_completion_tokens": 8000,
        "reasoning_effort": "low",
        "reasoning_summary": "auto"
    }
}

# Example: To increase reasoning effort for the syntax parser, change:
# "syntax_parser": {
#     "model": "gpt-5",
#     "max_completion_tokens": 16000,
#     "reasoning_effort": "medium",  # Changed from "low" to "medium"
#     "reasoning_summary": "auto"
# }
#
# Example: To use manual reasoning summary for the plantuml_writer, change:
# "plantuml_writer": {
#     "model": "gpt-5",
#     "max_completion_tokens": 8000,
#     "reasoning_effort": "low",
#     "reasoning_summary": "manual"  # Changed from "auto" to "manual"
# }

# Model configuration
MODEL_CONFIG = {
    "gpt-5": {
        "supports_temperature": False,
        "default_temperature": 1.0,
        "supports_response_format": True,
        "supports_reasoning": True
    },
    "gpt-5-nano": {
        "supports_temperature": False,
        "default_temperature": 1.0,
        "supports_response_format": True,
        "supports_reasoning": True  # gpt-5-nano does support reasoning
    },
    "gpt-5-mini": {
        "supports_temperature": False,
        "default_temperature": 1.0,
        "supports_response_format": True,
        "supports_reasoning": True  # gpt-5-mini supports reasoning_effort (default medium)
    },
    "o3": {
        "supports_temperature": False,
        "default_temperature": 1.0,
        "supports_response_format": True,
        "supports_reasoning": True  # o3 supports reasoning_effort with low/medium/high
    },
    "o4-mini": {
        "supports_temperature": False,
        "default_temperature": 1.0,
        "supports_response_format": True,
        "supports_reasoning": True  # o4-mini supports reasoning_effort with low/medium/high
    }
}



def ensure_directories():
    """Ensure all required directories exist"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    INPUT_NETLOGO_DIR.mkdir(exist_ok=True)
    INPUT_ICRASH_DIR.mkdir(exist_ok=True)
    INPUT_IMAGES_DIR.mkdir(exist_ok=True)
    INPUT_PERSONA_DIR.mkdir(exist_ok=True)



def get_model_config(model_name: str) -> dict:
    """Get configuration for a specific model"""
    return MODEL_CONFIG.get(model_name, MODEL_CONFIG["gpt-5"])

def get_agent_config(agent_name: str) -> dict:
    """Get the complete configuration for a specific agent"""
    return AGENT_CONFIGS.get(agent_name, AGENT_CONFIGS["syntax_parser"])

def get_reasoning_config(agent_name: str) -> dict:
    """Get the complete API configuration for an agent including reasoning and model"""
    agent_config = get_agent_config(agent_name)
    model_name = agent_config["model"]
    model_config = get_model_config(model_name)
    
    api_config = {
        "model": model_name
    }
    
    # Add reasoning if supported by the model
    if model_config.get("supports_reasoning", False):
        api_config["reasoning"] = {
            "effort": agent_config["reasoning_effort"],
            "summary": agent_config["reasoning_summary"]
        }
    
    return api_config



def get_reasoning_suffix(agent_name: str) -> str:
    """Get the reasoning suffix for a given agent name based on its configuration"""
    if agent_name not in AGENT_CONFIGS:
        return "reasoning-unknown"
    
    config = AGENT_CONFIGS[agent_name]
    effort = config.get("reasoning_effort", "low")
    summary = config.get("reasoning_summary", "auto")
    
    return f"reasoning-{effort}-{summary}"

# Unified Agent Response Schema
AGENT_RESPONSE_SCHEMA = {
    # Common fields for all agents
    "common_fields": {
        "agent_type": str,
        "model": str,
        "timestamp": str,
        "base_name": str,
        "step_number": str,
        "reasoning_summary": str,
        "errors": list,
        "data": dict  # Unified field for agent-specific output
    },
    
    # Agent-specific data structure validation
    "agent_data_schemas": {
        "syntax_parser": {
            "data_type": "ast",
            "required_keys": ["procedures", "breeds", "globals", "setup", "go"],
            "description": "Abstract Syntax Tree"
        },
        "semantics_parser": {
            "data_type": "state_machine", 
            "required_keys": ["states", "transitions", "initial_state", "final_states"],
            "description": "State Machine Representation"
        },
        "messir_mapper": {
            "data_type": "messir_concepts",
            "required_keys": ["actors", "input_events", "output_events"],
            "description": "Messir Concepts Mapping"
        },
        "scenario_writer": {
            "data_type": "scenarios",
            "required_keys": ["typical"],
            "description": "Generated Scenarios"
        },
        "plantuml_writer": {
            "data_type": "plantuml_diagrams",
            "required_keys": ["typical"],
            "description": "PlantUML Diagrams"
        },
        "plantuml_auditor": {
            "data_type": "audit_results",
            "required_keys": ["verdict", "non-compliant-rules"],
            "description": "Audit Results"
        },
        "plantuml_corrector": {
            "data_type": "corrected_diagrams",
            "required_keys": ["typical"],
            "description": "Corrected PlantUML Diagrams"
        }
    }
}

def get_agent_schema(agent_type: str) -> dict:
    """Get schema for specific agent type"""
    return AGENT_RESPONSE_SCHEMA["agent_data_schemas"].get(agent_type, {})

def validate_agent_response(agent_type: str, response: dict) -> list:
    """Validate agent response against schema"""
    errors = []
    schema = get_agent_schema(agent_type)
    
    # Check common fields
    for field, field_type in AGENT_RESPONSE_SCHEMA["common_fields"].items():
        if field not in response:
            errors.append(f"Missing required field: {field}")
        elif not isinstance(response[field], field_type):
            errors.append(f"Field {field} must be of type {field_type}")
    
    # Check agent-specific data
    if "data" in response and schema:
        data = response["data"]
        for required_key in schema.get("required_keys", []):
            if required_key not in data:
                errors.append(f"Missing required data key: {required_key}")
    
    return errors
