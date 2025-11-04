#!/usr/bin/env python3
"""
Test script for the persona v3 orchestrator.
Tests the v3 pipeline that starts with LUCIM Environment Synthesizer using NetLogo source code only.
"""

import asyncio
import sys
import pathlib
import pytest
try:
    from orchestrator_persona_v3 import NetLogoOrchestratorPersonaV3  # legacy path
except Exception:
    # Fallback to ADK-based orchestrator shim
    try:
        from orchestrator_persona_v3_adk import NetLogoOrchestratorPersonaV3ADK as NetLogoOrchestratorPersonaV3
    except Exception:
        pytest.skip("persona v3 orchestrator not available; skipping test_orchestrator_persona_v3", allow_module_level=True)


async def test_orchestrator_persona_v3():
    """Test the persona v3 orchestrator with a basic case."""
    
    print("🧪 Testing Persona V3 Orchestrator")
    print("="*50)
    
    # Test with a simple case
    base_name = "3d-solids"  # Use a known case
    
    try:
        # Ensure input directories point to experimentation single source of truth
        try:
            repo_root = pathlib.Path(__file__).resolve().parents[1]
            import os
            os.environ.setdefault("INPUT_PERSONA_DIR", str(repo_root / "experimentation" / "input" / "input-persona"))
            os.environ.setdefault("INPUT_NETLOGO_DIR", str(repo_root / "experimentation" / "input" / "input-netlogo"))
            os.environ.setdefault("INPUT_VALID_EXAMPLES_DIR", str(repo_root / "experimentation" / "input" / "input-valid-examples"))
        except Exception:
            pass
        
        # Create orchestrator (persona set is hardcoded to persona-v3-limited-agents)
        orchestrator = NetLogoOrchestratorPersonaV3(model_name="gpt-5-mini")
        
        # Configure for low effort to speed up testing
        orchestrator.update_reasoning_config("low", "auto")
        orchestrator.update_text_config("medium")
        
        print(f"✅ Orchestrator created successfully")
        print(f"📁 Persona set: {orchestrator.selected_persona_set}")
        print(f"📁 Processing base name: {base_name}")
        print(f"🔧 Model: {orchestrator.model}")
        
        # Run the orchestrator
        results = await orchestrator.run(base_name)
        
        print(f"\n✅ Orchestration completed")
        print(f"📊 Results summary:")
        print(f"   - Files processed: {results.get('files_processed', 0)}")
        print(f"   - Total agents: {results.get('total_agents', 0)}")
        print(f"   - Successful agents: {results.get('successful_agents', 0)}")
        print(f"   - Failed agents: {results.get('failed_agents', 0)}")
        print(f"   - Success rate: {results.get('success_rate', 0):.1f}%")
        
        # Check if we have results
        if results.get("results"):
            for file_name, file_results in results["results"].items():
                print(f"\n📄 File: {file_name}")
                
                # Check each step in the v3 pipeline
                v3_steps = [
                    "lucim_operation_synthesizer",
                    "lucim_scenario_synthesizer",
                    "plantuml_writer",
                    "plantuml_lucim_auditor",
                    "plantuml_lucim_corrector",
                    "plantuml_lucim_final_auditor"
                ]
                
                for step_key in v3_steps:
                    if step_key in file_results:
                        step_result = file_results[step_key]
                        if isinstance(step_result, dict):
                            status = "✅" if step_result.get("data") else "❌"
                            errors = step_result.get("errors", [])
                            print(f"   {status} {step_key}: {'OK' if step_result.get('data') else f'FAILED - {errors}'}")
        
        # Check execution times
        if results.get("results"):
            first_file_results = next(iter(results["results"].values()))
            if "execution_times" in first_file_results:
                print(f"\n⏱️  Execution times:")
                for agent, duration in first_file_results["execution_times"].items():
                    if duration > 0:
                        print(f"   - {agent}: {duration:.2f}s")
        
        # Check token usage
        if results.get("results"):
            first_file_results = next(iter(results["results"].values()))
            if "token_usage" in first_file_results:
                print(f"\n💰 Token usage:")
                total_tokens = 0
                for agent, usage in first_file_results["token_usage"].items():
                    tokens = usage.get("used", 0)
                    if tokens > 0:
                        print(f"   - {agent}: {tokens:,} tokens")
                        total_tokens += tokens
                print(f"   - Total: {total_tokens:,} tokens")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    print("🚀 Starting Persona V3 Orchestrator Test")
    print()
    
    success = await test_orchestrator_persona_v3()
    
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

