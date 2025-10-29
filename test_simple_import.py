#!/usr/bin/env python3
"""
Simple test to verify imports and basic functionality.
"""

def test_imports():
    """Test that all required modules can be imported."""
    try:
        print("🧪 Testing imports...")
        
        # Test orchestrator imports
        from orchestrator_simplified import NetLogoOrchestratorSimplified
        print("✅ NetLogoOrchestratorSimplified imported")
        
        # Test agent imports
        from agent_1_netlogo_abstract_syntax_extractor import NetLogoAbstractSyntaxExtractorAgent
        print("✅ NetLogoAbstractSyntaxExtractorAgent imported")
        
        from agent_2a_netlogo_interface_image_analyzer import NetLogoInterfaceImageAnalyzerAgent
        print("✅ NetLogoInterfaceImageAnalyzerAgent imported")
        
        from agent_2b_netlogo_behavior_extractor import NetLogoBehaviorExtractorAgent
        print("✅ NetLogoBehaviorExtractorAgent imported")
        
        from agent_3_lucim_environment_synthesizer import NetLogoLucimEnvironmentSynthesizerAgent
        print("✅ NetLogoLucimEnvironmentSynthesizerAgent imported")
        
        from agent_4_lucim_scenario_synthesizer import NetLogoLUCIMScenarioSynthesizerAgent
        print("✅ NetLogoLUCIMScenarioSynthesizerAgent imported")
        
        from agent_5_plantuml_writer import NetLogoPlantUMLWriterAgent
        print("✅ NetLogoPlantUMLWriterAgent imported")
        
        from agent_6_plantuml_auditor import NetLogoPlantUMLLUCIMAuditorAgent
        print("✅ NetLogoPlantUMLLUCIMAuditorAgent imported")
        
        from agent_7_plantuml_corrector import NetLogoPlantUMLLUCIMCorrectorAgent
        print("✅ NetLogoPlantUMLLUCIMCorrectorAgent imported")
        
        # Test utility imports
        from utils_config_constants import DEFAULT_MODEL, AGENT_CONFIGS
        print("✅ Utils imported")
        
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
        
        # Test that we can create an orchestrator instance
        from orchestrator_simplified import NetLogoOrchestratorSimplified
        from utils_config_constants import DEFAULT_MODEL
        
        # This should work without API calls
        orchestrator = NetLogoOrchestratorSimplified(
            model_name=DEFAULT_MODEL, 
            persona_set="persona-v1"
        )
        
        print("✅ Orchestrator instance created")
        print(f"📊 Model: {orchestrator.model}")
        print(f"📊 Persona set: {orchestrator.persona_set}")
        print(f"📊 Timestamp: {orchestrator.timestamp}")
        
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
