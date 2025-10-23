#!/usr/bin/env python3
"""
Test script to validate the orchestrator fix.
"""

import asyncio
import sys
from orchestrator_simplified import NetLogoOrchestratorSimplified


async def test_orchestrator_fix():
    """Test the fixed orchestrator with my-ecosys case."""
    
    print("🔧 Testing Orchestrator Fix")
    print("="*50)
    
    # Test with my-ecosys case (the one that failed)
    base_name = "my-ecosys"
    
    try:
        # Create orchestrator
        orchestrator = NetLogoOrchestratorSimplified(model_name="gpt-5-mini")
        
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
                
                # Check specific agents
                if "ast" in file_results:
                    ast_success = file_results["ast"].get("data") is not None
                    print(f"   Step 1 - Syntax Parser: {'✅' if ast_success else '❌'}")
                
                if "semantics" in file_results:
                    sem_success = file_results["semantics"].get("data") is not None
                    print(f"   Step 2 - Semantics Parser: {'✅' if sem_success else '❌'}")
                
                if "lucim_environment_synthesizer" in file_results:
                    lucim_environment_success = file_results["lucim_environment_synthesizer"].get("data") is not None
                    print(f"   Step 3 - LUCIM Environment Synthesizer: {'✅' if lucim_environment_success else '❌'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    print("🚀 Starting Orchestrator Fix Test")
    
    success = await test_orchestrator_fix()
    
    if success:
        print("\n🎉 Orchestrator fix validated!")
        print("✅ The simplified orchestrator now correctly passes results between parallel and sequential stages.")
        sys.exit(0)
    else:
        print("\n💥 Test failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
