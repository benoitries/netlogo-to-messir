#!/usr/bin/env python3
"""
OpenAI API Key Management Utility
Centralized handling of OpenAI API keys with automatic .env loading and validation
"""

import os
import sys
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv

# Try to import OpenAI, but don't fail if not available
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = object  # type: ignore


def load_env_files() -> None:
    """
    Load environment variables from multiple .env file locations.
    
    Searches for .env files in:
    1. Current working directory
    2. Code directory (where this file is located)
    3. Parent directory of code directory
    4. Project root (parent of parent)
    
    Stops loading once a valid API key is found.
    """
    # Get the directory where this utility is located
    code_dir = Path(__file__).parent
    
    # List of potential .env file locations
    env_locations = [
        Path.cwd(),  # Current working directory
        code_dir,    # Code directory
        code_dir.parent,  # Parent directory
        code_dir.parent.parent,  # Project root
    ]
    
    # Load .env files from all locations
    for location in env_locations:
        env_file = location / '.env'
        if env_file.exists():
            load_dotenv(env_file)
            print(f"✓ Loaded environment variables from: {env_file}")
            
            # Check if we have a valid API key after loading this file
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key and api_key.startswith('sk-'):
                print(f"✓ Found valid API key, stopping search")
                break


def get_openai_api_key() -> str:
    """
    Get OpenAI API key with automatic .env loading and validation.
    
    Returns:
        str: The OpenAI API key
        
    Raises:
        ValueError: If no API key is found or if validation fails
    """
    # Clear any existing environment variable to avoid conflicts
    if 'OPENAI_API_KEY' in os.environ:
        del os.environ['OPENAI_API_KEY']
    
    # Load environment variables from .env files
    load_env_files()
    
    # Try multiple environment variable names
    api_key = (
        os.getenv('OPENAI_API_KEY') or 
        os.getenv('OPENAI_KEY') or 
        os.getenv('API_KEY')
    )
    
    if not api_key:
        raise ValueError(
            "No OpenAI API key found. Please create a .env file with:\n"
            "OPENAI_API_KEY=your-api-key-here\n\n"
            "The .env file should be placed in one of these locations:\n"
            f"- {Path.cwd() / '.env'}\n"
            f"- {Path(__file__).parent / '.env'}\n"
            f"- {Path(__file__).parent.parent / '.env'}"
        )
    
    # Clean up the API key (remove export statements, quotes, etc.)
    api_key = clean_api_key(api_key)
    
    # Basic format validation
    if not api_key.startswith('sk-'):
        print("⚠️  Warning: API key doesn't start with 'sk-' - this might not be a valid OpenAI API key")
    
    return api_key


def clean_api_key(raw_key: str) -> str:
    """
    Clean up API key by removing common formatting issues.
    
    Args:
        raw_key: Raw API key string that might contain export statements, quotes, etc.
        
    Returns:
        str: Cleaned API key
    """
    key = raw_key.strip()
    
    # Remove leading export statements
    if key.lower().startswith("export "):
        key = key[len("export "):].strip()
    
    # If provided as KEY=VALUE, split and take the value part
    if "=" in key:
        parts = key.split("=", 1)
        # If the left side looks like the key name, use right side
        if parts[0].strip().upper() in {"OPENAI_API_KEY", "API_KEY", "KEY"}:
            key = parts[1].strip()
    
    # Strip surrounding quotes
    if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
        key = key[1:-1].strip()
    
    # Remove command substitution syntax $(...) and similar
    if key.startswith("$(") and key.endswith(")"):
        key = key[2:-1].strip()
    
    # Handle macOS security command patterns
    if "security find-generic-password" in key:
        print("⚠️  Warning: Found macOS security command in API key")
        print("   This suggests the .env file contains a security command instead of the actual key")
        print("   Please replace with the actual API key value")
        # Try to extract the actual key by executing the security command
        try:
            import subprocess
            # Extract the security command and execute it
            if key.startswith("security "):
                result = subprocess.run(key.split(), capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    key = result.stdout.strip()
                    print(f"   ✓ Successfully retrieved key from macOS keychain")
                else:
                    print(f"   ❌ Failed to retrieve key from keychain: {result.stderr}")
        except Exception as e:
            print(f"   ❌ Error executing security command: {e}")
    
    # Remove security command patterns
    if key.startswith("$(security ") and key.endswith('" -w'):
        # Extract the actual key from security command
        key = key[len("$(security "):-len('" -w')].strip()
    
    # Handle complex export patterns like "export OPENAI_API_KEY=sk-..." -w)"
    if " -w)" in key:
        key = key.split(" -w)")[0].strip()
    
    # Final cleanup of stray characters like trailing parentheses, semicolons, quotes
    key = key.strip().strip(";").strip(")").strip('"').strip("'")
    
    return key


def validate_openai_key(api_key: Optional[str] = None) -> bool:
    """
    Validate OpenAI API key with a test API call.
    
    Args:
        api_key: Optional API key to validate. If None, will load from environment.
        
    Returns:
        bool: True if key is valid and API is accessible, False otherwise
    """
    if not OPENAI_AVAILABLE:
        print("❌ OpenAI package not available. Install with: pip install openai")
        return False
    
    try:
        # Get API key if not provided
        if api_key is None:
            api_key = get_openai_api_key()
        
        # Create client and test with minimal API call
        client = OpenAI(api_key=api_key)
        
        print("🔄 Testing OpenAI API key...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=1
        )
        
        print("✅ OpenAI API key validation successful")
        return True
        
    except Exception as e:
        print(f"❌ OpenAI API key validation failed: {e}")
        print("Please check your API key and try again")
        return False


def create_openai_client() -> OpenAI:
    """
    Create an OpenAI client with automatic API key loading and validation.
    
    Returns:
        OpenAI: Configured OpenAI client
        
    Raises:
        ValueError: If API key is not found or invalid
        ImportError: If OpenAI package is not installed
    """
    if not OPENAI_AVAILABLE:
        raise ImportError(
            "OpenAI package not available. Install with: pip install openai"
        )
    
    api_key = get_openai_api_key()
    return OpenAI(api_key=api_key)


def check_env_setup() -> bool:
    """
    Check if the environment is properly set up for OpenAI API usage.
    
    Returns:
        bool: True if environment is properly configured, False otherwise
    """
    print("🔍 Checking OpenAI API environment setup...")
    
    # Check if OpenAI package is available
    if not OPENAI_AVAILABLE:
        print("❌ OpenAI package not installed")
        print("   Install with: pip install openai")
        return False
    
    # Check if API key is available
    try:
        api_key = get_openai_api_key()
        print(f"✅ API key found: {api_key[:8]}...{api_key[-4:]}")
    except ValueError as e:
        print(f"❌ API key not found: {e}")
        return False
    
    # Validate the API key
    if not validate_openai_key(api_key):
        return False
    
    print("✅ Environment setup complete!")
    return True


def main():
    """Command-line interface for API key management."""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "validate":
            success = check_env_setup()
            sys.exit(0 if success else 1)
        
        elif command == "test":
            try:
                client = create_openai_client()
                print("✅ OpenAI client created successfully")
            except Exception as e:
                print(f"❌ Failed to create OpenAI client: {e}")
                sys.exit(1)
        
        else:
            print(f"Unknown command: {command}")
            print("Available commands: validate, test")
            sys.exit(1)
    else:
        # Default: check environment setup
        success = check_env_setup()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
