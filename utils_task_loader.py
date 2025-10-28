#!/usr/bin/env python3
"""
Task Loading Utilities for Agents
Provides centralized task instruction loading for all agents.
"""

import pathlib
from typing import Optional


def load_task_instruction(step: int, agent_name: str = None) -> str:
    """
    Load TASK instruction from the appropriate step file.
    
    Args:
        step: Step number (1-8) for task file selection
        agent_name: Optional agent name for logging context
        
    Returns:
        Formatted task instruction string (empty if not found)
    """
    task_content = ""
    
    try:
        # Get the directory containing the current agent file
        # This assumes the utility is imported from an agent file
        current_dir = pathlib.Path(__file__).parent
        
        # Construct task file path
        task_file = current_dir / "input-task" / f"step-{step}-task"
        
        if task_file.exists():
            task_content = task_file.read_text(encoding="utf-8").strip()
            if task_content:
                task_content = f"\n\n{task_content}\n"
                if agent_name:
                    print(f"[INFO] Loaded TASK instruction for {agent_name} (step {step})")
            else:
                if agent_name:
                    print(f"[WARNING] Empty TASK file for {agent_name}: step-{step}-task")
        else:
            if agent_name:
                print(f"[WARNING] TASK file not found for {agent_name}: step-{step}-task")
    except Exception as e:
        if agent_name:
            print(f"[WARNING] Failed to load TASK file for {agent_name}: {e}")
    
    return task_content
