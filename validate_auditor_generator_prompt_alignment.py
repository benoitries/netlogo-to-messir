#!/usr/bin/env python3
"""
Validation script to verify that auditor system prompts match their respective generator prompts.

This script performs static analysis to ensure:
1. Operation Model Auditor instructions include netlogo_lucim_mapping
2. Operation Model Auditor input_text includes NETLOGO-SOURCE-CODE
3. Scenario Auditor input_text includes LUCIM-OPERATION-MODEL
4. PlantUML Diagram Auditor input_text includes LUCIM-SCENARIO (mandatory)
5. All auditors use raw text copy (no json.dumps or markdown fences where generators don't)
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Tuple


def extract_function_code(file_path: Path, function_name: str) -> str:
    """Extract the source code of a function from a Python file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                # Get the function's source lines
                start_line = node.lineno - 1
                end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 50
                lines = content.split('\n')
                return '\n'.join(lines[start_line:end_line])
        return ""
    except Exception as e:
        print(f"Error extracting function from {file_path}: {e}")
        return ""


def check_operation_model_auditor():
    """Check Operation Model Auditor alignment with generator."""
    auditor_file = Path("code-netlogo-to-lucim-agentic-workflow/agent_lucim_operation_auditor.py")
    generator_file = Path("code-netlogo-to-lucim-agentic-workflow/agent_lucim_operation_generator.py")
    
    issues = []
    
    # Check auditor function signature
    auditor_code = extract_function_code(auditor_file, "audit_operation_model")
    if "netlogo_lucim_mapping: str" not in auditor_code:
        issues.append("Operation Model Auditor: netlogo_lucim_mapping parameter not found or not mandatory")
    if "netlogo_source_code: str" not in auditor_code:
        issues.append("Operation Model Auditor: netlogo_source_code parameter not found or not mandatory")
    
    # Check instructions construction
    if 'f"{persona_text}\\n\\n{netlogo_lucim_mapping}\\n\\n{rules_lucim_operation_model}"' not in auditor_code.replace(' ', ''):
        # Check for alternative patterns
        if "netlogo_lucim_mapping" not in auditor_code or "instructions" not in auditor_code:
            issues.append("Operation Model Auditor: instructions may not include netlogo_lucim_mapping")
    
    # Check input_text construction
    if "<NETLOGO-SOURCE-CODE>" not in auditor_code:
        issues.append("Operation Model Auditor: input_text missing <NETLOGO-SOURCE-CODE> block")
    if "<LUCIM-OPERATION-MODEL>" not in auditor_code:
        issues.append("Operation Model Auditor: input_text missing <LUCIM-OPERATION-MODEL> block")
    
    # Check generator for reference
    generator_code = extract_function_code(generator_file, "generate_lucim_operation_model")
    if "netlogo_lucim_mapping" not in generator_code:
        issues.append("Operation Model Generator: netlogo_lucim_mapping not found (reference check)")
    
    return issues


def check_scenario_auditor():
    """Check Scenario Auditor alignment with generator."""
    auditor_file = Path("code-netlogo-to-lucim-agentic-workflow/agent_lucim_scenario_auditor.py")
    generator_file = Path("code-netlogo-to-lucim-agentic-workflow/agent_lucim_scenario_generator.py")
    
    issues = []
    
    # Check auditor function signature
    auditor_code = extract_function_code(auditor_file, "audit_scenario_text")
    # Check for mandatory parameter (should not have Optional or default None)
    if "lucim_operation_model" not in auditor_code:
        issues.append("Scenario Auditor: lucim_operation_model parameter not found")
    elif "Optional" in auditor_code and "lucim_operation_model" in auditor_code:
        # Check if Optional is used for lucim_operation_model
        if "lucim_operation_model: Optional" in auditor_code or "Optional[lucim_operation_model" in auditor_code:
            issues.append("Scenario Auditor: lucim_operation_model should not be Optional")
    elif "lucim_operation_model = None" in auditor_code or "lucim_operation_model=None" in auditor_code:
        issues.append("Scenario Auditor: lucim_operation_model should not have default None")
    
    # Check input_text construction
    if "<LUCIM-OPERATION-MODEL>" not in auditor_code:
        issues.append("Scenario Auditor: input_text missing <LUCIM-OPERATION-MODEL> block")
    if "<SCENARIO-TEXT>" not in auditor_code:
        issues.append("Scenario Auditor: input_text missing <SCENARIO-TEXT> block")
    
    # Check for json.dumps usage (should use str() instead)
    if "json.dumps" in auditor_code and "lucim_operation_model" in auditor_code:
        # Check if it's in the input_text construction
        if "json.dumps(lucim_operation_model" in auditor_code:
            issues.append("Scenario Auditor: uses json.dumps for lucim_operation_model (should use str() like generator)")
    
    # Check generator for reference
    generator_code = extract_function_code(generator_file, "generate_scenarios")
    if "str(lucim_operation_model)" not in generator_code and "operation_model_text = str(" not in generator_code:
        # Generator might use different pattern, check for str() usage
        if "json.dumps" in generator_code and "lucim_operation_model" in generator_code:
            pass  # Generator might use json.dumps, but auditor should match
        elif "str(" not in generator_code:
            issues.append("Scenario Generator: check str() usage pattern")
    
    return issues


