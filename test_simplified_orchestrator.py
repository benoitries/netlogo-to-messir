#!/usr/bin/env python3
"""
Legacy simplified orchestrator test replaced to use Orchestrator V3 ADK.
"""

import asyncio
import sys
from orchestrator_persona_v3_adk import NetLogoOrchestratorPersonaV3ADK
from utils_orchestrator_v3_agent_config import update_agent_configs


async def test_v3_adk_orchestrator():
    """Smoke test for the V3 ADK orchestrator with a basic case."""
    
    print("🧪 Testing Orchestrator V3 ADK")
    print("="*50)
    
    # Test with a simple case
    base_name = "3d-solids"  # Use a known case
    
    try:
        # Create orchestrator with persona set to avoid interactive prompt
        orchestrator = NetLogoOrchestratorPersonaV3ADK(model_name="gpt-5-mini")
        
        # Configure for low effort to speed up testing
        update_agent_configs(orchestrator, reasoning_effort="low", reasoning_summary="auto", text_verbosity="medium")
        
        print(f"✅ Orchestrator created successfully")
        print(f"📁 Processing base name: {base_name}")
        
        # Run the orchestrator
        results = await orchestrator.run(base_name)
        
        print(f"✅ Orchestration completed")
        print(f"📊 Results: {len(results.get('results', {}))} files processed")
        
        # Check if we have results
        if results.get("results"):
            for file_name, file_results in results["results"].items():
                print(f"📄 {file_name}: {len(file_results)} agents")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    print("🚀 Starting Orchestrator V3 ADK Test")
    
    success = await test_v3_adk_orchestrator()
    
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
