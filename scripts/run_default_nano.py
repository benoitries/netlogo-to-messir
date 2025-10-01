#!/usr/bin/env python3
"""
Convenience entry point to run the NetLogo orchestrator with default settings:
- Model: gpt-5-nano
- Case study: 3d-solids (first case)
- Reasoning effort: low (summary: auto)
- Parallel execution: enabled (uses config flag)

This wrapper avoids interactive prompts and runs a single combination.
"""

import asyncio
import datetime
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from netlogo_orchestrator import NetLogoOrchestrator  # noqa: E402
from config import AGENT_CONFIGS, ENABLE_PARALLEL_FIRST_STAGE  # noqa: E402


async def run_default() -> None:
    """Run orchestrator for 3d-solids with gpt-5-nano and low effort."""
    # Derive a default token configuration from AGENT_CONFIGS
    token_config = {
        agent: cfg.get("max_completion_tokens", 8000) for agent, cfg in AGENT_CONFIGS.items()
    }

    model_name = "gpt-5-nano"
    base_name = "3d-solids"

    orchestrator = NetLogoOrchestrator(model_name=model_name, max_tokens_config=token_config)

    # Apply low reasoning effort globally
    orchestrator.update_reasoning_config("low", "auto")

    # Log current parallel flag for visibility
    print(f"Parallel first stage enabled: {ENABLE_PARALLEL_FIRST_STAGE}")

    # Kick off the run (start_step defaults to 1)
    results = await orchestrator.run(base_name)

    # Minimal success signal
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ok = bool(results)
    print(f"[{ts}] Default nano run completed. Success: {ok}")


def main() -> None:
    asyncio.run(run_default())


if __name__ == "__main__":
    main()


