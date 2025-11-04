#!/usr/bin/env python3
"""
Logging utilities for NetLogo to PlantUML pipeline
Provides centralized logging configuration and file management
"""

import logging
import sys
import io
import pathlib
import datetime
from typing import Optional
from utils_config_constants import OUTPUT_DIR
from utils_path import get_run_base_dir

def _stringify(obj) -> str:
    """Safely stringify arbitrary objects for Markdown output."""
    try:
        import json
        if isinstance(obj, (dict, list)):
            return json.dumps(obj, indent=2, ensure_ascii=False)
        return str(obj)
    except Exception:
        return str(obj)

def write_reasoning_md_from_payload(
    *,
    output_dir: pathlib.Path,
    agent_name: str,
    base_name: str,
    model: str,
    timestamp: str,
    reasoning_effort: Optional[str] = None,
    step_number: Optional[int] = None,
    payload: Optional[dict] = None,
) -> None:
    """
    Write a structured reasoning.md including all available reasoning-related fields from the API payload.

    The output uses deterministic section ordering and includes only sections with available data.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    reasoning_file = output_dir / "output-reasoning.md"

    sections = []

    header = [
        f"# Reasoning - {agent_name.title().replace('_', ' ')}",
        "",
        f"**Base Name:** {base_name}",
        f"**Model:** {model}",
        f"**Timestamp:** {timestamp}",
        f"**Step Number:** {step_number if step_number is not None else 'N/A'}",
        f"**Reasoning Level:** {reasoning_effort if reasoning_effort else 'N/A'}",
        "",
    ]
    sections.append("\n".join(header))

    payload = payload or {}

    # Normalize common reasoning-related fields from diverse API payload shapes
    # Try multiple canonical keys for each concept
    def get_first(*keys, default=None):
        for k in keys:
            if k in payload and payload.get(k) not in (None, ""):
                return payload.get(k)
        return default

    reasoning_text = get_first("reasoning", "reasoning_text", "chain_of_thought", "thoughts")
    reasoning_summary = get_first("reasoning_summary", "summary")
    step_trace = get_first("step_trace", "trace", "steps")
    tool_justifications = get_first("tool_justifications", "tools_justification", "tool_rationale")

    # Token usage can be in flat counts or nested under usage
    token_usage = None
    if any(k in payload for k in ("tokens_used", "input_tokens", "output_tokens", "reasoning_tokens")):
        token_usage = {
            "total_tokens": payload.get("tokens_used"),
            "prompt_tokens": payload.get("input_tokens"),
            "completion_tokens": payload.get("output_tokens"),
            "reasoning_tokens": payload.get("reasoning_tokens"),
        }
    usage_nested = payload.get("usage") or payload.get("token_usage")
    if isinstance(usage_nested, dict):
        # Merge, nested wins when present
        token_usage = {**(token_usage or {}), **usage_nested}

    errors = payload.get("errors")

    # Deterministic section ordering
    if reasoning_text is not None:
        sections.append("## Reasoning\n\n" + (_stringify(reasoning_text) if str(reasoning_text).strip() else ""))
    if reasoning_summary is not None:
        sections.append("## Reasoning Summary\n\n" + (_stringify(reasoning_summary) if str(reasoning_summary).strip() else ""))
    if step_trace is not None:
        sections.append("## Step Trace\n\n" + (_stringify(step_trace) if str(step_trace).strip() else ""))
    if tool_justifications is not None:
        sections.append("## Tool Justifications\n\n" + (_stringify(tool_justifications) if str(tool_justifications).strip() else ""))
    if token_usage is not None:
        # Expose visible output tokens and total output tokens (reasoning + visible)
        try:
            reasoning_toks = 0
            visible_output_toks = 0
            # Accept multiple common keys
            if isinstance(token_usage, dict):
                reasoning_toks = int(token_usage.get("reasoning_tokens") or token_usage.get("reasoningTokens") or 0)
                # completion/output tokens represent the visible channel
                visible_output_toks = int(
                    token_usage.get("completion_tokens")
                    or token_usage.get("output_tokens")
                    or token_usage.get("visible_output_tokens")
                    or token_usage.get("visibleOutputTokens")
                    or 0
                )
            total_output_toks = reasoning_toks + visible_output_toks
            token_usage_augmented = {
                **(token_usage or {}),
                "visible_output_tokens": visible_output_toks,
                "total_output_tokens": total_output_toks,
            }
        except Exception:
            token_usage_augmented = token_usage

        sections.append("## Token Usage (Reasoning & Visible)\n\n" + (_stringify(token_usage_augmented) if token_usage_augmented else ""))
    if errors is not None:
        # Ensure list formatting when list, allow empty section when empty
        if isinstance(errors, list):
            formatted = "\n".join(f"- {e}" for e in errors) if errors else ""
        else:
            formatted = _stringify(errors) if str(errors).strip() else ""
        sections.append("## Errors\n\n" + formatted)

    # Always include a raw payload section for auditability
    # Always include raw payload section, even if empty dict
    sections.append("## Raw Reasoning Payload\n\n" + (_stringify(payload) if payload else ""))

    content = "\n\n".join(sections)
    reasoning_file.write_text(content, encoding="utf-8")

def setup_orchestration_logger(base_name: str, model_name: str, timestamp: str, reasoning_effort: str = "medium", text_verbosity: str = "medium", persona_set: str = "persona-v1", version: Optional[str] = None) -> logging.Logger:
    """
    Set up a logger for orchestration execution with file output.
    
    Args:
        base_name: Base name for the output files
        model_name: AI model name used for processing
        timestamp: Timestamp string for the execution
        reasoning_effort: Reasoning effort level (default: medium)
        text_verbosity: Text verbosity level (default: medium)
        persona_set: Persona set name (default: persona-v1)
        version: Optional orchestrator version (e.g., "v2", "v3-no-adk", "v3-adk")
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(f"orchestrator_{base_name}_{timestamp}")
    logger.setLevel(logging.INFO)
    
    # Clear any existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create file handler under per-run/per-combination directory
    # New format: output/runs/<YYYY-MM-DD>/<HHMM>-<persona-set>[-<version>]/<case>-<model>-reason-<effort>-verb-<verbosity>/<case>_<timestamp>_<model>_orchestrator.log
    run_dir = get_run_base_dir(timestamp, base_name, model_name, reasoning_effort, text_verbosity, persona_set, version)
    run_dir.mkdir(parents=True, exist_ok=True)
    log_filename = f"{base_name}_{timestamp}_{model_name}_orchestrator.log"
    log_file = run_dir / log_filename
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # Create console handler bound to original stdout to avoid recursion when stdout/stderr are redirected
    console_handler = logging.StreamHandler(stream=sys.__stdout__)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

