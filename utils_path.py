#!/usr/bin/env python3
"""
Path utilities for orchestrator and agents.

Provides centralized construction of run directories following the
new layout:

  output/runs/<YYYY-MM-DD>/<HHMM>/<case>-<model-name>-reason-<reasoning-value>-verb-<verbosity-value>/<NN-stage>/

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


def build_combination_folder_name(
    case_name: str,
    model_name: str,
    reasoning_effort: str,
    text_verbosity: str,
) -> str:
    """Return the combination folder name for a given case/model/reasoning/verbosity.

    Example: "boiling-<model>-reason-medium-verb-high"
    """
    case_safe = sanitize_path_component(case_name)
    model_safe = sanitize_path_component(model_name)
    return f"{case_safe}-{model_safe}-reason-{reasoning_effort}-verb-{text_verbosity}"


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
        Path to: OUTPUT_DIR/runs/YYYY-MM-DD/HHMM-<PERSONA-SET-NAME>[-<VERSION>]/<combination-folder>
    """
    odir = output_dir if output_dir is not None else OUTPUT_DIR
    day_folder = f"{timestamp[0:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
    time_folder = f"{timestamp.split('_')[1]}-{persona_set}"
    if version:
        time_folder = f"{time_folder}-{version}"
    combo = build_combination_folder_name(case_name, model_name, reasoning_effort, text_verbosity)
    return odir / "runs" / day_folder / time_folder / combo


