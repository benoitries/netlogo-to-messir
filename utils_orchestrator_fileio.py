#!/usr/bin/env python3
"""
Orchestrator File I/O Utilities
File I/O operations and path management for the NetLogo orchestrator.
"""

import pathlib
from typing import Dict, Any, List, Optional
from utils_config_constants import INPUT_NETLOGO_DIR, INPUT_ICRASH_DIR, MESSIR_RULES_FILE
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
            # Find corresponding interface images
            interface_images = []
            for img_file in INPUT_NETLOGO_DIR.glob(f"{base_name}-netlogo-interface-*.png"):
                interface_images.append(str(img_file))
            
            files.append({
                "code_file": code_file,
                "interface_images": interface_images,
                "base_name": base_name
            })
        
        return files
    
    def find_icrash_files(self) -> List[pathlib.Path]:
        """
        Find icrash files in the input-icrash directory.
        
        Returns:
            List of icrash file paths
        """
        icrash_files = []
        
        if INPUT_ICRASH_DIR.exists():
            for icrash_file in INPUT_ICRASH_DIR.glob("*.pdf"):
                icrash_files.append(icrash_file)
        
        return icrash_files
    
    def read_icrash_file_content(self, icrash_file: pathlib.Path) -> Dict[str, str]:
        """
        Read the content of an iCrash PDF file.
        
        Args:
            icrash_file: Path to the iCrash PDF file
            
        Returns:
            Dictionary containing filename, filepath, and content
        """
        try:
            # For now, we'll use a simple approach to extract text from PDF
            # In a production environment, you might want to use a proper PDF library like PyPDF2 or pdfplumber
            
            # Try to read the file as text first (in case it's not a real PDF)
            try:
                with open(icrash_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                return {
                    "filename": icrash_file.name,
                    "filepath": str(icrash_file),
                    "content": content
                }
            except UnicodeDecodeError:
                # If it's a real PDF, we'll use a fallback approach
                # For now, we'll create a reference based on the filename
                if "actors" in icrash_file.name.lower():
                    content = "iCrash Actors Reference: Contains definitions of system actors and their roles in the iCrash case study. Use this to understand actor naming conventions and responsibilities."
                elif "casestudy" in icrash_file.name.lower():
                    content = "iCrash Case Study: Contains the complete case study description with system requirements, actors, and event patterns. Use this as the primary reference for Messir UCI mapping."
                else:
                    content = f"iCrash Reference File: {icrash_file.name} - Contains relevant patterns and examples for Messir UCI mapping."
                
                return {
                    "filename": icrash_file.name,
                    "filepath": str(icrash_file),
                    "content": content
                }
                
        except Exception as e:
            return {
                "filename": icrash_file.name,
                "filepath": str(icrash_file),
                "content": f"Error reading file: {e}"
            }
    
    def load_messir_dsl_content(self) -> str:
        """
        Load MUCIM DSL content from the rules file.
        
        Returns:
            MUCIM DSL content as string
        """
        try:
            messir_dsl_content = MESSIR_RULES_FILE.read_text(encoding="utf-8")
            return messir_dsl_content
        except FileNotFoundError:
            raise FileNotFoundError(f"MANDATORY INPUT MISSING: MUCIM DSL file not found: {MESSIR_RULES_FILE}")
    
    def load_icrash_contents(self) -> List[Dict[str, str]]:
        """
        Load all iCrash file contents.
        
        Returns:
            List of iCrash file content dictionaries
        """
        icrash_files = self.find_icrash_files()
        icrash_contents = []
        
        for icrash_file in icrash_files:
            icrash_content = self.read_icrash_file_content(icrash_file)
            icrash_contents.append(icrash_content)
        
        return icrash_contents
    
    def create_run_directory(self, timestamp: str, base_name: str, model: str, 
                           reasoning_effort: str, text_verbosity: str) -> pathlib.Path:
        """
        Create the run directory for a specific orchestration.
        
        Args:
            timestamp: Timestamp for the run
            base_name: Base name being processed
            model: Model name
            reasoning_effort: Reasoning effort level
            text_verbosity: Text verbosity level
            
        Returns:
            Path to the created run directory
        """
        run_dir = get_run_base_dir(timestamp, base_name, model, reasoning_effort, text_verbosity)
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
    
    def validate_mandatory_inputs(self, base_name: str, model: str) -> Dict[str, Any]:
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
        
        # Check for MUCIM DSL file
        if not MESSIR_RULES_FILE.exists():
            validation_results["valid"] = False
            validation_results["errors"].append(f"MANDATORY INPUT MISSING: MUCIM DSL file not found: {MESSIR_RULES_FILE}")
        
        # Check for iCrash files (optional but recommended)
        icrash_files = self.find_icrash_files()
        if not icrash_files:
            validation_results["warnings"].append(f"No iCrash files found in {INPUT_ICRASH_DIR}")
        
        return validation_results
    
    def get_interface_images(self, base_name: str) -> List[str]:
        """
        Get interface images for a base name.
        
        Args:
            base_name: Base name to get images for
            
        Returns:
            List of interface image file paths
        """
        interface_images = []
        for img_file in INPUT_NETLOGO_DIR.glob(f"{base_name}-netlogo-interface-*.png"):
            interface_images.append(str(img_file))
        return interface_images
    
    def ensure_output_directories(self, run_dir: pathlib.Path) -> None:
        """
        Ensure all necessary output directories exist.
        
        Args:
            run_dir: Base run directory
        """
        # Create directories for all 8 steps
        step_agents = [
            (1, "syntax_parser"),
            (2, "semantics_parser"),
            (3, "messir_mapper"),
            (4, "scenario_writer"),
            (5, "plantuml_writer"),
            (6, "plantuml_messir_auditor"),
            (7, "plantuml_messir_corrector"),
            (8, "plantuml_messir_final_auditor")
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
        
        # Add specific file patterns based on agent type
        if agent_type == "syntax_parser":
            file_info["pattern"] = f"{base_name}_{timestamp}_{model}_1a_syntax_parser_v1_*.md"
        elif agent_type == "semantics_parser":
            file_info["pattern"] = f"{base_name}_{timestamp}_{model}_1b_semantics_parser_v1_*.json/md"
        elif agent_type == "messir_mapper":
            file_info["pattern"] = f"{base_name}_{timestamp}_{model}_2_messir_v1_*.json/md"
        elif agent_type == "scenario_writer":
            file_info["pattern"] = f"{base_name}_{timestamp}_{model}_3_scenario_v1_*.md"
        elif agent_type == "plantuml_writer":
            file_info["pattern"] = f"{base_name}_{timestamp}_{model}_4_plantuml_*.json/md/.puml"
        elif agent_type == "plantuml_messir_auditor":
            file_info["pattern"] = f"{base_name}_{timestamp}_{model}_5_messir_audit_*.json/md/.puml"
        elif agent_type == "plantuml_messir_corrector":
            file_info["pattern"] = f"{base_name}_{timestamp}_{model}_7_messir_corrector_*.json/md/.puml"
        elif agent_type == "plantuml_messir_final_auditor":
            file_info["pattern"] = f"{base_name}_{timestamp}_{model}_8_messir_final_auditor_*.json/md/.puml"
        
        return file_info
