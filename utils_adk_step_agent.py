#!/usr/bin/env python3
"""
ADK Step Agent Utility
Custom ADK agent that wraps AgentStepAdapter for ADK workflow integration.
"""

from typing import Any
from google.adk.agents import BaseAgent


class ADKStepAgent(BaseAgent):
    """
    Custom ADK agent that wraps AgentStepAdapter for ADK workflow integration.
    
    This agent executes an AgentStepAdapter, allowing existing agent methods
    to be orchestrated using ADK's agent structure while maintaining manual execution control.
    
    Uses object.__setattr__ to bypass Pydantic validation for custom attributes.
    """
    def __init__(self, step_adapter: 'AgentStepAdapter', name: str, description: str, **kwargs):
        """Initialize the ADK step agent with an adapter."""
        super().__init__(name=name, description=description, **kwargs)
        object.__setattr__(self, 'step_adapter', step_adapter)
        object.__setattr__(self, '_args', None)
        object.__setattr__(self, '_kwargs', None)
        # Store logger reference if available from orchestrator
        if hasattr(step_adapter, 'orchestrator') and hasattr(step_adapter.orchestrator, 'logger'):
            object.__setattr__(self, '_logger', step_adapter.orchestrator.logger)
        else:
            object.__setattr__(self, '_logger', None)
    
    def set_args(self, *args, **kwargs):
        """Set arguments to pass to the step adapter when executed."""
        object.__setattr__(self, '_args', args)
        object.__setattr__(self, '_kwargs', kwargs)
    
    async def _run_async_impl(self, ctx) -> Any:
        """Execute the step adapter asynchronously."""
        args = getattr(self, '_args', None) or ()
        kwargs_dict = getattr(self, '_kwargs', None) or {}
        
        step_adapter = getattr(self, 'step_adapter', None)
        if step_adapter is None:
            raise RuntimeError("ADKStepAgent: step_adapter not initialized")
        
        logger = getattr(self, '_logger', None)
        if logger:
            logger.debug(f"[ADK] ADKStepAgent._run_async_impl() called for {self.name}")
        
        result = await step_adapter.execute(*args, **kwargs_dict)
        
        if logger:
            logger.debug(f"[ADK] ADKStepAgent._run_async_impl() completed for {self.name}")
        
        return result

