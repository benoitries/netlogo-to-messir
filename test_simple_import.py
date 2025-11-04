#!/usr/bin/env python3
"""
Simple test to verify imports and basic functionality.
"""

def test_imports():
    """Test that all required modules can be imported."""
    try:
        print("🧪 Testing imports...")
        
        # Test orchestrator imports
        from orchestrator_persona_v3_adk import NetLogoOrchestratorPersonaV3ADK, ADKStepAgent
        assert isinstance(NetLogoOrchestratorPersonaV3ADK, type), "NetLogoOrchestratorPersonaV3ADK should be a class"
        assert isinstance(ADKStepAgent, type), "ADKStepAgent should be a class"
        print("✅ NetLogoOrchestratorPersonaV3ADK imported and verified as class")
        print("✅ ADKStepAgent imported and verified as class")
        
        # Test agent class imports (current active agents)
        from agent_lucim_operation_generator import LucimOperationModelGeneratorAgent
        assert isinstance(LucimOperationModelGeneratorAgent, type), "LucimOperationModelGeneratorAgent should be a class"
        print("✅ LucimOperationModelGeneratorAgent imported and verified as class")
        
        from agent_lucim_scenario_generator import LUCIMScenarioGeneratorAgent
        assert isinstance(LUCIMScenarioGeneratorAgent, type), "LUCIMScenarioGeneratorAgent should be a class"
        print("✅ LUCIMScenarioGeneratorAgent imported and verified as class")
        
        from agent_lucim_plantuml_diagram_generator import LUCIMPlantUMLDiagramGeneratorAgent
        assert isinstance(LUCIMPlantUMLDiagramGeneratorAgent, type), "LUCIMPlantUMLDiagramGeneratorAgent should be a class"
        print("✅ LUCIMPlantUMLDiagramGeneratorAgent imported and verified as class")
        
        from agent_lucim_plantuml_diagram_auditor import LUCIMPlantUMLDiagramAuditorAgent
        assert isinstance(LUCIMPlantUMLDiagramAuditorAgent, type), "LUCIMPlantUMLDiagramAuditorAgent should be a class"
        print("✅ LUCIMPlantUMLDiagramAuditorAgent imported and verified as class")
        
        # Test auditor function imports
        from agent_lucim_operation_auditor import audit_environment_model
        assert callable(audit_environment_model), "audit_environment_model should be callable"
        print("✅ audit_environment_model imported and verified as callable")
        
        from agent_lucim_scenario_auditor import audit_scenario_text
        assert callable(audit_scenario_text), "audit_scenario_text should be callable"
        print("✅ audit_scenario_text imported and verified as callable")
        
        # Test utility imports
        from utils_config_constants import DEFAULT_MODEL, AGENT_CONFIGS
        assert DEFAULT_MODEL is not None, "DEFAULT_MODEL should be defined"
        assert isinstance(AGENT_CONFIGS, dict), "AGENT_CONFIGS should be a dict"
        print("✅ Utils imported and verified")
        
        print("\n🎉 All imports successful!")
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_basic_functionality():
    """Test basic functionality without API calls."""
    try:
        print("\n🧪 Testing basic functionality...")
        
        # Test orchestrator instance creation
        from orchestrator_persona_v3_adk import NetLogoOrchestratorPersonaV3ADK
        from utils_config_constants import DEFAULT_MODEL
        
        orchestrator = NetLogoOrchestratorPersonaV3ADK(
            model_name=DEFAULT_MODEL
        )
        
        print("✅ Orchestrator instance created")
        print(f"📊 Model: {orchestrator.model}")
        print(f"📊 Persona set: {orchestrator.persona_set}")
        print(f"📊 Timestamp: {orchestrator.timestamp}")
        
        # Test agent class instances
        from agent_lucim_operation_generator import LucimOperationModelGeneratorAgent
        from agent_lucim_scenario_generator import LUCIMScenarioGeneratorAgent
        from agent_lucim_plantuml_diagram_generator import LUCIMPlantUMLDiagramGeneratorAgent
        from agent_lucim_plantuml_diagram_auditor import LUCIMPlantUMLDiagramAuditorAgent
        
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        
        op_agent = LucimOperationModelGeneratorAgent(
            model_name=DEFAULT_MODEL, 
            external_timestamp=timestamp
        )
        print("✅ LucimOperationModelGeneratorAgent instance created")
        print(f"   - Name: {op_agent.name}")
        
        scen_agent = LUCIMScenarioGeneratorAgent(
            model_name=DEFAULT_MODEL, 
            external_timestamp=timestamp
        )
        print("✅ LUCIMScenarioGeneratorAgent instance created")
        print(f"   - Name: {scen_agent.name}")
        
        puml_gen_agent = LUCIMPlantUMLDiagramGeneratorAgent(
            model_name=DEFAULT_MODEL, 
            external_timestamp=timestamp
        )
        print("✅ LUCIMPlantUMLDiagramGeneratorAgent instance created")
        print(f"   - Name: {puml_gen_agent.name}")
        
        puml_aud_agent = LUCIMPlantUMLDiagramAuditorAgent(
            model_name=DEFAULT_MODEL, 
            external_timestamp=timestamp
        )
        print("✅ LUCIMPlantUMLDiagramAuditorAgent instance created")
        print(f"   - Name: {puml_aud_agent.name}")
        
        # Test auditor functions are callable
        from agent_lucim_operation_auditor import audit_environment_model
        from agent_lucim_scenario_auditor import audit_scenario_text
        
        assert callable(audit_environment_model), "audit_environment_model should be callable"
        assert callable(audit_scenario_text), "audit_scenario_text should be callable"
        print("✅ Auditor functions are callable")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print("🚀 Starting Simple Import Test")
    print("="*50)
    
    success1 = test_imports()
    success2 = test_basic_functionality()
    
    if success1 and success2:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n💥 Some tests failed!")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
