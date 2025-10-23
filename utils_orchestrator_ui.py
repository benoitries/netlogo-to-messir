#!/usr/bin/env python3
"""
Orchestrator UI Utilities
Terminal UI interaction and user prompts for the NetLogo orchestrator.
"""

from typing import List, Dict, Any, Tuple
import os
from pathlib import Path
from utils_config_constants import AVAILABLE_MODELS, DEFAULT_MODEL, INPUT_NETLOGO_DIR, INPUT_PERSONA_DIR


class OrchestratorUI:
    """Centralized UI interaction utilities for the orchestrator."""
    
    def __init__(self):
        """Initialize the orchestrator UI utilities."""
        pass
    
    def validate_openai_key(self) -> bool:
        """Validate OpenAI API key before any user interaction."""
        from utils_openai_client import validate_openai_key
        print("Validating OpenAI API key...")
        if not validate_openai_key():
            print("Exiting due to invalid OpenAI API key")
            return False
        return True
    
    def get_available_base_names(self) -> List[str]:
        """
        Get available base names from supported patterns.
        
        Returns:
            List of base names found in the input directory
        """
        code_files = set()
        for pattern in ("*-netlogo-code.md", "*-code.md"):
            for f in INPUT_NETLOGO_DIR.glob(pattern):
                code_files.add(f)
        
        if not code_files:
            print(f"No NetLogo code files found in {INPUT_NETLOGO_DIR} (expected *-netlogo-code.md or *-code.md)")
            return []
        
        base_names = []
        for code_file in sorted(code_files):
            stem = code_file.stem
            if stem.endswith("-netlogo-code"):
                base_name = stem.replace("-netlogo-code", "")
            elif stem.endswith("-code"):
                base_name = stem.replace("-code", "")
            else:
                # Fallback: keep original stem
                base_name = stem
            base_names.append(base_name)
        
        return base_names
    
    def select_models(self) -> List[str]:
        """
        Handle model selection UI.
        
        Returns:
            List of selected models
        """
        print("NetLogo Orchestrator - AI Model Selection")
        print("="*50)
        print("Available AI Models:")
        print("0. All models")
        for i, model in enumerate(AVAILABLE_MODELS, 1):
            print(f"{i}. {model}")
        
        print("\nEnter the number of the AI model to use")
        print(f" - Press Enter once to immediately start the default run: {DEFAULT_MODEL or 'default-model'}, 3d-solids, low effort (parallel steps 1+2)")
        print(" - Or type a number (or 'q' to quit):")
        
        while True:
            try:
                model_input = input("Model > ").strip()
                
                if model_input.lower() == 'q':
                    print("Exiting...")
                    return []
                
                # Short-circuit: single Enter triggers immediate default run
                if model_input == "":
                    print("\nStarting default run (single Enter detected):")
                    print(" - Steps 1+2 will run in parallel, then continue from step 3")
                    return [DEFAULT_MODEL]
                
                model_number = int(model_input)
                if model_number == 0:
                    return AVAILABLE_MODELS
                elif 1 <= model_number <= len(AVAILABLE_MODELS):
                    return [AVAILABLE_MODELS[model_number - 1]]
                else:
                    print(f"Error: Invalid number {model_number}. Available options: 0-{len(AVAILABLE_MODELS)}")
                    print("Please enter a valid number, press Enter for default, or 'q' to quit:")
            except ValueError:
                print("Error: Please enter a valid number, press Enter for default, or 'q' to quit:")
    
    def select_base_names(self, base_names: List[str]) -> List[str]:
        """
        Handle base name selection UI.
        
        Args:
            base_names: List of available base names
            
        Returns:
            List of selected base names
        """
        print("\nNetLogo Orchestrator - Available Models")
        print("="*40)
        print("0. All cases (excluding: my-ecosys)")
        for i, base_name in enumerate(base_names, 1):
            print(f"{i:2d}. {base_name}")
        
        print("\nEnter the number of the NetLogo model to process (or press Enter for default 'my-ecosys', or 'q' to quit):")
        
        while True:
            try:
                user_input = input("NetLogo Model > ").strip()
                
                if user_input.lower() == 'q':
                    print("Exiting...")
                    return []
                
                # Default to 'my-ecosys' if no input provided (fallback to first if missing)
                if user_input == "":
                    default_base_name = "my-ecosys"
                    chosen_base_name = default_base_name if default_base_name in base_names else base_names[0]
                    selected_base_names = [chosen_base_name]
                    print(f"Using default: {chosen_base_name}")
                    return selected_base_names
                
                number = int(user_input)
                if number == 0:
                    # Run all cases except explicitly excluded ones
                    return [bn for bn in base_names if bn != "my-ecosys"]
                elif 1 <= number <= len(base_names):
                    return [base_names[number - 1]]
                else:
                    print(f"Error: Invalid number {number}. Available options: 0-{len(base_names)}")
                    print("Please enter a valid number, press Enter for default, or 'q' to quit:")
            except ValueError:
                print("Error: Please enter a valid number, press Enter for default, or 'q' to quit:")
    
    def select_timeout_preset(self) -> Tuple[int, str]:
        """
        Handle timeout preset selection UI.
        
        Returns:
            Tuple of (timeout_seconds, preset_name)
        """
        print(f"\n{'='*60}")
        print("TIMEOUT PRESET SELECTION")
        print(f"{'='*60}")
        import utils_config_constants as cfg
        
        # Determine display of current defaults from utils_config_constants.py
        current_orch_default = getattr(cfg, "ORCHESTRATOR_PARALLEL_TIMEOUT", None)
        if current_orch_default is None:
            default_label = "No timeout"
        else:
            default_label = f"{current_orch_default}s"
        
        print("Choose timeout preset (applies to agents polling and orchestrator watchdog):")
        print("0. No timeout (agents and orchestrator)")
        print("1. Medium timeout (900s)")
        print("2. Long timeout (1800s)")
        print(f"Press Enter for default from utils_config_constants.py ({default_label})")
        print("Note: default utils_config_constants.py now sets NO TIMEOUT for both agents and orchestrator.")
        
        preset_map = {0: None, 1: 900, 2: 1800}
        while True:
            timeout_input = input("Timeout preset > ").strip()
            if timeout_input == "":
                # Keep utils_config_constants.py defaults as-is
                chosen_seconds = current_orch_default
                chosen_preset = "default"
                print(f"Using default from utils_config_constants.py: {default_label}")
                return chosen_seconds, chosen_preset
            try:
                timeout_choice = int(timeout_input)
                if timeout_choice in preset_map:
                    chosen_seconds = preset_map[timeout_choice]
                    chosen_preset = str(timeout_choice)
                    # Apply to orchestrator watchdog
                    setattr(cfg, "ORCHESTRATOR_PARALLEL_TIMEOUT", chosen_seconds)
                    # Apply to all agent timeouts (None -> unlimited)
                    if hasattr(cfg, "AGENT_TIMEOUTS") and isinstance(cfg.AGENT_TIMEOUTS, dict):
                        for k in list(cfg.AGENT_TIMEOUTS.keys()):
                            cfg.AGENT_TIMEOUTS[k] = chosen_seconds
                    label = "No timeout" if chosen_seconds is None else f"{chosen_seconds}s"
                    print(f"Applied timeout preset {timeout_choice} → {label}")
                    return chosen_seconds, chosen_preset
                else:
                    print("Error: Invalid choice. Available options: 0,1,2 or Enter for default")
            except ValueError:
                print("Error: Please enter 0, 1, 2 or press Enter for default")
    
    def select_reasoning_effort(self) -> List[Dict[str, str]]:
        """
        Handle reasoning effort selection UI.
        
        Returns:
            List of reasoning configurations
        """
        print(f"\n{'='*60}")
        print("REASONING EFFORT SELECTION")
        print(f"{'='*60}")
        print("Available reasoning effort levels:")
        print("1. Minimal effort (fastest)")
        print("2. Low effort")
        print("3. Medium effort - DEFAULT")
        print("4. High effort (highest quality)")
        print("   - Option 0 will run each effort level sequentially for comparison")
        print("   - Takes 3x longer but provides comprehensive analysis")
        
        print("\nEnter your choice (0-4, or press Enter for default medium, or 'q' to quit):")
        
        while True:
            try:
                reasoning_input = input("Reasoning effort > ").strip()
                
                if reasoning_input.lower() == 'q':
                    print("Exiting...")
                    return []
                
                # Default to medium (3) if no input provided
                if reasoning_input == "":
                    reasoning_choice = 3
                    print("Using default: Medium effort")
                    break
                
                reasoning_choice = int(reasoning_input)
                if 0 <= reasoning_choice <= 4:
                    break
                else:
                    print(f"Error: Invalid choice {reasoning_choice}. Available options: 0-4")
                    print("Please enter a valid choice, press Enter for default, or 'q' to quit:")
            except ValueError:
                print("Error: Please enter a valid number, press Enter for default, or 'q' to quit:")
        
        # Define reasoning effort configurations
        reasoning_configs = {
            0: "all",  # Special case for all effort levels
            1: {"effort": "minimal", "summary": "auto"},
            2: {"effort": "low", "summary": "auto"},
            3: {"effort": "medium", "summary": "auto"},
            4: {"effort": "high", "summary": "auto"}
        }
        
        selected_reasoning = reasoning_configs[reasoning_choice]
        
        if selected_reasoning == "all":
            print(f"\nSelected: ALL reasoning effort levels (runs efforts sequentially for comparison)")
            print("This will run each effort level sequentially for comprehensive analysis.")
            reasoning_levels = [
                {"effort": "minimal", "summary": "auto"},
                {"effort": "low", "summary": "auto"},
                {"effort": "medium", "summary": "auto"},
                {"effort": "high", "summary": "auto"}
            ]
        else:
            print(f"\nSelected: {selected_reasoning['effort'].title()} effort")
            reasoning_levels = [selected_reasoning]
        
        return reasoning_levels
    
    def select_text_verbosity(self) -> List[str]:
        """
        Handle text verbosity selection UI.
        
        Returns:
            List of selected verbosity levels
        """
        print("\nTEXT VERBOSITY SELECTION")
        print("0. All verbosities (low, medium, high)")
        print("1. Low verbosity")
        print("2. Medium verbosity - DEFAULT")
        print("3. High verbosity")
        print("Enter your choice (0-3, or press Enter for default medium):")
        
        while True:
            text_input = input("Text verbosity > ").strip()
            if text_input == "":
                text_choice = 2
                print("Using default: Medium verbosity")
                break
            try:
                text_choice = int(text_input)
                if 0 <= text_choice <= 3:
                    break
                else:
                    print("Error: Invalid choice. Available options: 0-3")
            except ValueError:
                print("Error: Please enter a valid number or press Enter for default")
        
        text_map = {1: "low", 2: "medium", 3: "high"}
        
        # Determine which verbosity levels to run
        if text_choice == 0:
            return ["low", "medium", "high"]
        else:
            return [text_map[text_choice]]
    
    def print_parameter_bundle(self, model: str, base_name: str, reasoning_effort: str, 
                            reasoning_summary: str, text_verbosity: str) -> None:
        """
        Print a parameter bundle line.
        
        Args:
            model: AI model name
            base_name: Base name being processed
            reasoning_effort: Reasoning effort level
            reasoning_summary: Reasoning summary mode
            text_verbosity: Text verbosity level
        """
        from utils_logging import format_parameter_bundle
        bundle_line = format_parameter_bundle(
            model=model,
            base_name=base_name,
            reasoning_effort=reasoning_effort,
            reasoning_summary=reasoning_summary,
            text_verbosity=text_verbosity
        )
        print(bundle_line)
    
    def print_combination_header(self, current_combination: int, total_combinations: int) -> None:
        """Print combination processing header."""
        print(f"\n{'='*60}")
        print(f"PROCESSING COMBINATION {current_combination}/{total_combinations}")
        print(f"{'='*60}")
    
    def print_final_summary(self, total_execution_time: float, total_files: int, 
                          total_agents: int, total_successful_agents: int, 
                          overall_success_rate: float, all_results: dict = None) -> None:
        """
        Print final execution summary with enhanced audit metrics.
        
        Args:
            total_execution_time: Total execution time
            total_files: Total files processed
            total_agents: Total agents executed
            total_successful_agents: Total successful agents
            overall_success_rate: Overall success rate percentage
            all_results: All orchestration results for audit analysis
        """
        from utils_format import FormatUtils
        
        print(f"\n⏱️  TOTAL EXECUTION TIME:")
        print(f"   Total time: {FormatUtils.format_duration(total_execution_time)}")
        
        print(f"\n{'='*80}")
        print("OVERALL SUMMARY")
        print(f"{'='*80}")
        print(f"Total combinations processed: {total_files}")
        print(f"Total files processed: {total_files}")
        print(f"Total agents: {total_agents}")
        print(f"Successful agents: {total_successful_agents}")
        print(f"Overall success rate: {overall_success_rate:.1f}%")
        
        # Enhanced audit metrics
        if all_results:
            self._print_audit_metrics(all_results)
    
    def _print_audit_metrics(self, all_results: dict) -> None:
        """
        Print enhanced audit metrics including compliance analysis.
        
        Args:
            all_results: All orchestration results for audit analysis
        """
        print(f"\n{'='*80}")
        print("AUDIT COMPLIANCE METRICS")
        print(f"{'='*80}")
        
        # Analyze audit results
        audit_analysis = self._analyze_audit_results(all_results)
        
        # Successful runs (step 6 or 8 audit = compliant)
        successful_runs = audit_analysis['successful_runs']
        total_runs = audit_analysis['total_runs']
        success_percentage = (successful_runs / total_runs * 100) if total_runs > 0 else 0
        
        print(f"📊 RUN SUCCESS ANALYSIS:")
        print(f"   Successful runs: {successful_runs}/{total_runs} ({success_percentage:.1f}%)")
        print(f"   Failed runs: {total_runs - successful_runs}/{total_runs} ({100 - success_percentage:.1f}%)")
        print(f"   Success criteria: Step 6 OR Step 8 audit = compliant")
        
        # Non-compliant rules per run
        print(f"\n📋 NON-COMPLIANT RULES PER RUN:")
        for run_name, non_compliant_count in audit_analysis['non_compliant_per_run'].items():
            print(f"   {run_name}: {non_compliant_count} non-compliant rules")
        
        # Frequency analysis of non-compliant rules
        if audit_analysis['rule_frequency']:
            print(f"\n🔍 RULE VIOLATION FREQUENCY (sorted by frequency):")
            for rule, count in audit_analysis['rule_frequency']:
                print(f"   {rule}: {count} violations")
        else:
            print(f"\n✅ No rule violations found across all runs!")
    
    def _analyze_audit_results(self, all_results: dict) -> dict:
        """
        Analyze audit results to extract compliance metrics.
        
        Args:
            all_results: All orchestration results
            
        Returns:
            Dictionary with audit analysis results
        """
        successful_runs = 0
        total_runs = 0
        non_compliant_per_run = {}
        rule_violations = {}
        
        for run_name, result in all_results.items():
            if not result or not isinstance(result.get("results"), dict):
                continue
                
            total_runs += 1
            run_results = result["results"]
            
            # Check step 6 (plantuml_messir_auditor) and step 8 (plantuml_messir_final_auditor)
            step6_compliant = self._is_audit_compliant(run_results.get("plantuml_messir_auditor"))
            step8_compliant = self._is_audit_compliant(run_results.get("plantuml_messir_final_auditor"))
            
            # Run is successful if either step 6 OR step 8 is compliant
            if step6_compliant or step8_compliant:
                successful_runs += 1
            
            # Count non-compliant rules for this run
            non_compliant_count = 0
            for step_name in ["plantuml_messir_auditor", "plantuml_messir_final_auditor"]:
                step_result = run_results.get(step_name)
                if step_result and isinstance(step_result, dict):
                    data = step_result.get("data", {})
                    if isinstance(data, dict):
                        non_compliant_rules = data.get("non-compliant-rules", [])
                        if isinstance(non_compliant_rules, list):
                            non_compliant_count += len(non_compliant_rules)
                            
                            # Track rule violations for frequency analysis
                            for rule in non_compliant_rules:
                                if isinstance(rule, str):
                                    rule_violations[rule] = rule_violations.get(rule, 0) + 1
            
            non_compliant_per_run[run_name] = non_compliant_count
        
        # Sort rule violations by frequency (descending)
        rule_frequency = sorted(rule_violations.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'successful_runs': successful_runs,
            'total_runs': total_runs,
            'non_compliant_per_run': non_compliant_per_run,
            'rule_frequency': rule_frequency
        }
    
    def _is_audit_compliant(self, audit_result) -> bool:
        """
        Check if an audit result is compliant.
        
        Args:
            audit_result: Audit result data
            
        Returns:
            True if compliant, False otherwise
        """
        if not audit_result or not isinstance(audit_result, dict):
            return False
            
        data = audit_result.get("data", {})
        if not isinstance(data, dict):
            return False
            
        # Check if verdict is compliant
        verdict = data.get("verdict")
        if verdict == "compliant":
            return True
            
        # Check if there are no non-compliant rules
        non_compliant_rules = data.get("non-compliant-rules", [])
        if isinstance(non_compliant_rules, list) and len(non_compliant_rules) == 0:
            return True
            
        return False
    
    def select_persona_set(self, persona_set: str = None) -> str:
        """
        Interactive selection of persona set from available subfolders in input-persona.
        
        Args:
            persona_set: Optional pre-selected persona set (bypasses interactive selection)
            
        Returns:
            Selected persona set name
        """
        if persona_set:
            # Validate the provided persona set
            persona_path = INPUT_PERSONA_DIR / persona_set
            if persona_path.exists() and persona_path.is_dir():
                print(f"✅ Using pre-selected persona set: {persona_set}")
                return persona_set
            else:
                print(f"⚠️  Warning: Specified persona set '{persona_set}' not found. Falling back to interactive selection.")
        
        # Get available persona sets
        available_persona_sets = self._get_available_persona_sets()
        
        if not available_persona_sets:
            print("❌ No persona sets found in input-persona directory")
            return "persona-v1"  # Fallback to default
        
        if len(available_persona_sets) == 1:
            selected = available_persona_sets[0]
            print(f"✅ Only one persona set available: {selected}")
            return selected
        
        # Interactive selection
        print(f"\n🎭 Available Persona Sets:")
        print("=" * 50)
        
        for i, persona_set in enumerate(available_persona_sets, 1):
            print(f"  {i}. {persona_set}")
        
        print(f"\nDefault: persona-v1 (press Enter to use default)")
        
        while True:
            try:
                choice = input(f"\nSelect persona set (1-{len(available_persona_sets)}) or press Enter for default: ").strip()
                
                if not choice:  # Empty input - use default
                    return "persona-v1"
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(available_persona_sets):
                    selected = available_persona_sets[choice_num - 1]
                    print(f"✅ Selected persona set: {selected}")
                    return selected
                else:
                    print(f"❌ Please enter a number between 1 and {len(available_persona_sets)}")
            except ValueError:
                print("❌ Please enter a valid number or press Enter for default")
    
    def _get_available_persona_sets(self) -> List[str]:
        """
        Get list of available persona sets from input-persona subdirectories.
        
        Returns:
            List of persona set names (subdirectory names)
        """
        if not INPUT_PERSONA_DIR.exists():
            return []
        
        persona_sets = []
        for item in INPUT_PERSONA_DIR.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it contains required persona files
                if self._validate_persona_set(item):
                    persona_sets.append(item.name)
        
        return sorted(persona_sets)
    
    def _validate_persona_set(self, persona_dir: Path) -> bool:
        """
        Validate that a persona directory contains the required files.
        
        Args:
            persona_dir: Path to the persona directory
            
        Returns:
            True if the directory contains required persona files
        """
        required_files = [
            "PSN_1_NetLogoAbstractSyntaxExtractor.md",
            "PSN_2_NetlogoBehaviorExtractor.md", 
            "PSN_3_LUCIMEnvironmentSynthesizer.md",
            "PSN_4_LUCIMScenarioSynthesizer.md",
            "PSN_5_PlantUMLWriter.md",
            "PSN_6_PlantUMLMessirAuditor.md",
            "PSN_7_PlantUMLMessirCorrector.md",
            "DSL_Target_LUCIM-full-definition-for-compliance.md"
        ]
        
        for required_file in required_files:
            if not (persona_dir / required_file).exists():
                return False
        
        return True
