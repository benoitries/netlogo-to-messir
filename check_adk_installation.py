#!/usr/bin/env python3
"""
Quick script to verify Google ADK installation.

Run this before using orchestrator_persona_v3_adk.py to ensure ADK is properly installed.
"""

import sys

def check_adk():
    """Check if Google ADK is properly installed."""
    print("Checking Google ADK installation...")
    print("=" * 60)
    
    # Check 1: Basic import
    try:
        from google.adk.agents import SequentialAgent, BaseAgent
        print("✓ ADK agents module imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import ADK agents: {e}")
        print("\nTo install ADK, run:")
        print("  pip install \"google-adk>=1.12.0\"")
        return False
    
    # Check 2: Check version
    try:
        import google.adk
        version = getattr(google.adk, '__version__', 'unknown')
        print(f"✓ ADK version: {version}")
    except Exception as e:
        print(f"⚠ Could not determine ADK version: {e}")
    
    # Check 3: Verify SequentialAgent
    try:
        from google.adk.agents import SequentialAgent
        print("✓ SequentialAgent class available")
    except Exception as e:
        print(f"✗ SequentialAgent not available: {e}")
        return False
    
    # Check 4: Verify BaseAgent
    try:
        from google.adk.agents import BaseAgent
        print("✓ BaseAgent class available")
    except Exception as e:
        print(f"✗ BaseAgent not available: {e}")
        return False
    
    # Check 5: Verify tools (optional but recommended)
    try:
        from google.adk.tools import google_search
        print("✓ ADK tools (google_search) available")
    except ImportError:
        print("⚠ ADK tools (google_search) not available (optional)")
    
    print("=" * 60)
    print("✓ Google ADK is properly installed and ready to use!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = check_adk()
    sys.exit(0 if success else 1)

