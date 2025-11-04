#!/usr/bin/env python3
"""
NetLogo Orchestrator Agent — Persona V3 (Google ADK Integration)

Coordinates a 6-agent LUCIM pipeline using Google ADK Sequential agents:
1) LUCIM Operation Model Generator → 2) LUCIM Operation Model Auditor →
3) LUCIM Scenario Generator → 4) LUCIM Scenario Auditor →
5) LUCIM PlantUML Diagram Generator → 6) LUCIM PlantUML Diagram Auditor.

Generators perform corrections when their paired Auditor flags non-compliance.
There is no separate Corrector agent. Output layout and artifacts remain backward compatible.

REQUIREMENTS:
- Google ADK must be installed: pip install "google-adk>=1.12.0"
- No fallback mode — this orchestrator requires ADK to function.
"""

import sys
from typing import Dict, Any
import os

# Fail fast on unsupported Python versions
if sys.version_info < (3, 10):
    raise RuntimeError(
        f"Python 3.10+ is required to run this orchestrator. Detected: {sys.version.split()[0]}"
    )

# Import ADK components - fail fast if not available (no fallback)
try:
    import google.adk.agents as _  # noqa: F401
except ImportError as e:
    raise RuntimeError(
        f"Google ADK is required but not available: {e}\n"
        f"Please install it with: pip install \"google-adk>=1.12.0\""
    ) from e

from utils_config_constants import DEFAULT_MODEL, ensure_directories
from utils_orchestrator_ui import OrchestratorUI
from utils_orchestrator_fileio import OrchestratorFileIO
from utils_orchestrator_v3_init import initialize_v3_orchestrator_components
from utils_orchestrator_v3_agent_config import update_agent_configs
from utils_orchestrator_v3_run import run_orchestrator_v3
from utils_orchestrator_v3_process import process_netlogo_file_v3_adk as _process_file
from utils_adk_step_agent import ADKStepAgent

# Ensure all directories exist
ensure_directories()

# Re-export ADKStepAgent for convenience
__all__ = ['NetLogoOrchestratorPersonaV3ADK', 'ADKStepAgent']


class NetLogoOrchestratorPersonaV3ADK:
    """
    Persona V3 orchestrator using Google ADK agent structure.

    Orchestrates a 6-agent flow: Operation Model (Gen/Audit), Scenario (Gen/Audit),
    and PlantUML Diagram (Gen/Audit). Generators may apply corrections in-line
    when auditors report non-compliance. Artifacts and output layout remain compatible
    with existing tooling and validators.

    Requires Google ADK to be installed and available.
    """
    
    def __init__(self, model_name: str = DEFAULT_MODEL):
        """Initialize the NetLogo Orchestrator for Persona V3 with ADK support."""
        self.logger = None
        self.orchestrator_logger = None
        self.adk_monitor = None
        self.ui = OrchestratorUI()
        self.fileio = OrchestratorFileIO()
        initialize_v3_orchestrator_components(self, model_name)
        # Iterative correction guard
        try:
            self.max_correction = int(os.getenv("MAX_CORRECTION", "2"))
        except Exception:
            self.max_correction = 2
    
    def update_reasoning_config(self, reasoning_effort: str, reasoning_summary: str):
        """Backward-compatible wrapper to update reasoning across agents."""
        update_agent_configs(self, reasoning_effort=reasoning_effort, reasoning_summary=reasoning_summary)
    
    def update_text_config(self, text_verbosity: str):
        """Backward-compatible wrapper to update text verbosity across agents."""
        update_agent_configs(self, text_verbosity=text_verbosity)
    
    async def process_netlogo_file_v3_adk(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single NetLogo file using ADK Sequential workflow."""
        return await _process_file(self, file_info)
    
    async def run(self, base_name: str) -> Dict[str, Any]:
        """Run the orchestrator for a given base name with v3 pipeline processing."""
        return await run_orchestrator_v3(self, base_name)


if __name__ == "__main__":
    import asyncio
    from utils_orchestrator_v3_main import main
    asyncio.run(main())
