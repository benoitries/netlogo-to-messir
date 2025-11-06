#!/usr/bin/env python3
"""
Test script for orchestrator_persona_v3_adk.py
Tests the ADK-integrated orchestrator with basic functionality checks.

Requires Google ADK to be installed. No fallback if ADK is not available.
"""

import sys
import asyncio
import pathlib
from utils_orchestrator_v3_agent_config import update_agent_configs

# Verify ADK is available first
print("Testing ADK availability...")
try:
    from google.adk.agents import BaseAgent
    print("✓ Google ADK is available")
except ImportError as e:
    print(f"✗ Google ADK is not available: {e}")
    print("\nError: This orchestrator requires Google ADK to be installed.")
    print("Install it with: pip install \"google-adk>=1.12.0\"")
    sys.exit(1)

# Test orchestrator imports
print("Testing orchestrator imports...")
try:
    from orchestrator_persona_v3_adk import NetLogoOrchestratorPersonaV3ADK
    print("✓ Orchestrator imports successful")
except Exception as e:
    print(f"✗ Orchestrator import failed: {e}")
    sys.exit(1)

async def test_orchestrator_adk():
    """Test basic orchestrator ADK functionality."""
    
    print("=" * 60)
    print("Testing Orchestrator Persona V3 ADK")
    print("=" * 60)
    print("ADK: Required and available")
    print()
    
    # Test 1: Initialization
    print("Test 1: Initializing orchestrator...")
    try:
        orchestrator = NetLogoOrchestratorPersonaV3ADK(model_name="gpt-5-mini")
        print("✓ Orchestrator initialized successfully")
        print(f"  - Model: {orchestrator.model}")
        print(f"  - Persona Set: {orchestrator.persona_set}")
        print()
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Agent initialization
    print("Test 2: Checking agent initialization...")
    try:
        agents = [
            ("LUCIM Operation Model Generator", orchestrator.lucim_operation_model_generator_agent),
            ("LUCIM Scenario Generator", orchestrator.lucim_scenario_generator_agent),
            ("PlantUML Diagram Generator", orchestrator.lucim_plantuml_diagram_generator_agent),
            ("PlantUML Diagram Auditor", orchestrator.lucim_plantuml_diagram_auditor_agent),
        ]
        
        for name, agent in agents:
            if agent is None:
                print(f"✗ {name} agent is None")
                return False
            print(f"  ✓ {name} initialized")
        print()
    except Exception as e:
        print(f"✗ Agent initialization check failed: {e}")
        return False
    
    # Test 3: Configuration updates
    print("Test 3: Testing configuration updates...")
    try:
        update_agent_configs(orchestrator, reasoning_effort="high", reasoning_summary="auto", text_verbosity="high")
        print("✓ Configuration updates successful")
        print()
    except Exception as e:
        print(f"✗ Configuration update failed: {e}")
        return False
    
    # Test 4: Persona path initialization
    print("Test 4: Checking persona path initialization...")
    try:
        if hasattr(orchestrator, 'netlogo_lucim_mapping_path'):
            if orchestrator.netlogo_lucim_mapping_path.exists():
                print(f"✓ NetLogo-LUCIM mapping file found: {orchestrator.netlogo_lucim_mapping_path}")
            else:
                print(f"⚠ NetLogo-LUCIM mapping file not found: {orchestrator.netlogo_lucim_mapping_path}")
        print()
    except Exception as e:
        print(f"⚠ Persona path check warning: {e}")
        print()
    
    # Test 5: ADK structure verification
    print("Test 5: Testing ADK integration structure...")
    try:
        from google.adk.agents import BaseAgent
        from orchestrator_persona_v3_adk import ADKStepAgent
        print("✓ ADK imports successful")
        print("✓ ADKStepAgent class available")
        print("✓ ADK integration structure ready")
        print()
    except Exception as e:
        print(f"✗ ADK structure check failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 6: File I/O utilities
    print("Test 6: Checking file I/O utilities...")
    try:
        fileio = orchestrator.fileio
        if fileio is None:
            print("✗ FileIO utility is None")
            return False
        print("✓ FileIO utility initialized")
        print()
    except Exception as e:
        print(f"✗ File I/O utility check failed: {e}")
        return False
    
    print("=" * 60)
    print("All basic tests passed! ✓")
    print("=" * 60)
    print()
    print("Note: Full integration test requires:")
    print("  1. Google ADK installed (✓ verified)")
    print("  2. Valid NetLogo input files")
    print("  3. Valid OpenAI API key")
    print("  4. All persona files in place")
    print()
    print("To verify ADK installation separately, run:")
    print("  python check_adk_installation.py")
    print()
    print("To run full integration test, use:")
    print("  python orchestrator_persona_v3_adk.py")
    print()
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_orchestrator_adk())
    sys.exit(0 if success else 1)

