#!/usr/bin/env python3
"""
Generic entry point to run the NetLogo orchestrator with configurable model and defaults:
- Model: required via --model (falls back to DEFAULT_MODEL if omitted)
- Case study: provided via --base (e.g., 'boiling', 'my-ecosys')
- Reasoning effort: low|medium|high (default: medium)
- Reasoning summary: auto|manual (default: auto)
- Text verbosity: low|medium|high (default: low)

This wrapper avoids interactive prompts and runs a single combination with explicit model selection.
"""

import asyncio
import argparse
import datetime
import re
import sys
from pathlib import Path
import subprocess

# Ensure repository modules are importable
sys.path.append(str(Path(__file__).resolve().parents[1]))

from orchestrator_simplified import NetLogoOrchestratorSimplified  # noqa: E402
from utils_config_constants import DEFAULT_MODEL, AGENT_TIMEOUTS, ORCHESTRATOR_PARALLEL_TIMEOUT  # noqa: E402
from utils_logging import format_parameter_bundle  # noqa: E402


async def run_default(args: argparse.Namespace) -> None:
    """Run orchestrator for a given base with a configurable model and parameters."""
    # Preflight: validate model/provider before any processing
    from utils_openai_client import validate_model_name_and_connectivity
    model_name = args.model or DEFAULT_MODEL
    print(f"Preflight validation for model: {model_name}")
    ok, provider, message = validate_model_name_and_connectivity(model_name, verbose=True)
    if not ok:
        print(f"ERROR: Model preflight failed for provider '{provider}'. {message}")
        sys.exit(1)
    base_name = args.base

    orchestrator = NetLogoOrchestratorSimplified(model_name=model_name, persona_set=args.persona_set)

    # Apply requested configuration globally via unified API
    orchestrator.update_agent_configs(
        reasoning_effort=args.reasoning,
        reasoning_summary=args.summary,
        text_verbosity=args.verbosity,
    )

    # Emit a single parameter bundle line (console) for visibility
    bundle_line = format_parameter_bundle(
        model=model_name,
        base_name=base_name,
        reasoning_effort=args.reasoning,
        reasoning_summary=args.summary,
        text_verbosity=args.verbosity,
        extra_params={
            "timeout_agents": "no-timeout" if all(v is None for v in AGENT_TIMEOUTS.values()) else AGENT_TIMEOUTS,
            "timeout_orchestrator": "no-timeout" if ORCHESTRATOR_PARALLEL_TIMEOUT is None else f"{ORCHESTRATOR_PARALLEL_TIMEOUT}s",
        }
    )
    print(bundle_line)

    # Single-pass orchestration: steps 01–02 in parallel, then 03→ sequential
    print("Single-pass: steps 01–02 in parallel, then 03→ sequential")

    # Kick off the run (start_step defaults to 1)
    results = await orchestrator.run(base_name)

    # Minimal success signal
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ok = bool(results)
    print(f"[{ts}] Default run completed. Success: {ok}")

    # Auto-validate response.json keys for the latest run folder (today)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    runs_root = Path(__file__).resolve().parents[1] / "output" / "runs" / today
    if runs_root.exists():
        # Match folders with pattern: HHMM-persona-v1 (or HHMM-persona-...)
        time_persona_pattern = re.compile(r"^(\d{4})(-persona-[^/]+)?$")
        candidates = sorted(
            [p for p in runs_root.iterdir() if p.is_dir() and time_persona_pattern.match(p.name)],
            key=lambda p: p.name,
            reverse=True
        )
        if candidates:
            last_run_dir = candidates[0]
            print(f"Validating output-response-full.json keys under: {last_run_dir}")
            proc = subprocess.run([
                "python3",
                str(Path(__file__).resolve().parent / "validate_response_jsons.py"),
                str(last_run_dir)
            ])
            if proc.returncode != 0:
                raise SystemExit("Validation failed: response.json keys mismatch detected")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run orchestrator with configurable model")
    parser.add_argument("--base", type=str, default="boiling", help="Base (case study) name, e.g., 'boiling' or 'my-ecosys'")
    parser.add_argument("--model", type=str, default=None, help="Model name, e.g., 'gpt-5-nano-2025-08-07', 'gpt-5-mini-2025-08-07', 'gpt-5-2025-08-07'")
    parser.add_argument("--reasoning", choices=["low", "medium", "high"], default="medium", help="Reasoning effort")
    parser.add_argument("--summary", choices=["auto", "manual"], default="auto", help="Reasoning summary mode")
    parser.add_argument("--verbosity", choices=["low", "medium", "high"], default="low", help="Text verbosity level")
    parser.add_argument("--persona-set", type=str, default="persona-v2-after-ng-meeting", help="Persona set to use (default: persona-v2-after-ng-meeting). Remove or set to empty to enable interactive selection")
    args = parser.parse_args()
    asyncio.run(run_default(args))


if __name__ == "__main__":
    main()
