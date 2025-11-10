#!/usr/bin/env python3
"""
Minimal API key loader

Responsibilities:
- Load environment variables from .env files (few common locations)
- Return API keys for a given model/provider without validation
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv


def _env_locations() -> List[Path]:
    """Return .env file locations in priority order (workspace root first)."""
    code_dir = Path(__file__).parent  # code-netlogo-to-lucim-agentic-workflow/
    workspace_root = code_dir.parent  # Workspace root where .env should be
    return [
        workspace_root,  # PRIORITY 1: Workspace root (where .env should be)
        Path.cwd(),      # Current working directory
        code_dir,        # Code directory
    ]


def load_env_files() -> None:
    """Load .env files from common locations in order (workspace root first, override system env)."""
    seen: set[str] = set()
    locations = _env_locations()
    for i, base in enumerate(locations):
        env_path = (base / ".env").resolve()
        if str(env_path) in seen:
            continue
        seen.add(str(env_path))
        if env_path.exists():
            # First file (workspace root): override=True to override system environment variables
            # Subsequent files: override=False so workspace root wins
            override = (i == 0)
            load_dotenv(env_path, override=override)


def clean_api_key(raw_key: str) -> str:
    """
    Clean up API key by removing common formatting issues.
    
    Simple logic: extract sk-... from anywhere in the string, remove shell fragments.
    """
    if not raw_key:
        return ""
    
    key = raw_key.strip()
    
    # Detect and reject shell commands (security find-generic-password, etc.)
    if key.startswith("$(") or "security find" in key.lower() or "find-generic-password" in key.lower():
        return ""  # Return empty to trigger error message
    
    # Remove "export " prefix if present (handles "export OPENAI_API_KEY=...")
    if key.lower().startswith("export "):
        key = key[7:].strip()  # Remove "export "
    
    # Handle KEY=VALUE format (multiple times if nested)
    while "=" in key:
        parts = key.split("=", 1)
        left = parts[0].strip().upper()
        if left in {"OPENAI_API_KEY", "API_KEY", "KEY", "EXPORT", "EXPORT OPENAI_API_KEY"}:
            key = parts[1].strip()
        else:
            break
    
    # Extract sk-... if present (handles sk-proj-... or sk-...)
    if 'sk-' in key:
        start = key.find('sk-')
        key = key[start:]
        
        # Stop at first whitespace, quote, or paren
        for term in [' ', '\n', '\t', '"', "'", ')', ';']:
            if term in key:
                key = key.split(term)[0]
        
        # Remove trailing shell fragments
        for suffix in [' -w"', ' -w)', ' -w', ')"', '"', ')', '`']:
            if key.endswith(suffix):
                key = key[:-len(suffix)]
        
        key = key.strip()
        if key.startswith('sk-') and len(key) >= 10:
            return key
    
    # Remove quotes
    key = key.strip('"\'`')
    
    # Remove shell fragments
    for suffix in [' -w"', ' -w)', ' -w', ')"', '"', ')', '`']:
        if key.endswith(suffix):
            key = key[:-len(suffix)].strip()
    
    return key.strip()


def get_openai_api_key() -> str:
    """Return OpenAI API key from environment after loading .env files."""
    load_env_files()
    key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY") or os.getenv("API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    # Clean the key to remove any formatting issues
    original_key = key
    key = clean_api_key(key)
    if not key:
        raise ValueError(
            f"OPENAI_API_KEY is invalid. It may contain a shell command instead of the actual key.\n"
            f"Original value starts with: {original_key[:50]}...\n"
            f"Please ensure your .env file contains: OPENAI_API_KEY=sk-proj-... (not a shell command)"
        )
    # Validate: must start with sk-
    if not key.startswith('sk-'):
        raise ValueError(
            f"OPENAI_API_KEY does not start with 'sk-'. Got: {key[:20]}... (first 20 chars)\n"
            f"Original value: {original_key[:50]}...\n"
            f"Please check your .env file at: {_env_locations()[0] / '.env'}"
        )
    return key


def get_provider_for_model(model_name: str) -> str:
    """Infer provider from model name: "openai" | "router"."""
    name = (model_name or "").lower()
    if name.startswith("gpt-5") or name.startswith("gpt-"):
        return "openai"
    # All other models (Gemini, Mistral, Llama, etc.) are routed through OpenRouter
    return "router"


def get_api_key_for_model(model_name: str) -> str:
    """Return API key for the inferred provider (no validation)."""
    load_env_files()
    provider = get_provider_for_model(model_name)
    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY") or os.getenv("API_KEY")
        if key:
            original_key = key
            key = clean_api_key(key)
            # Validate: OpenAI keys must start with sk-
            if key and not key.startswith('sk-'):
                raise ValueError(
                    f"OPENAI_API_KEY does not start with 'sk-'. Got: {key[:20]}... (first 20 chars)\n"
                    f"Original value: {original_key[:50]}...\n"
                    f"Please check your .env file at: {_env_locations()[0] / '.env'}"
                )
    else:
        key = os.getenv("ROUTER_API_KEY") or os.getenv("ROUTER_KEY") or os.getenv("ROUTER") or os.getenv("OPENROUTER_API_KEY")
        if key:
            key = clean_api_key(key)
    if not key:
        raise ValueError(f"No API key found for provider '{provider}'.")
    return key
