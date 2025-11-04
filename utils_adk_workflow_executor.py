#!/usr/bin/env python3
"""
ADK Workflow Executor Utility
Executes ADK workflow steps sequentially with monitoring.
"""

import time
from typing import List, Tuple

from utils_adk_step_agent import ADKStepAgent


async def execute_adk_workflow_steps(orchestrator_instance, steps: List[Tuple]) -> None:
    """
    Execute ADK workflow steps sequentially.
    
    Args:
        orchestrator_instance: Orchestrator instance
        steps: List of (step_adapter, static_args, options) tuples
    """
    adk_agents = []
    step_args_functions = []
    
    for idx, (step_adapter, static_args, options) in enumerate(steps):
        adk_agent = ADKStepAgent(
            step_adapter,
            name=f"step_{idx+1}_{step_adapter.agent_name}",
            description=f"Pipeline step {idx+1}: {step_adapter.agent_name}"
        )
        
        if options.get("dynamic_args"):
            step_args_functions.append(options["dynamic_args"])
        else:
            captured_args = static_args or []
            step_args_functions.append(lambda captured=captured_args: captured)
        
        adk_agents.append(adk_agent)
    
    orchestrator_instance.logger.info(f"[ADK] Executing workflow using ADK-structured sequential execution...")
    orchestrator_instance.logger.info(f"[ADK] Total steps configured: {len(adk_agents)}")
    
    for idx, adk_agent in enumerate(adk_agents):
        step_num = idx + 1
        orchestrator_instance.logger.info(f"[ADK] Executing step {step_num}/{len(adk_agents)}: {adk_agent.name}")
        
        args_fn = step_args_functions[idx]
        args = args_fn()
        
        adk_agent.set_args(*args)
        orchestrator_instance.logger.info(f"[ADK] Calling ADKStepAgent._run_async_impl() for {adk_agent.name}")
        
        result = await adk_agent.step_adapter.execute(*args)
        
        if result is None:
            orchestrator_instance.logger.info(f"[ADK] Step {step_num} skipped (conditional check returned None)")
            continue
        
        orchestrator_instance.logger.info(f"[ADK] Step {step_num} completed successfully")

