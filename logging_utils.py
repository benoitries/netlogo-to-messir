#!/usr/bin/env python3
"""
Logging utilities for NetLogo to PlantUML pipeline
Provides centralized logging configuration and file management
"""

import logging
import pathlib
import datetime
from typing import Optional
from config import OUTPUT_DIR

def setup_orchestration_logger(base_name: str, model_name: str, timestamp: str) -> logging.Logger:
    """
    Set up a logger for orchestration execution with file output.
    
    Args:
        base_name: Base name for the output files
        model_name: AI model name used for processing
        timestamp: Timestamp string for the execution
        
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
    
    # Create file handler under per-run/per-case directory
    # New format: output/runs/<YYYY-MM-DD>/<HHMM>/<case-name>/<case>_<timestamp>_<model>_orchestrator.log
    ts = timestamp  # format YYYYMMDD_HHMM
    day_folder = f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}"
    time_folder = ts.split("_")[1]
    run_dir = OUTPUT_DIR / "runs" / day_folder / time_folder / base_name
    run_dir.mkdir(parents=True, exist_ok=True)
    log_filename = f"{base_name}_{timestamp}_{model_name}_orchestrator.log"
    log_file = run_dir / log_filename
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

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
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
