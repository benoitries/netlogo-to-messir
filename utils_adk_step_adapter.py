#!/usr/bin/env python3
"""
ADK Step Adapter Utility
Adapter to wrap existing agent methods as ADK-compatible workflow steps.
"""

import time
import pathlib
import inspect
from typing import Dict, Any, Optional, Callable

from utils_adk_retry import execute_with_retry


class AgentStepAdapter:
    """
    Adapter to wrap existing agent methods as ADK-compatible workflow steps.
    
    This adapter allows existing agent methods to be executed within ADK workflows
    while maintaining all tracking, logging, and file operations.
    """
    
    def __init__(self, 
                 orchestrator_instance,
                 agent_instance,
                 method_name: str,
                 agent_name: str,
                 step_number: int,
                 base_name: str,
                 model: str,
                 run_dir: pathlib.Path,
                 conditional_check: Optional[Callable] = None):
        """Initialize the adapter."""
        self.orchestrator = orchestrator_instance
        self.agent_instance = agent_instance
        self.method = getattr(agent_instance, method_name)
        self.agent_name = agent_name
        self.step_number = step_number
        self.base_name = base_name
        self.model = model
        self.run_dir = run_dir
        self.conditional_check = conditional_check
        
    async def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """Execute the agent method with full tracking and file operations."""
        if self.conditional_check and not self.conditional_check(self.orchestrator.processed_results):
            self.orchestrator.logger.info(
                f"Skipping Step {self.step_number}: {self.agent_name} for {self.base_name} (condition not met)"
            )
            
            # Create output directory and placeholder file to document the skip
            try:
                agent_output_dir = self.orchestrator.fileio.create_agent_output_directory(
                    self.run_dir, self.step_number, self.agent_name
                )
                
                # Determine skip reason based on agent type
                skip_reason = "condition not met"
                if self.agent_name == "plantuml_lucim_corrector":
                    # Check audit verdict to provide specific reason
                    auditor_result = self.orchestrator.processed_results.get("plantuml_lucim_auditor", {})
                    if auditor_result and auditor_result.get("data", {}).get("verdict") == "compliant":
                        skip_reason = "diagrams already compliant (correction not needed)"
                    else:
                        skip_reason = "audit result not available or not non-compliant"
                elif self.agent_name == "plantuml_lucim_final_auditor":
                    skip_reason = "corrector step was not executed (diagrams were already compliant)"
                
                # Create placeholder file documenting the skip
                placeholder_content = {
                    "step_number": self.step_number,
                    "agent_name": self.agent_name,
                    "status": "skipped",
                    "skip_reason": skip_reason,
                    "base_name": self.base_name,
                    "model": self.model,
                    "timestamp": self.orchestrator.timestamp if hasattr(self.orchestrator, 'timestamp') else None
                }
                
                import json
                placeholder_file = agent_output_dir / "step-skipped.json"
                with open(placeholder_file, 'w', encoding='utf-8') as f:
                    json.dump(placeholder_content, f, indent=2, ensure_ascii=False)
                
                # Also create a human-readable markdown file
                markdown_content = f"""# Step {self.step_number} - {self.agent_name}

## Status: SKIPPED

**Reason:** {skip_reason}

**Base Name:** {self.base_name}

**Model:** {self.model}

**Timestamp:** {placeholder_content.get('timestamp', 'N/A')}

---

This step was conditionally skipped because the required conditions were not met.
"""
                markdown_file = agent_output_dir / "step-skipped.md"
                with open(markdown_file, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                
                self.orchestrator.logger.info(
                    f"[ADK] Created placeholder files in {agent_output_dir.name} documenting step skip"
                )
            except Exception as e:
                self.orchestrator.logger.warning(
                    f"[ADK] Failed to create placeholder files for skipped step {self.step_number}: {e}"
                )
            
            return None
        
        self.orchestrator.logger.info(
            f"Step {self.step_number}: Running {self.agent_name} agent for {self.base_name}..."
        )
        
        start_time = time.time()
        self.orchestrator.detailed_timing[self.agent_name]["start"] = start_time
        self.orchestrator.orchestrator_logger.log_agent_start(self.agent_name)
        
        try:
            agent_output_dir = self.orchestrator.fileio.create_agent_output_directory(
                self.run_dir, self.step_number, self.agent_name
            )
            
            if "output_dir" not in kwargs:
                kwargs["output_dir"] = agent_output_dir
            
            retry_count = 0
            max_retries = self.orchestrator.retry_config.max_retries
            
            self.orchestrator.logger.info(
                f"[ADK] Executing {self.agent_name} with retry configuration: "
                f"max_retries={max_retries}, "
                f"backoff_factor={self.orchestrator.retry_config.backoff_factor}, "
                f"initial_delay={self.orchestrator.retry_config.initial_delay}s"
            )
            
            def on_retry_callback(attempt: int, exception: Exception):
                nonlocal retry_count
                retry_count = attempt
                exception_type = type(exception).__name__
                exception_msg = str(exception)
                
                self.orchestrator.logger.warning(
                    f"[ADK] Retry callback triggered for {self.agent_name}: "
                    f"attempt {attempt}/{max_retries}, "
                    f"exception: {exception_type}: {exception_msg}"
                )
                
                self.orchestrator.adk_monitor.record_error(
                    self.agent_name, exception_type, exception_msg
                )
            
            is_async = inspect.iscoroutinefunction(self.method)
            
            if is_async:
                result = await execute_with_retry(
                    self.method, *args,
                    max_retries=max_retries,
                    backoff_factor=self.orchestrator.retry_config.backoff_factor,
                    initial_delay=self.orchestrator.retry_config.initial_delay,
                    max_delay=self.orchestrator.retry_config.max_delay,
                    on_retry=on_retry_callback,
                    external_logger=self.orchestrator.logger,
                    **kwargs
                )
            else:
                result, retry_count = self._execute_sync_with_retry(*args, on_retry_callback=on_retry_callback, **kwargs)
            
            end_time = time.time()
            duration = end_time - start_time
            self._record_timing(duration, end_time)
            
            if not isinstance(result, dict):
                result = {"data": result}
            
            result["agent_type"] = self.agent_name
            
            tokens_used = result.get("tokens_used", 0)
            input_tokens = result.get("input_tokens", 0)
            output_tokens = result.get("output_tokens", 0)
            reasoning_tokens = result.get("reasoning_tokens", 0)
            self.orchestrator.token_usage[self.agent_name]["used"] = tokens_used
            
            save_method = getattr(self.agent_instance, "save_results", None)
            if save_method:
                save_method(result, self.base_name, self.model, str(self.step_number), output_dir=agent_output_dir)
            
            self.orchestrator.orchestrator_logger.log_agent_completion(
                self.agent_name, duration, tokens_used, input_tokens, output_tokens, reasoning_tokens
            )
            
            self.orchestrator.adk_monitor.record_agent_execution(
                self.agent_name, duration, success=True, retry_count=retry_count
            )
            
            if retry_count > 0:
                self.orchestrator.logger.info(
                    f"[ADK] {self.agent_name} completed successfully after {retry_count} retry attempt(s) "
                    f"(total attempts: {retry_count + 1}, max allowed: {max_retries + 1})"
                )
            else:
                self.orchestrator.logger.debug(
                    f"[ADK] {self.agent_name} completed successfully on first attempt "
                    f"(no retries needed, max allowed: {max_retries + 1})"
                )
            
            self.orchestrator.processed_results[self.agent_name] = result
            return result
            
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            self._record_timing(duration, end_time)
            
            error_result = {
                "agent_type": self.agent_name,
                "reasoning_summary": f"{self.agent_name} failed: {str(e)}",
                "data": None,
                "errors": [f"{self.agent_name} error: {str(e)}"]
            }
            
            self.orchestrator.logger.error(
                f"✗ Step {self.step_number}: {self.agent_name} agent failed for {self.base_name}: {str(e)}"
            )
            self.orchestrator.orchestrator_logger.log_agent_error(self.agent_name, duration, str(e))
            
            self.orchestrator.adk_monitor.record_agent_execution(
                self.agent_name, duration, success=False, retry_count=retry_count
            )
            self.orchestrator.adk_monitor.record_error(
                self.agent_name, type(e).__name__, str(e)
            )
            
            if retry_count > 0:
                self.orchestrator.logger.error(
                    f"[ADK] {self.agent_name} failed after {retry_count} retry attempt(s) "
                    f"(total attempts: {retry_count + 1}, max allowed: {max_retries + 1}). All retries exhausted."
                )
            else:
                self.orchestrator.logger.error(
                    f"[ADK] {self.agent_name} failed on first attempt. "
                    f"No retries were performed (max allowed: {max_retries + 1})"
                )
            
            self.orchestrator.processed_results[self.agent_name] = error_result
            return error_result
    
    def _execute_sync_with_retry(self, *args, on_retry_callback, **kwargs):
        """Execute synchronous method with retry logic. Returns (result, retry_count)."""
        attempt = 0
        sync_max_retries = self.orchestrator.retry_config.max_retries
        
        self.orchestrator.logger.info(
            f"[ADK] Using synchronous retry for {self.agent_name}: "
            f"max_retries={sync_max_retries}, "
            f"initial_delay={self.orchestrator.retry_config.initial_delay}s, "
            f"backoff_factor={self.orchestrator.retry_config.backoff_factor}"
        )
        
        while attempt <= sync_max_retries:
            try:
                if attempt == 0:
                    self.orchestrator.logger.info(
                        f"[ADK] Executing {self.agent_name} (initial attempt, sync method)"
                    )
                else:
                    self.orchestrator.logger.info(
                        f"[ADK] Executing {self.agent_name} (retry attempt {attempt}/{sync_max_retries}, sync method)"
                    )
                
                result = self.method(*args, **kwargs)
                
                if attempt > 0:
                    self.orchestrator.logger.info(
                        f"[ADK] ✓ {self.agent_name} succeeded after {attempt} retry attempt(s) "
                        f"(total attempts: {attempt + 1}, max allowed: {sync_max_retries + 1})"
                    )
                else:
                    self.orchestrator.logger.debug(
                        f"[ADK] ✓ {self.agent_name} succeeded on first attempt "
                        f"(max allowed: {sync_max_retries + 1})"
                    )
                
                return result, attempt
                
            except Exception as e:
                attempt += 1
                exception_type = type(e).__name__
                exception_msg = str(e)
                
                self.orchestrator.logger.warning(
                    f"[ADK] ✗ {self.agent_name} failed on attempt {attempt}/{sync_max_retries + 1} "
                    f"(sync method): {exception_type}: {exception_msg}"
                )
                
                if attempt > sync_max_retries:
                    self.orchestrator.logger.error(
                        f"[ADK] ✗✗ {self.agent_name} exhausted all {sync_max_retries} retry attempts "
                        f"(sync method). Total attempts: {sync_max_retries + 1}. "
                        f"Last error: {exception_type}: {exception_msg}"
                    )
                    raise
                
                delay = min(
                    self.orchestrator.retry_config.initial_delay *
                    (self.orchestrator.retry_config.backoff_factor ** (attempt - 1)),
                    self.orchestrator.retry_config.max_delay
                )
                
                self.orchestrator.logger.warning(
                    f"[ADK] ⟳ Retrying {self.agent_name} in {delay:.2f}s "
                    f"(attempt {attempt + 1}/{sync_max_retries + 1} will be made, sync method). "
                    f"Backoff: {self.orchestrator.retry_config.initial_delay}s * "
                    f"{self.orchestrator.retry_config.backoff_factor}^{attempt - 1} = {delay:.2f}s"
                )
                
                on_retry_callback(attempt, e)
                time.sleep(delay)
        
        raise RuntimeError(f"Unexpected exit from sync retry loop for {self.agent_name}")
    
    def _record_timing(self, duration: float, end_time: float):
        """Record timing information."""
        self.orchestrator.detailed_timing[self.agent_name]["end"] = end_time
        self.orchestrator.detailed_timing[self.agent_name]["duration"] = duration
        self.orchestrator.execution_times[self.agent_name] = duration

