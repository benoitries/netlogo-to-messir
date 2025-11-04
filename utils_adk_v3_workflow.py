#!/usr/bin/env python3
"""
ADK Workflow Utilities for Persona V3 Orchestrator
Provides utilities for integrating Google ADK workflow agents with the v3 pipeline.
"""

import time
import logging
from typing import Dict, Any, Optional, Callable, List
from functools import wraps

logger = logging.getLogger(__name__)


class ADKWorkflowWrapper:
    """
    Wrapper to integrate existing agent methods with ADK workflow patterns.
    
    This wrapper allows existing agent methods to be used within ADK workflows
    while maintaining backward compatibility with existing timing and token tracking.
    """
    
    def __init__(self, agent_instance, method_name: str, agent_name: str):
        """
        Initialize the wrapper.
        
        Args:
            agent_instance: Instance of an agent (e.g., NetLogoLucimEnvironmentSynthesizerAgent)
            method_name: Name of the method to wrap (e.g., 'synthesize_lucim_operation_from_source_code')
            agent_name: Name for tracking (e.g., 'lucim_operation_synthesizer')
        """
        self.agent_instance = agent_instance
        self.method = getattr(agent_instance, method_name)
        self.agent_name = agent_name
        
    async def execute_async(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Execute the wrapped method asynchronously.
        
        Args:
            *args, **kwargs: Arguments to pass to the wrapped method
            
        Returns:
            Dictionary containing the result with timing and token information
        """
        start_time = time.time()
        
        try:
            # Execute the method (may be sync or async)
            if hasattr(self.method, '__await__'):
                result = await self.method(*args, **kwargs)
            else:
                result = self.method(*args, **kwargs)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Ensure result is a dict with expected structure
            if not isinstance(result, dict):
                result = {"data": result}
            
            # Add timing information
            result["_timing"] = {
                "start": start_time,
                "end": end_time,
                "duration": duration
            }
            
            # Extract token usage if available
            if isinstance(result, dict):
                result["_token_usage"] = {
                    "used": result.get("tokens_used", 0),
                    "input_tokens": result.get("input_tokens", 0),
                    "output_tokens": result.get("output_tokens", 0),
                    "reasoning_tokens": result.get("reasoning_tokens", 0)
                }
            
            return result
            
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            
            logger.error(f"Error executing {self.agent_name}: {e}")
            return {
                "agent_type": self.agent_name,
                "reasoning_summary": f"{self.agent_name} failed: {str(e)}",
                "data": None,
                "errors": [f"{self.agent_name} error: {str(e)}"],
                "_timing": {
                    "start": start_time,
                    "end": end_time,
                    "duration": duration
                },
                "_token_usage": {
                    "used": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_tokens": 0
                }
            }


def create_workflow_step_wrapper(agent_instance, method_name: str, agent_name: str):
    """
    Create a workflow step wrapper for an agent method.
    
    Args:
        agent_instance: Instance of an agent
        method_name: Name of the method to wrap
        agent_name: Name for tracking
        
    Returns:
        ADKWorkflowWrapper instance
    """
    return ADKWorkflowWrapper(agent_instance, method_name, agent_name)


def extract_timing_from_result(result: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract timing information from a workflow result.
    
    Args:
        result: Result dictionary that may contain _timing information
        
    Returns:
        Dictionary with timing information (start, end, duration)
    """
    timing = result.get("_timing", {})
    return {
        "start": timing.get("start", 0),
        "end": timing.get("end", 0),
        "duration": timing.get("duration", 0)
    }


def extract_token_usage_from_result(result: Dict[str, Any]) -> Dict[str, int]:
    """
    Extract token usage information from a workflow result.
    
    Args:
        result: Result dictionary that may contain _token_usage information
        
    Returns:
        Dictionary with token usage information
    """
    token_usage = result.get("_token_usage", {})
    return {
        "used": token_usage.get("used", 0),
        "input_tokens": token_usage.get("input_tokens", 0),
        "output_tokens": token_usage.get("output_tokens", 0),
        "reasoning_tokens": token_usage.get("reasoning_tokens", 0)
    }


def condition_check_audit_result(processed_results: Dict[str, Any]) -> bool:
    """
    Check if correction step is needed based on audit result.
    
    Args:
        processed_results: Dictionary containing all processed results
        
    Returns:
        True if correction step should be executed (audit verdict is non-compliant)
    """
    auditor_result = processed_results.get("plantuml_lucim_auditor", {})
    if not auditor_result:
        return False
    
    data = auditor_result.get("data", {})
    if not isinstance(data, dict):
        return False
    
    verdict = data.get("verdict")
    return verdict == "non-compliant"


def condition_check_corrector_result(processed_results: Dict[str, Any]) -> bool:
    """
    Check if final audit step is needed based on corrector result.
    
    Args:
        processed_results: Dictionary containing all processed results
        
    Returns:
        True if final audit step should be executed (corrector has results)
    """
    corrector_result = processed_results.get("plantuml_lucim_corrector", {})
    return corrector_result and corrector_result.get("data") is not None