class _StreamToLogger(io.TextIOBase):
    """Bridge a text stream (stdout/stderr) to a logger."""
    def __init__(self, logger: logging.Logger, level: int) -> None:
        self._logger = logger
        self._level = level

    def write(self, buf: str) -> int:
        if not buf:
            return 0
        for line in buf.rstrip().splitlines():
            self._logger.log(self._level, line)
        return len(buf)

    def flush(self) -> None:  # pragma: no cover
        pass

def attach_stdio_to_logger(logger: logging.Logger) -> None:
    """
    Redirect sys.stdout and sys.stderr to the provided logger so that
    all terminal outputs (including print statements) are persisted in the
    orchestrator log file as well as the console.
    """
    sys.stdout = _StreamToLogger(logger, logging.INFO)
    sys.stderr = _StreamToLogger(logger, logging.ERROR)

def get_agent_logger(agent_name: str, base_name: str, model_name: str, timestamp: str) -> logging.Logger:
    """
    Get a logger for a specific agent.
    
    Args:
        agent_name: Name of the agent
        base_name: Base name for the output files
        model_name: AI model name used for processing
        timestamp: Timestamp string for the execution
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(f"{agent_name}_{base_name}_{timestamp}")
    logger.setLevel(logging.INFO)
    
    # Clear any existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create file handler
    # Format: base-name_timestamp_AI-model_agent-name.log
    log_filename = f"{base_name}_{timestamp}_{model_name}_{agent_name}.log"
    log_file = OUTPUT_DIR / log_filename
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # Create console handler bound to original stdout to avoid recursion when stdout/stderr are redirected
    console_handler = logging.StreamHandler(stream=sys.__stdout__)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def format_parameter_bundle(
    *,
    model: Optional[str] = None,
    base_name: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    reasoning_summary: Optional[str] = None,
    text_verbosity: Optional[str] = None,
    
    seed: Optional[int] = None,
    extra_params: Optional[dict] = None,
) -> str:
    """
    Build a single-line parameter bundle string that ALWAYS includes text verbosity
    when other run parameters are displayed/logged together.

    Only call this helper in contexts where a parameter bundle is intended to be shown.
    Do not use it for non-parameter messages to keep verbosity out of unrelated logs.
    """
    kv_pairs = []
    if model is not None:
        kv_pairs.append(f"model={model}")
    if base_name is not None:
        kv_pairs.append(f"base={base_name}")
    if reasoning_effort is not None:
        kv_pairs.append(f"reasoning_effort={reasoning_effort}")
    if reasoning_summary is not None:
        kv_pairs.append(f"reasoning_summary={reasoning_summary}")
    # No max_tokens logging
    if seed is not None:
        kv_pairs.append(f"seed={seed}")
    # Always include verbosity in the parameter bundle
    if text_verbosity is not None:
        kv_pairs.append(f"text_verbosity={text_verbosity}")
    if extra_params:
        for k, v in extra_params.items():
            kv_pairs.append(f"{k}={v}")
    return "Parameters: " + ", ".join(kv_pairs)
