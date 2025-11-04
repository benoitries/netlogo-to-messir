#!/usr/bin/env python3
"""
ADK Monitoring and Observability Utilities for Persona V3 Orchestrator
Provides utilities for ADK monitoring, observability, and performance tracking.
"""

import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ADKMonitor:
    """
    Monitoring and observability tracker for ADK workflows.
    
    Tracks performance metrics, error rates, and provides observability
    for the ADK-integrated orchestrator.
    """
    
    def __init__(self, external_logger: Optional[logging.Logger] = None):
        """
        Initialize the ADK monitor.
        
        Args:
            external_logger: Optional logger instance to use for logging (e.g., orchestrator logger)
        """
        self.metrics = {
            "agent_executions": {},
            "error_counts": {},
            "retry_counts": {},
            "total_durations": {},
            "success_rates": {},
        }
        self.start_time = None
        self.end_time = None
        self.external_logger = external_logger or logger
        
    def start_monitoring(self):
        """Start monitoring session."""
        self.start_time = time.time()
        self.external_logger.info("[ADK] Monitoring session started")
    
    def stop_monitoring(self):
        """Stop monitoring session and calculate final metrics."""
        self.end_time = time.time()
        duration = self.end_time - self.start_time if self.start_time else 0
        self.external_logger.info(f"[ADK] Monitoring session stopped (duration: {duration:.2f}s)")
        return duration
    
    def record_agent_execution(self, agent_name: str, duration: float, success: bool, retry_count: int = 0):
        """
        Record an agent execution metric.
        
        Args:
            agent_name: Name of the agent
            duration: Execution duration in seconds
            success: Whether the execution was successful
            retry_count: Number of retries performed
        """
        if agent_name not in self.metrics["agent_executions"]:
            self.metrics["agent_executions"][agent_name] = {
                "count": 0,
                "successes": 0,
                "failures": 0,
                "total_duration": 0,
                "avg_duration": 0,
                "min_duration": float('inf'),
                "max_duration": 0,
            }
        
        exec_metrics = self.metrics["agent_executions"][agent_name]
        exec_metrics["count"] += 1
        exec_metrics["total_duration"] += duration
        
        if duration < exec_metrics["min_duration"]:
            exec_metrics["min_duration"] = duration
        if duration > exec_metrics["max_duration"]:
            exec_metrics["max_duration"] = duration
        
        if success:
            exec_metrics["successes"] += 1
        else:
            exec_metrics["failures"] += 1
            
        exec_metrics["avg_duration"] = exec_metrics["total_duration"] / exec_metrics["count"]
        
        # Log execution to external logger
        status = "SUCCESS" if success else "FAILED"
        retry_info = f" (retries: {retry_count})" if retry_count > 0 else ""
        self.external_logger.info(
            f"[ADK] Agent execution recorded: {agent_name} - {status} - "
            f"duration: {duration:.2f}s{retry_info}"
        )
        
        # Track retries
        if retry_count > 0:
            if agent_name not in self.metrics["retry_counts"]:
                self.metrics["retry_counts"][agent_name] = 0
            self.metrics["retry_counts"][agent_name] += retry_count
            self.external_logger.info(
                f"[ADK] Retry tracked for {agent_name}: {retry_count} retry(ies) performed"
            )
        
        # Update success rate
        if agent_name not in self.metrics["success_rates"]:
            self.metrics["success_rates"][agent_name] = {"successes": 0, "total": 0}
        
        self.metrics["success_rates"][agent_name]["total"] += 1
        if success:
            self.metrics["success_rates"][agent_name]["successes"] += 1
    
    def record_error(self, agent_name: str, error_type: str, error_message: str):
        """
        Record an error occurrence.
        
        Args:
            agent_name: Name of the agent where error occurred
            error_type: Type/category of error
            error_message: Error message
        """
        if agent_name not in self.metrics["error_counts"]:
            self.metrics["error_counts"][agent_name] = {}
        
        if error_type not in self.metrics["error_counts"][agent_name]:
            self.metrics["error_counts"][agent_name][error_type] = 0
        
        self.metrics["error_counts"][agent_name][error_type] += 1
        
        self.external_logger.warning(
            f"[ADK] Error recorded: {agent_name} - {error_type}: {error_message}"
        )
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all collected metrics.
        
        Returns:
            Dictionary containing metrics summary
        """
        # Calculate totals across all agents
        total_agents_executed = 0
        total_successful = 0
        total_failed = 0
        total_retries = 0
        
        summary = {
            "monitoring_duration": (
                (self.end_time - self.start_time) if self.start_time and self.end_time else 0
            ),
            "agents": {},
        }
        
        for agent_name, exec_metrics in self.metrics["agent_executions"].items():
            success_rate = (
                (exec_metrics["successes"] / exec_metrics["count"] * 100)
                if exec_metrics["count"] > 0 else 0
            )
            
            # Accumulate totals
            total_agents_executed += exec_metrics["count"]
            total_successful += exec_metrics["successes"]
            total_failed += exec_metrics["failures"]
            total_retries += self.metrics["retry_counts"].get(agent_name, 0)
            
            summary["agents"][agent_name] = {
                "executions": exec_metrics["count"],
                "successes": exec_metrics["successes"],
                "failures": exec_metrics["failures"],
                "success_rate": f"{success_rate:.1f}%",
                "avg_duration": f"{exec_metrics['avg_duration']:.2f}s",
                "min_duration": f"{exec_metrics['min_duration']:.2f}s",
                "max_duration": f"{exec_metrics['max_duration']:.2f}s",
                "retries": self.metrics["retry_counts"].get(agent_name, 0),
                "errors": self.metrics["error_counts"].get(agent_name, {}),
            }
        
        # Add global totals to summary
        summary["total_agents_executed"] = total_agents_executed
        summary["successful_executions"] = total_successful
        summary["failed_executions"] = total_failed
        summary["total_retries"] = total_retries
        
        return summary
    
    def log_summary(self):
        """Log metrics summary."""
        summary = self.get_metrics_summary()
        self.external_logger.info("=" * 60)
        self.external_logger.info("[ADK] ADK MONITORING SUMMARY")
        self.external_logger.info("=" * 60)
        self.external_logger.info(f"[ADK] Monitoring Duration: {summary['monitoring_duration']:.2f}s")
        self.external_logger.info(f"[ADK] Total Agents Executed: {summary['total_agents_executed']}")
        self.external_logger.info(f"[ADK] Successful Executions: {summary['successful_executions']}")
        self.external_logger.info(f"[ADK] Failed Executions: {summary['failed_executions']}")
        self.external_logger.info(f"[ADK] Total Retries: {summary['total_retries']}")
        self.external_logger.info(f"[ADK] Agents Monitored: {len(summary['agents'])}")
        self.external_logger.info("")
        
        for agent_name, agent_metrics in summary["agents"].items():
            self.external_logger.info(f"[ADK] Agent: {agent_name}")
            self.external_logger.info(f"[ADK]   Executions: {agent_metrics['executions']}")
            self.external_logger.info(f"[ADK]   Success Rate: {agent_metrics['success_rate']}")
            self.external_logger.info(f"[ADK]   Avg Duration: {agent_metrics['avg_duration']}")
            self.external_logger.info(f"[ADK]   Retries: {agent_metrics['retries']}")
            if agent_metrics['errors']:
                self.external_logger.info(f"[ADK]   Errors: {agent_metrics['errors']}")
            self.external_logger.info("")
        
        self.external_logger.info("=" * 60)


# Global monitor instance (can be shared across orchestrator instances)
_global_monitor = None


def get_global_monitor(external_logger: Optional[logging.Logger] = None) -> ADKMonitor:
    """
    Get or create the global ADK monitor instance.
    
    Args:
        external_logger: Optional logger to use for logging. 
                         If monitor doesn't exist, it will be initialized with this logger.
                         If monitor exists and logger is provided, update its logger.
    """
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = ADKMonitor(external_logger=external_logger)
    elif external_logger is not None:
        # Update logger if monitor already exists
        _global_monitor.external_logger = external_logger
    return _global_monitor


def reset_global_monitor():
    """Reset the global monitor (useful for testing)."""
    global _global_monitor
    _global_monitor = ADKMonitor()

