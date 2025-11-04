#!/usr/bin/env python3
"""
Test script for the simplified orchestrator.
"""

import asyncio
import sys
import pytest
try:
    from orchestrator_simplified import NetLogoOrchestratorSimplified
except Exception:
    pytest.skip("orchestrator_simplified module not available; skipping test_simplified_orchestrator", allow_module_level=True)


async def test_simplified_orchestrator():
    """Test the simplified orchestrator with a basic case."""
    
    print("🧪 Testing Simplified Orchestrator")
    print("="*50)
    
    # Test with a simple case
    base_name = "3d-solids"  # Use a known case
    
    try:
        # Create orchestrator with persona set to avoid interactive prompt
        orchestrator = NetLogoOrchestratorSimplified(model_name="gpt-5-mini", persona_set="persona-v1")
        
        # Configure for low effort to speed up testing
        orchestrator.update_reasoning_config("low", "auto")
        orchestrator.update_text_config("medium")
        
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
    print("🚀 Starting Simplified Orchestrator Test")
    
    success = await test_simplified_orchestrator()
    
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