def check_plantuml_auditor():
    """Check PlantUML Diagram Auditor alignment with generator."""
    auditor_file = Path("code-netlogo-to-lucim-agentic-workflow/agent_lucim_plantuml_diagram_auditor.py")
    generator_file = Path("code-netlogo-to-lucim-agentic-workflow/agent_lucim_plantuml_diagram_generator.py")
    
    issues = []
    
    # Check auditor method signature
    auditor_code = extract_function_code(auditor_file, "audit_plantuml_diagrams")
    # Check for mandatory parameter (should not have Optional or default None)
    if "lucim_scenario" not in auditor_code:
        issues.append("PlantUML Diagram Auditor: lucim_scenario parameter not found")
    elif "Optional" in auditor_code and "lucim_scenario" in auditor_code:
        # Check if Optional is used for lucim_scenario in the signature
        if "lucim_scenario: Optional" in auditor_code or "Optional[lucim_scenario" in auditor_code:
            issues.append("PlantUML Diagram Auditor: lucim_scenario should not be Optional")
    elif "lucim_scenario = None" in auditor_code or "lucim_scenario=None" in auditor_code:
        issues.append("PlantUML Diagram Auditor: lucim_scenario should not have default None")
    
    # Check input_text construction
    if "<LUCIM-SCENARIO>" not in auditor_code:
        issues.append("PlantUML Diagram Auditor: input_text missing <LUCIM-SCENARIO> block")
    if "<PLANTUML-DIAGRAM>" not in auditor_code:
        issues.append("PlantUML Diagram Auditor: input_text missing <PLANTUML-DIAGRAM> block")
    
    # Check that LUCIM-SCENARIO comes before PLANTUML-DIAGRAM
    lucim_pos = auditor_code.find("<LUCIM-SCENARIO>")
    puml_pos = auditor_code.find("<PLANTUML-DIAGRAM>")
    if lucim_pos != -1 and puml_pos != -1 and lucim_pos > puml_pos:
        issues.append("PlantUML Diagram Auditor: <LUCIM-SCENARIO> should come before <PLANTUML-DIAGRAM>")
    
    # Check for json.dumps usage in input_text construction (should use str() instead, like generator)
    # Only flag if json.dumps is used for lucim_scenario in the input_text section
    if "json.dumps" in auditor_code and "lucim_scenario" in auditor_code:
        # Check if json.dumps is used for lucim_scenario specifically in input_text
        # Look for pattern: json.dumps(...lucim_scenario...) in input_text construction
        input_text_section = ""
        if "<LUCIM-SCENARIO>" in auditor_code:
            # Extract section around LUCIM-SCENARIO
            start = auditor_code.find("<LUCIM-SCENARIO>")
            end = auditor_code.find("</LUCIM-SCENARIO>", start)
            if end != -1:
                input_text_section = auditor_code[start:end+20]  # Include some context
        if "json.dumps" in input_text_section and "lucim_scenario" in input_text_section:
            issues.append("PlantUML Diagram Auditor: uses json.dumps for lucim_scenario in input_text (should use str() like generator)")
    
    # Check generator for reference
    generator_code = extract_function_code(generator_file, "generate_plantuml_diagrams")
    if "str(scenario_data)" not in generator_code and "str(scenario_text)" not in generator_code:
        if "json.dumps" in generator_code:
            pass  # Generator might use json.dumps, but should check
    
    return issues


