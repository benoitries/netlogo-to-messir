#!/usr/bin/env python3
"""
Integration test script for orchestrator_persona_v3_adk.py
Tests the full ADK-integrated orchestrator with a real NetLogo file.

Requires Google ADK and all dependencies to be installed.
"""

import asyncio
import sys
import pathlib
from orchestrator_persona_v3_adk import NetLogoOrchestratorPersonaV3ADK
from utils_orchestrator_v3_agent_config import update_agent_configs


async def test_integration_adk():
    """Run full integration test of the ADK orchestrator."""
    
    print("🧪 Integration Test: Orchestrator Persona V3 ADK")
    print("=" * 60)
    print()
    
    # Test with a simple case (quick test)
    base_name = "3d-solids"  # Use a known case with smaller codebase
    
    try:
        # Ensure input directories point to experimentation single source of truth
        try:
            repo_root = pathlib.Path(__file__).resolve().parents[1]
            import os
            os.environ.setdefault("INPUT_PERSONA_DIR", str(repo_root / "experimentation" / "input" / "input-persona"))
            os.environ.setdefault("INPUT_NETLOGO_DIR", str(repo_root / "experimentation" / "input" / "input-netlogo"))
            os.environ.setdefault("INPUT_VALID_EXAMPLES_DIR", str(repo_root / "experimentation" / "input" / "input-valid-examples"))
        except Exception as e:
            print(f"⚠ Warning setting up input directories: {e}")
            print()
        
        print(f"📁 Processing base name: {base_name}")
        print(f"🔧 Model: gpt-5-mini (for faster testing)")
        print(f"⚙️  Reasoning: low (for faster testing)")
        print(f"📝 Verbosity: medium")
        print()
        
        # Create orchestrator
        orchestrator = NetLogoOrchestratorPersonaV3ADK(model_name="gpt-5-mini")
        
        # Configure for low effort to speed up testing
        update_agent_configs(orchestrator, reasoning_effort="low", reasoning_summary="auto", text_verbosity="medium")
        
        print(f"✅ Orchestrator created successfully")
        print(f"📁 Persona set: {orchestrator.persona_set}")
        print()
        print("Starting full pipeline execution...")
        print("-" * 60)
        print()
        
        # Run the orchestrator
        results = await orchestrator.run(base_name)
        
        print()
        print("-" * 60)
        print("✅ Integration test completed!")
        print()
        print("📊 Results summary:")
        
        if "error" in results:
            print(f"❌ Error: {results['error']}")
            return False
        
        # Check which steps executed
        # Results are stored in processed_results dictionary
        processed_results = results.get("results", {}).get(base_name, results)
        
        steps_completed = []
        steps_failed = []
        
        if processed_results.get("lucim_operation_model_generator"):
            steps_completed.append("Step 1: LUCIM Operation Model Generator")
        else:
            steps_failed.append("Step 1: LUCIM Operation Model Generator")
        
        if processed_results.get("lucim_scenario_generator"):
            steps_completed.append("Step 2: LUCIM Scenario Generator")
        else:
            steps_failed.append("Step 2: LUCIM Scenario Generator")
        
        if processed_results.get("lucim_plantuml_diagram_generator"):
            steps_completed.append("Step 3: LUCIM PlantUML Diagram Generator")
        else:
            steps_failed.append("Step 3: LUCIM PlantUML Diagram Generator")
        
        if processed_results.get("lucim_plantuml_diagram_auditor"):
            steps_completed.append("Step 4: PlantUML LUCIM Auditor")
        else:
            steps_failed.append("Step 4: PlantUML LUCIM Auditor")
        
        # v3 pipeline: no corrector/final auditor
        
        print()
        print(f"✅ Steps completed ({len(steps_completed)}):")
        for step in steps_completed:
            print(f"   {step}")
        
        if steps_failed:
            print()
            print(f"❌ Steps failed ({len(steps_failed)}):")
            for step in steps_failed:
                print(f"   {step}")
            return False
        
        # Show timing information
        execution_times = processed_results.get("execution_times", results.get("execution_times", {}))
        if execution_times:
            print()
            print("⏱️  Execution times:")
            total = execution_times.get("total_orchestration", 0)
            print(f"   Total orchestration: {total:.2f}s")
            for step_name, step_time in execution_times.items():
                if step_name != "total_orchestration" and step_time > 0:
                    print(f"   {step_name}: {step_time:.2f}s")
        
        # Show ADK metrics if available
        adk_metrics = processed_results.get("adk_metrics", results.get("adk_metrics", {}))
        if adk_metrics:
            print()
            print("📈 ADK Monitoring Metrics:")
            total_agents = adk_metrics.get("total_agents_executed", 0)
            successful = adk_metrics.get("successful_executions", 0)
            failed = adk_metrics.get("failed_executions", 0)
            print(f"   Agents executed: {total_agents}")
            print(f"   Successful: {successful}")
            print(f"   Failed: {failed}")
            if adk_metrics.get("total_retries", 0) > 0:
                print(f"   Retries: {adk_metrics.get('total_retries', 0)}")
        
        print()
        print("=" * 60)
        print("✅ Integration test PASSED!")
        print("=" * 60)
        
        return True
        
    except KeyboardInterrupt:
        print()
        print("⚠️  Test interrupted by user")
        return False
    except Exception as e:
        print()
        print(f"❌ Integration test FAILED with error:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_integration_adk())
    sys.exit(0 if success else 1)

