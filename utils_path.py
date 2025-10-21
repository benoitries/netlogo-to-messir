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

from utils_config_constants import OUTPUT_DIR


def build_combination_folder_name(
    case_name: str,
    model_name: str,
    reasoning_effort: str,
    text_verbosity: str,
) -> str:
    """Return the combination folder name for a given case/model/reasoning/verbosity.

    Example: "boiling-<model>-reason-medium-verb-high"
    """
    return f"{case_name}-{model_name}-reason-{reasoning_effort}-verb-{text_verbosity}"


def get_run_base_dir(
    timestamp: str,
    case_name: str,
    model_name: str,
    reasoning_effort: str,
    text_verbosity: str,
    output_dir: Optional[Path] = None,
) -> Path:
    """Compute the base directory for a run combination.

    Args:
        timestamp: Timestamp string formatted as YYYYMMDD_HHMM
        case_name: Case identifier (base name)
        model_name: Model name (from AVAILABLE_MODELS)
        reasoning_effort: minimal|low|medium|high
        text_verbosity: low|medium|high
        output_dir: Override for OUTPUT_DIR mainly for testing

    Returns:
        Path to: OUTPUT_DIR/runs/YYYY-MM-DD/HHMM/<combination-folder>
    """
    odir = output_dir if output_dir is not None else OUTPUT_DIR
    day_folder = f"{timestamp[0:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
    time_folder = timestamp.split("_")[1]
    combo = build_combination_folder_name(case_name, model_name, reasoning_effort, text_verbosity)
    return odir / "runs" / day_folder / time_folder / combo