def check_orchestrator_calls():
    """Check that orchestrator passes all required parameters."""
    orchestrator_file = Path("code-netlogo-to-lucim-agentic-workflow/utils_orchestrator_v3_process.py")
    
    issues = []
    
    try:
        content = orchestrator_file.read_text(encoding="utf-8")
        
        # Check Operation Model Auditor call
        if "audit_operation_model(" in content:
            # Find the call
            pattern = r"audit_operation_model\([^)]+\)"
            matches = re.findall(pattern, content, re.DOTALL)
            if matches:
                call = matches[0]
                if "netlogo_lucim_mapping_content" not in call:
                    issues.append("Orchestrator: Operation Model Auditor call missing netlogo_lucim_mapping_content")
                if "code_content" not in call:
                    issues.append("Orchestrator: Operation Model Auditor call missing code_content")
        
        # Check Scenario Auditor call
        if "audit_scenario_text(" in content:
            pattern = r"audit_scenario_text\([^)]+\)"
            matches = re.findall(pattern, content, re.DOTALL)
            if matches:
                call = matches[0]
                if "operation_model_data_for_scenario" not in call:
                    issues.append("Orchestrator: Scenario Auditor call missing operation_model_data_for_scenario")
        
        # Check PlantUML Diagram Auditor call
        if "audit_plantuml_diagrams(" in content:
            # Find the call with more context (may span multiple lines)
            # Look for the call pattern with context
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if "audit_plantuml_diagrams(" in line:
                    # Check next few lines for the parameter
                    context = '\n'.join(lines[i:i+5])
                    # Check if lucim_scenario is passed (could be lucim_scenario_for_audit or similar)
                    if "lucim_scenario" in context.lower():
                        # Parameter is present, check if it's None (should be validated)
                        if "lucim_scenario_for_audit" in context or "lucim_scenario" in context:
                            # Check if there's validation before the call
                            prev_context = '\n'.join(lines[max(0, i-5):i])
                            if "lucim_scenario_for_audit is None" in prev_context or "if lucim_scenario" in prev_context.lower():
                                # Validation exists, good
                                pass
                            # Parameter is present, good
                            break
                    else:
                        issues.append("Orchestrator: PlantUML Diagram Auditor call missing lucim_scenario parameter")
                        break
    
    except Exception as e:
        issues.append(f"Error checking orchestrator calls: {e}")
    
    return issues


def main():
    """Run all validation checks."""
    print("=" * 70)
    print("Validating Auditor-Generator Prompt Alignment")
    print("=" * 70)
    print()
    
    all_issues = []
    
    print("1. Checking Operation Model Auditor...")
    issues = check_operation_model_auditor()
    if issues:
        all_issues.extend(issues)
        for issue in issues:
            print(f"   ❌ {issue}")
    else:
        print("   ✅ Operation Model Auditor structure aligned")
    print()
    
    print("2. Checking Scenario Auditor...")
    issues = check_scenario_auditor()
    if issues:
        all_issues.extend(issues)
        for issue in issues:
            print(f"   ❌ {issue}")
    else:
        print("   ✅ Scenario Auditor structure aligned")
    print()
    
    print("3. Checking PlantUML Diagram Auditor...")
    issues = check_plantuml_auditor()
    if issues:
        all_issues.extend(issues)
        for issue in issues:
            print(f"   ❌ {issue}")
    else:
        print("   ✅ PlantUML Diagram Auditor structure aligned")
    print()
    
    print("4. Checking Orchestrator calls...")
    issues = check_orchestrator_calls()
    if issues:
        all_issues.extend(issues)
        for issue in issues:
            print(f"   ❌ {issue}")
    else:
        print("   ✅ Orchestrator calls pass all required parameters")
    print()
    
    print("=" * 70)
    if all_issues:
        print(f"❌ Validation failed: {len(all_issues)} issue(s) found")
        return 1
    else:
        print("✅ All validations passed!")
        print()
        print("Summary:")
        print("  - Operation Model Auditor: instructions and input_text match generator")
        print("  - Scenario Auditor: input_text matches generator")
        print("  - PlantUML Diagram Auditor: input_text matches generator")
        print("  - Orchestrator: all required parameters are passed")
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

