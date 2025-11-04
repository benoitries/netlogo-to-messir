#!/usr/bin/env python3
"""
Analyze ADK orchestrator run results.
Summarizes the execution and validates the output structure.
"""

import json
import pathlib
import sys
from typing import Dict, Any, Optional
from datetime import datetime


def analyze_run_directory(run_dir: pathlib.Path) -> Dict[str, Any]:
    """
    Analyze a single run directory.
    
    Args:
        run_dir: Path to the run directory (e.g., runs/2025-11-01/0740-persona-v3-limited-agents-v3-adk/...)
        
    Returns:
        Dictionary with analysis results
    """
    results = {
        "run_directory": str(run_dir),
        "steps": {},
        "compliance_status": None,
        "errors": [],
        "warnings": []
    }
    
    # Expected steps in v3 pipeline
    expected_steps = {
        "01-lucim_operation_synthesizer": "Step 1: LUCIM Operation Synthesizer",
        "02-lucim_scenario_synthesizer": "Step 2: LUCIM Scenario Synthesizer",
        "03-plantuml_writer": "Step 3: PlantUML Writer",
        "04-plantuml_lucim_auditor": "Step 4: PlantUML LUCIM Auditor",
        "05-plantuml_lucim_corrector": "Step 5: PlantUML LUCIM Corrector (conditional)",
        "06-plantuml_lucim_final_auditor": "Step 6: PlantUML LUCIM Final Auditor (conditional)"
    }
    
    # Analyze each step
    for step_dir_name, step_description in expected_steps.items():
        step_dir = run_dir / step_dir_name
        
        step_info = {
            "description": step_description,
            "executed": step_dir.exists() and step_dir.is_dir() and any(step_dir.iterdir()),
            "files": [],
            "has_output_data": False,
            "has_diagram": False,
            "verdict": None,
            "errors": []
        }
        
        if step_info["executed"]:
            # Check for required files
            output_data_file = step_dir / "output-data.json"
            output_response_file = step_dir / "output-response.json"
            diagram_file = step_dir / "diagram.puml"
            
            step_info["files"] = [f.name for f in step_dir.iterdir() if f.is_file()]
            
            # Check output-data.json
            if output_data_file.exists():
                step_info["has_output_data"] = True
                try:
                    with open(output_data_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    # Extract verdict if it's an auditor step
                    if "verdict" in data:
                        step_info["verdict"] = data.get("verdict")
                        if step_info["verdict"] == "compliant":
                            results["compliance_status"] = "COMPLIANT"
                        elif step_info["verdict"] == "non-compliant":
                            results["compliance_status"] = "NON_COMPLIANT"
                except Exception as e:
                    step_info["errors"].append(f"Failed to parse output-data.json: {e}")
            
            # Check for diagram
            if diagram_file.exists():
                step_info["has_diagram"] = True
        
        results["steps"][step_dir_name] = step_info
    
    # Determine pipeline status
    step1_executed = results["steps"]["01-lucim_operation_synthesizer"]["executed"]
    step2_executed = results["steps"]["02-lucim_scenario_synthesizer"]["executed"]
    step3_executed = results["steps"]["03-plantuml_writer"]["executed"]
    step4_executed = results["steps"]["04-plantuml_lucim_auditor"]["executed"]
    step4_verdict = results["steps"]["04-plantuml_lucim_auditor"].get("verdict")
    step5_executed = results["steps"]["05-plantuml_lucim_corrector"]["executed"]
    step6_executed = results["steps"]["06-plantuml_lucim_final_auditor"]["executed"]
    
    # Validate pipeline flow
    if not step1_executed:
        results["errors"].append("Step 1 (LUCIM Environment Synthesizer) not executed")
    if not step2_executed:
        results["errors"].append("Step 2 (LUCIM Scenario Synthesizer) not executed")
    if not step3_executed:
        results["errors"].append("Step 3 (PlantUML Writer) not executed")
    if not step4_executed:
        results["errors"].append("Step 4 (PlantUML LUCIM Auditor) not executed")
    
    # Conditional steps logic
    if step4_verdict == "compliant":
        if step5_executed:
            results["warnings"].append("Step 5 (Corrector) executed but verdict was compliant (should be skipped)")
        if step6_executed:
            results["warnings"].append("Step 6 (Final Auditor) executed but corrector was not needed")
    elif step4_verdict == "non-compliant":
        if not step5_executed:
            results["warnings"].append("Step 5 (Corrector) not executed but verdict was non-compliant (should be executed)")
        if step5_executed and not step6_executed:
            results["warnings"].append("Step 6 (Final Auditor) not executed after corrector")
    
    return results


def print_analysis(results: Dict[str, Any]):
    """Print analysis results in a readable format."""
    print("=" * 80)
    print("ADK Orchestrator Run Analysis")
    print("=" * 80)
    print(f"Run Directory: {results['run_directory']}")
    print()
    
    # Steps summary
    print("Steps Execution Summary:")
    print("-" * 80)
    for step_name, step_info in results["steps"].items():
        status = "✓ EXECUTED" if step_info["executed"] else "✗ NOT EXECUTED"
        verdict_str = f" [{step_info['verdict']}]" if step_info.get("verdict") else ""
        print(f"  {status} {step_info['description']}{verdict_str}")
        
        if step_info["executed"]:
            if step_info["has_output_data"]:
                print(f"    ✓ output-data.json present")
            if step_info["has_diagram"]:
                print(f"    ✓ diagram.puml present")
            if step_info["files"]:
                print(f"    Files: {', '.join(step_info['files'])}")
        print()
    
    # Compliance status
    if results["compliance_status"]:
        print(f"Compliance Status: {results['compliance_status']}")
        print()
    
    # Errors
    if results["errors"]:
        print("ERRORS:")
        print("-" * 80)
        for error in results["errors"]:
            print(f"  ✗ {error}")
        print()
    
    # Warnings
    if results["warnings"]:
        print("WARNINGS:")
        print("-" * 80)
        for warning in results["warnings"]:
            print(f"  ⚠ {warning}")
        print()
    
    # Overall status
    if not results["errors"] and not results["warnings"]:
        print("✓ Run completed successfully with no errors or warnings")
    elif not results["errors"]:
        print("⚠ Run completed with warnings (see above)")
    else:
        print("✗ Run completed with errors (see above)")
    
    print("=" * 80)


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python analyze_adk_run_results.py <run_directory_path>")
        print()
        print("Example:")
        print('  python analyze_adk_run_results.py "output/runs/2025-11-01/0740-persona-v3-limited-agents-v3-adk/my-ecosys-..."')
        sys.exit(1)
    
    run_dir = pathlib.Path(sys.argv[1])
    
    if not run_dir.exists():
        print(f"Error: Directory not found: {run_dir}")
        sys.exit(1)
    
    results = analyze_run_directory(run_dir)
    print_analysis(results)
    
    # Exit with error code if there are errors
    sys.exit(1 if results["errors"] else 0)


if __name__ == "__main__":
    main()

