#!/usr/bin/env python3
"""
Orchestrator File I/O Utilities
File I/O operations and path management for the NetLogo orchestrator.
"""

import pathlib
from typing import Dict, Any, List, Optional
from utils_config_constants import (
    INPUT_NETLOGO_DIR,
    DEFAULT_PERSONA_SET,
    RULES_LUCIM_OPERATION_MODEL,
    RULES_LUCIM_SCENARIO,
    RULES_LUCIM_PLANTUML_DIAGRAM,
)
from utils_path import get_run_base_dir


class OrchestratorFileIO:
    """Centralized file I/O utilities for the orchestrator."""
    
    def __init__(self):
        """Initialize the orchestrator file I/O utilities."""
        pass
    
    def find_netlogo_files(self, base_name: str) -> List[Dict[str, Any]]:
        """
        Find NetLogo files matching the given base name.
        
        Args:
            base_name: Base name to search for (e.g., "climate-change", "ecosys")
            
        Returns:
            List of dictionaries containing file information
        """
        files = []
        
        # Support both legacy and new naming conventions
        candidate_files = [
            INPUT_NETLOGO_DIR / f"{base_name}-netlogo-code.md",
            INPUT_NETLOGO_DIR / f"{base_name}-code.md",
        ]
        
        code_file = next((p for p in candidate_files if p.exists()), None)
        
        if code_file is not None:
            # Find interface images for the case
            interface_images = []
            for i in [1, 2]:
                image_file = INPUT_NETLOGO_DIR / f"{base_name}-netlogo-interface-{i}.png"
                if image_file.exists():
                    interface_images.append(str(image_file))
            
            files.append({
                "code_file": code_file,
                "interface_images": interface_images,
                "base_name": base_name
            })
        
        return files
    
    
    
    def load_rules_operation_model(self) -> str:
        try:
            return RULES_LUCIM_OPERATION_MODEL.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise FileNotFoundError(f"MANDATORY INPUT MISSING: Operation Model rules not found: {RULES_LUCIM_OPERATION_MODEL}")

    def load_rules_scenario(self) -> str:
        try:
            return RULES_LUCIM_SCENARIO.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise FileNotFoundError(f"MANDATORY INPUT MISSING: Scenario rules not found: {RULES_LUCIM_SCENARIO}")

    def load_rules_diagram(self) -> str:
        try:
            return RULES_LUCIM_PLANTUML_DIAGRAM.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise FileNotFoundError(f"MANDATORY INPUT MISSING: Diagram rules not found: {RULES_LUCIM_PLANTUML_DIAGRAM}")
       
    def create_run_directory(self, timestamp: str, base_name: str, model: str, 
                           reasoning_effort: str, text_verbosity: str, persona_set: str = DEFAULT_PERSONA_SET,
                           version: Optional[str] = None) -> pathlib.Path:
        """
        Create the run directory for a specific orchestration.
        
        Args:
            timestamp: Timestamp for the run
            base_name: Base name being processed
            model: Model name
            reasoning_effort: Reasoning effort level
            text_verbosity: Text verbosity level
            persona_set: Persona set name (default: DEFAULT_PERSONA_SET)
            version: Optional orchestrator version (e.g., "v2", "v3-no-adk", "v3-adk")
            
        Returns:
            Path to the created run directory
        """
        run_dir = get_run_base_dir(timestamp, base_name, model, reasoning_effort, text_verbosity, persona_set, version)
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
    
    def create_agent_output_directory(self, run_dir: pathlib.Path, step_number: int, 
                                   agent_name: str) -> pathlib.Path:
        """
        Create the output directory for a specific agent step.
        
        Args:
            run_dir: Base run directory
            step_number: Step number (1-8)
            agent_name: Agent name
            
        Returns:
            Path to the created agent output directory
        """
        step_str = f"{int(step_number):02d}"
        agent_output_dir = run_dir / f"{step_str}-{agent_name}"
        agent_output_dir.mkdir(parents=True, exist_ok=True)
        return agent_output_dir
    
    def read_netlogo_code(self, code_file: pathlib.Path) -> str:
        """
        Read NetLogo code from a file.
        
        Args:
            code_file: Path to the NetLogo code file
            
        Returns:
            NetLogo code content
        """
        try:
            return code_file.read_text(encoding="utf-8")
        except Exception as e:
            raise Exception(f"Error reading code file: {e}")
    
    def validate_mandatory_inputs(self, base_name: str, model: str, persona_set: str = DEFAULT_PERSONA_SET) -> Dict[str, Any]:
        """
        Validate that all mandatory inputs are available.
        
        Args:
            base_name: Base name being processed
            model: Model name
            
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check for NetLogo files
        netlogo_files = self.find_netlogo_files(base_name)
        if not netlogo_files:
            validation_results["valid"] = False
            validation_results["errors"].append(f"No NetLogo files found for base name '{base_name}'")
        
        # Check for stage-specific rules files
        for required_rules in (RULES_LUCIM_OPERATION_MODEL, RULES_LUCIM_SCENARIO, RULES_LUCIM_PLANTUML_DIAGRAM):
            if not required_rules.exists():
                validation_results["valid"] = False
                validation_results["errors"].append(f"MANDATORY INPUT MISSING: Rules file not found: {required_rules}")
        
        
        return validation_results
    
    def get_interface_images(self, base_name: str) -> List[str]:
        """
        Get interface images for a base name.
        Note: input-images folder has been intentionally removed.
        
        Args:
            base_name: Base name to get images for
            
        Returns:
            Empty list since input-images folder was removed
        """
        return []
    
    def ensure_output_directories(self, run_dir: pathlib.Path) -> None:
        """
        Ensure all necessary output directories exist.
        
        Args:
            run_dir: Base run directory
        """
        # Create directories for the 6-step v3 workflow
        step_agents = [
            (1, "lucim_operation_model_generator"),
            (2, "lucim_operation_model_auditor"),
            (3, "lucim_scenario_generator"),
            (4, "lucim_scenario_auditor"),
            (5, "lucim_plantuml_diagram_generator"),
            (6, "lucim_plantuml_diagram_auditor"),
        ]
        
        for step_number, agent_name in step_agents:
            self.create_agent_output_directory(run_dir, step_number, agent_name)
    
    def get_plantuml_file_path(self, output_dir: pathlib.Path) -> Optional[str]:
        """
        Get the PlantUML file path from an output directory.
        
        Args:
            output_dir: Output directory to search
            
        Returns:
            Path to the .puml file if found, None otherwise
        """
        puml_files = list(output_dir.glob("*.puml"))
        if puml_files:
            return str(puml_files[0])
        return None
    
    def validate_plantuml_file(self, puml_file_path: str) -> bool:
        """
        Validate that a PlantUML file exists and is readable.
        
        Args:
            puml_file_path: Path to the PlantUML file
            
        Returns:
            True if valid, False otherwise
        """
        if not puml_file_path:
            return False
        
        puml_path = pathlib.Path(puml_file_path)
        return puml_path.exists() and puml_path.is_file()
    
    def get_output_file_info(self, base_name: str, timestamp: str, model: str, 
                           agent_type: str) -> Dict[str, str]:
        """
        Get output file information for a specific agent.
        
        Args:
            base_name: Base name being processed
            timestamp: Timestamp for the run
            model: Model name
            agent_type: Type of agent
            
        Returns:
            Dictionary with file information
        """
        file_info = {
            "base_name": base_name,
            "timestamp": timestamp,
            "model": model,
            "agent_type": agent_type
        }
        
        # Add file discovery hints based on agent type (v3 standardized artifacts)
        # Note: New pipeline writes canonical filenames inside stage folders:
        # - output-response.json, output-reasoning.md, output-data.json
        # - diagram.puml (PlantUML generator only)
        if agent_type == "lucim_operation_model_generator":
            file_info["pattern"] = "output-data.json"
        elif agent_type == "lucim_operation_model_auditor":
            file_info["pattern"] = "output-data.json"
        elif agent_type == "lucim_scenario_generator":
            file_info["pattern"] = "output-data.json"
        elif agent_type == "lucim_scenario_auditor":
            file_info["pattern"] = "output-data.json"
        elif agent_type == "lucim_plantuml_diagram_generator":
            # Prefer the diagram; JSON artifacts also exist
            file_info["pattern"] = "*.puml"
        elif agent_type == "lucim_plantuml_diagram_auditor":
            file_info["pattern"] = "output-data.json"
        
        return file_info
