#!/usr/bin/env python3
"""
Path utilities for orchestrator and agents.

Provides centralized construction of run directories following the
new layout:

  output/runs/<YYYY-MM-DD>/<HHMM>/<case>-<model-name>-<RXX>-<VXX>/<NN-stage>/

Where:
  - RXX is reasoning effort short code: RMI (minimal), RLO (low), RME (medium), RHI (high)
  - VXX is verbosity short code: VLO (low), VME (medium), VHI (high)

Example: "my-ecosys-gemini-2.5-flash-RME-VME"

This builder is deterministic and should be the single source of truth
for output folder computation across modules.
"""

from pathlib import Path
from typing import Optional
import re

from utils_config_constants import OUTPUT_DIR, DEFAULT_PERSONA_SET


def sanitize_path_component(value: str) -> str:
    """Return a filesystem-safe component string.

    Replaces any character not in [A-Za-z0-9._-] with '_', then collapses consecutive underscores
    and strips leading/trailing underscores. This keeps names readable/stable while safe for paths.
    """
    if value is None:
        return ""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(value))
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe or "unnamed"


def sanitize_agent_name(value: str) -> str:
    """Return a Python identifier-safe string for agent names.
    
    Replaces any character not in [A-Za-z0-9_] with '_', then collapses consecutive underscores
    and strips leading/trailing underscores. This ensures the name is a valid Python identifier
    suitable for Pydantic validation (must start with letter/underscore, contain only alphanumeric/underscore).
    
    Args:
        value: Original string (e.g., "mistral-medium" or "llama-3.3-70b-instruct")
        
    Returns:
        Sanitized identifier (e.g., "mistral_medium" or "llama_3_3_70b_instruct")
    """
    if value is None:
        return ""
    # Replace all non-alphanumeric (except underscore) with underscore
    safe = re.sub(r"[^A-Za-z0-9_]", "_", str(value))
    # Collapse consecutive underscores
    safe = re.sub(r"_+", "_", safe).strip("_")
    # Ensure it starts with letter or underscore (Python identifier requirement)
    if safe and not (safe[0].isalpha() or safe[0] == "_"):
        safe = "_" + safe
    return safe or "unnamed"


def _get_reasoning_short(reasoning_effort: str) -> str:
    """Convert reasoning effort to short code.
    
    Args:
        reasoning_effort: minimal|low|medium|high
        
    Returns:
        Short code: RMI|RLO|RME|RHI
    """
    mapping = {
        "minimal": "RMI",
        "low": "RLO",
        "medium": "RME",
        "high": "RHI"
    }
    return mapping.get(reasoning_effort.lower(), reasoning_effort.upper()[:3])


def _get_verbosity_short(text_verbosity: str) -> str:
    """Convert text verbosity to short code.
    
    Args:
        text_verbosity: low|medium|high
        
    Returns:
        Short code: VLO|VME|VHI
    """
    mapping = {
        "low": "VLO",
        "medium": "VME",
        "high": "VHI"
    }
    return mapping.get(text_verbosity.lower(), text_verbosity.upper()[:3])


def _get_persona_set_short(persona_set: str) -> str:
    """Convert persona set name to short code.
    
    Extracts version number from persona set name and returns "PSvX" format.
    Examples:
        "persona-v1" -> "PSv1"
        "persona-v2" -> "PSv2"
        "persona-v3-limited-agents-v3-adk" -> "PSv3"
    
    Args:
        persona_set: Persona set name (e.g., "persona-v1", "persona-v3-limited-agents-v3-adk")
        
    Returns:
        Short code: PSvX where X is the version number, or original name if no version found
    """
    # Try to extract version pattern like "v1", "v2", "v3", etc.
    version_match = re.search(r'-v(\d+)', persona_set.lower())
    if version_match:
        version_num = version_match.group(1)
        return f"PSv{version_num}"
    # Fallback: if no version found, return sanitized short version
    # Extract first meaningful part (e.g., "persona" -> "PS")
    if persona_set.lower().startswith("persona"):
        return "PS"
    return sanitize_path_component(persona_set)[:10]  # Limit length for safety


def build_combination_folder_name(
    case_name: str,
    model_name: str,
    reasoning_effort: str,
    text_verbosity: str,
) -> str:
    """Return the combination folder name for a given case/model/reasoning/verbosity.

    Example: "boiling-<model>-RME-VME" (short format)
    """
    case_safe = sanitize_path_component(case_name)
    model_safe = sanitize_path_component(model_name)
    reasoning_short = _get_reasoning_short(reasoning_effort)
    verbosity_short = _get_verbosity_short(text_verbosity)
    return f"{case_safe}-{model_safe}-{reasoning_short}-{verbosity_short}"


def get_run_base_dir(
    timestamp: str,
    case_name: str,
    model_name: str,
    reasoning_effort: str,
    text_verbosity: str,
    persona_set: str = DEFAULT_PERSONA_SET,
    version: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> Path:
    """Compute the base directory for a run combination.

    Args:
        timestamp: Timestamp string formatted as YYYYMMDD-HHMM
        case_name: Case identifier (base name)
        model_name: Model name (from AVAILABLE_MODELS)
        reasoning_effort: minimal|low|medium|high
        text_verbosity: low|medium|high
        persona_set: Persona set name (default: DEFAULT_PERSONA_SET)
        version: Optional orchestrator version (e.g., "v2", "v3-no-adk", "v3-adk")
        output_dir: Override for OUTPUT_DIR mainly for testing

    Returns:
        Path to: OUTPUT_DIR/runs/YYYY-MM-DD/HHMM-<PSvX>[-<VERSION>]/<combination-folder>
        Where PSvX is short format (e.g., PSv3 for persona-v3-limited-agents-v3-adk)
    """
    odir = output_dir if output_dir is not None else OUTPUT_DIR
    day_folder = f"{timestamp[0:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
    # Extract HHMM from timestamp (format: YYYYMMDD_HHMM or YYYYMMDD-HHMM)
    time_part = timestamp.split('_')[1] if '_' in timestamp else timestamp.split('-')[1] if '-' in timestamp else timestamp[-4:]
    persona_short = _get_persona_set_short(persona_set)
    time_folder = f"{time_part}-{persona_short}"
    if version:
        time_folder = f"{time_folder}-{version}"
    combo = build_combination_folder_name(case_name, model_name, reasoning_effort, text_verbosity)
    return odir / "runs" / day_folder / time_folder / combo


