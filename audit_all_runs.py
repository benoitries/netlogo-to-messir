#!/usr/bin/env python3
"""
Audit all runs in a specific directory using the three Python auditors:
- utils_audit_operation_model.py
- utils_audit_scenario.py
- utils_audit_diagram.py
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
import traceback

# Import the audit functions
from utils_audit_operation_model import audit_operation_model
from utils_audit_scenario import audit_scenario
from utils_audit_diagram import audit_diagram


def find_all_runs(base_dir: Path) -> List[Path]:
    """Find all run directories."""
    runs = []
    if not base_dir.exists():
        print(f"ERROR: Directory does not exist: {base_dir}")
        return runs
    
    for item in base_dir.iterdir():
        if item.is_dir() and item.name.startswith("my-ecosys-"):
            runs.append(item)
    
    return sorted(runs)


def extract_scenario_text(scenario_data: Any) -> str:
    """Extract scenario text from scenario data structure."""
    if not isinstance(scenario_data, (list, dict)):
        return ""
    
    lines = []
    if isinstance(scenario_data, list):
        for item in scenario_data:
            if isinstance(item, dict):
                msgs = (item.get("scenario", {}) or {}).get("messages", [])
                if isinstance(msgs, list):
                    for m in msgs:
                        if isinstance(m, dict):
                            src = m.get("source", "")
                            tgt = m.get("target", "")
                            name = m.get("event_name", m.get("name", ""))
                            params = m.get("parameters", "")
                            params_str = str(params).strip()
                            if params_str and not params_str.startswith("("):
                                params_str = f"({params_str})"
                            elif not params_str:
                                params_str = "()"
                            # Determine arrow type based on event type
                            event_type = m.get("event_type", "")
                            arrow = "-->" if event_type == "input_event" or name.startswith("ie") else "->"
                            lines.append(f"{src} {arrow} {tgt} : {name}{params_str}")
    
    return "\n".join(lines)


def audit_run(run_dir: Path) -> Dict[str, Any]:
    """Audit a single run directory."""
    results = {
        "run_name": run_dir.name,
        "operation_model": [],
        "scenario": [],
        "diagram": [],
        "errors": []
    }
    
    print(f"\n{'='*80}")
    print(f"Auditing run: {run_dir.name}")
    print(f"{'='*80}")
    
    # 1. Audit Operation Models
    op_model_dir = run_dir / "1_lucim_operation_model"
    if op_model_dir.exists():
        print(f"\n[Operation Model] Scanning {op_model_dir}...")
        for iter_dir in sorted(op_model_dir.glob("iter-*")):
            generator_dir = iter_dir / "1-generator"
            output_data = generator_dir / "output-data.json"
            if output_data.exists():
                try:
                    with open(output_data, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    # Handle both direct structure and wrapped in "data" key
                    op_model_data = data if isinstance(data, dict) and ("actors" in data or "system" in data) else data.get("data", {})
                    if op_model_data and isinstance(op_model_data, dict):
                        audit_result = audit_operation_model(op_model_data)
                        results["operation_model"].append({
                            "iteration": iter_dir.name,
                            "file": str(output_data.relative_to(run_dir)),
                            "audit": audit_result
                        })
                        verdict = "✅ COMPLIANT" if audit_result.get("verdict") else "❌ NON-COMPLIANT"
                        violations_count = len(audit_result.get("violations", []))
                        print(f"  {iter_dir.name}: {verdict} ({violations_count} violations)")
                except Exception as e:
                    error_msg = f"Error auditing {output_data}: {str(e)}"
                    results["errors"].append(error_msg)
                    print(f"  ❌ ERROR: {error_msg}")
    
    # 2. Audit Scenarios
    scenario_dir = run_dir / "2_lucim_scenario"
    if scenario_dir.exists():
        print(f"\n[Scenario] Scanning {scenario_dir}...")
        for iter_dir in sorted(scenario_dir.glob("iter-*")):
            generator_dir = iter_dir / "1-generator"
            output_data = generator_dir / "output-data.json"
            if output_data.exists():
                try:
                    with open(output_data, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    # Handle both direct list and wrapped in "data" key
                    scenario_data = data if isinstance(data, list) else data.get("data", [])
                    if scenario_data:
                        scenario_text = extract_scenario_text(scenario_data)
                        if scenario_text:
                            audit_result = audit_scenario(scenario_text)
                            results["scenario"].append({
                                "iteration": iter_dir.name,
                                "file": str(output_data.relative_to(run_dir)),
                                "audit": audit_result
                            })
                            verdict = "✅ COMPLIANT" if audit_result.get("verdict") else "❌ NON-COMPLIANT"
                            violations_count = len(audit_result.get("violations", []))
                            print(f"  {iter_dir.name}: {verdict} ({violations_count} violations)")
                except Exception as e:
                    error_msg = f"Error auditing {output_data}: {str(e)}"
                    results["errors"].append(error_msg)
                    print(f"  ❌ ERROR: {error_msg}")
    
    # 3. Audit Diagrams
    diagram_dir = run_dir / "3_lucim_plantuml_diagram"
    if diagram_dir.exists():
        print(f"\n[Diagram] Scanning {diagram_dir}...")
        for iter_dir in sorted(diagram_dir.glob("iter-*")):
            generator_dir = iter_dir / "1-generator"
            puml_file = generator_dir / "diagram.puml"
            if puml_file.exists():
                try:
                    with open(puml_file, 'r', encoding='utf-8') as f:
                        puml_text = f.read()
                    if puml_text:
                        audit_result = audit_diagram(puml_text)
                        results["diagram"].append({
                            "iteration": iter_dir.name,
                            "file": str(puml_file.relative_to(run_dir)),
                            "audit": audit_result
                        })
                        verdict = "✅ COMPLIANT" if audit_result.get("verdict") else "❌ NON-COMPLIANT"
                        violations_count = len(audit_result.get("violations", []))
                        print(f"  {iter_dir.name}: {verdict} ({violations_count} violations)")
                except Exception as e:
                    error_msg = f"Error auditing {puml_file}: {str(e)}"
                    results["errors"].append(error_msg)
                    print(f"  ❌ ERROR: {error_msg}")
    
    return results


def print_detailed_violations(results: Dict[str, Any]):
    """Print detailed violation information."""
    print(f"\n{'='*80}")
    print("DETAILED VIOLATIONS")
    print(f"{'='*80}")
    
    run_name = results["run_name"]
    
    # Operation Model violations
    for op_result in results["operation_model"]:
        violations = op_result["audit"].get("violations", [])
        if violations:
            print(f"\n[{run_name}] Operation Model - {op_result['iteration']}")
            print(f"  File: {op_result['file']}")
            for v in violations:
                line_num = v.get("line", "N/A")
                rule_id = v.get("id", "UNKNOWN")
                message = v.get("message", "")
                extracted = v.get("extracted_values", {})
                line_content = extracted.get("line_content") or extracted.get("actor_content") or extracted.get("event_content", "")
                location = v.get("location", "N/A")
                
                print(f"    ❌ {rule_id}: {message}")
                if location != "N/A":
                    print(f"       Location: {location}")
                if line_content:
                    if "actor_content" in extracted or "event_content" in extracted:
                        print(f"       Content (JSON):")
                        for line in line_content.split("\n")[:5]:  # Limit to first 5 lines
                            print(f"         {line}")
                    else:
                        print(f"       Line {line_num}: {line_content}")
    
    # Scenario violations
    for scen_result in results["scenario"]:
        violations = scen_result["audit"].get("violations", [])
        if violations:
            print(f"\n[{run_name}] Scenario - {scen_result['iteration']}")
            print(f"  File: {scen_result['file']}")
            for v in violations:
                line_num = v.get("line", "?")
                rule_id = v.get("id", "UNKNOWN")
                message = v.get("message", "")
                extracted = v.get("extracted_values", {})
                line_content = extracted.get("line_content", "")
                
                print(f"    ❌ {rule_id}: {message}")
                if line_content:
                    print(f"       Line {line_num}: {line_content}")
    
    # Diagram violations
    for diag_result in results["diagram"]:
        violations = diag_result["audit"].get("violations", [])
        if violations:
            print(f"\n[{run_name}] Diagram - {diag_result['iteration']}")
            print(f"  File: {diag_result['file']}")
            for v in violations:
                line_num = v.get("line", "?")
                rule_id = v.get("id", "UNKNOWN")
                message = v.get("message", "")
                extracted = v.get("extracted_values", {})
                line_content = extracted.get("line_content", "")
                
                print(f"    ❌ {rule_id}: {message}")
                if line_content:
                    print(f"       Line {line_num}: {line_content}")


def summarize_all_results(all_results: List[Dict[str, Any]]):
    """Generate a summary of all audit results."""
    print(f"\n{'='*80}")
    print("SUMMARY OF ALL AUDITS")
    print(f"{'='*80}")
    
    total_runs = len(all_results)
    op_model_stats = {"total": 0, "compliant": 0, "non_compliant": 0, "violations": {}}
    scenario_stats = {"total": 0, "compliant": 0, "non_compliant": 0, "violations": {}}
    diagram_stats = {"total": 0, "compliant": 0, "non_compliant": 0, "violations": {}}
    
    for result in all_results:
        # Operation Model stats
        for op_result in result["operation_model"]:
            op_model_stats["total"] += 1
            audit = op_result["audit"]
            if audit.get("verdict"):
                op_model_stats["compliant"] += 1
            else:
                op_model_stats["non_compliant"] += 1
                for v in audit.get("violations", []):
                    rule_id = v.get("id", "UNKNOWN")
                    op_model_stats["violations"][rule_id] = op_model_stats["violations"].get(rule_id, 0) + 1
        
        # Scenario stats
        for scen_result in result["scenario"]:
            scenario_stats["total"] += 1
            audit = scen_result["audit"]
            if audit.get("verdict"):
                scenario_stats["compliant"] += 1
            else:
                scenario_stats["non_compliant"] += 1
                for v in audit.get("violations", []):
                    rule_id = v.get("id", "UNKNOWN")
                    scenario_stats["violations"][rule_id] = scenario_stats["violations"].get(rule_id, 0) + 1
        
        # Diagram stats
        for diag_result in result["diagram"]:
            diagram_stats["total"] += 1
            audit = diag_result["audit"]
            if audit.get("verdict"):
                diagram_stats["compliant"] += 1
            else:
                diagram_stats["non_compliant"] += 1
                for v in audit.get("violations", []):
                    rule_id = v.get("id", "UNKNOWN")
                    diagram_stats["violations"][rule_id] = diagram_stats["violations"].get(rule_id, 0) + 1
    
    print(f"\n📊 OPERATION MODEL:")
    print(f"   Total audits: {op_model_stats['total']}")
    print(f"   ✅ Compliant: {op_model_stats['compliant']} ({op_model_stats['compliant']/op_model_stats['total']*100:.1f}%)" if op_model_stats['total'] > 0 else "   ✅ Compliant: 0")
    print(f"   ❌ Non-compliant: {op_model_stats['non_compliant']} ({op_model_stats['non_compliant']/op_model_stats['total']*100:.1f}%)" if op_model_stats['total'] > 0 else "   ❌ Non-compliant: 0")
    if op_model_stats["violations"]:
        print(f"   Top violations:")
        for rule_id, count in sorted(op_model_stats["violations"].items(), key=lambda x: -x[1])[:5]:
            print(f"     - {rule_id}: {count} occurrences")
    
    print(f"\n📊 SCENARIO:")
    print(f"   Total audits: {scenario_stats['total']}")
    print(f"   ✅ Compliant: {scenario_stats['compliant']} ({scenario_stats['compliant']/scenario_stats['total']*100:.1f}%)" if scenario_stats['total'] > 0 else "   ✅ Compliant: 0")
    print(f"   ❌ Non-compliant: {scenario_stats['non_compliant']} ({scenario_stats['non_compliant']/scenario_stats['total']*100:.1f}%)" if scenario_stats['total'] > 0 else "   ❌ Non-compliant: 0")
    if scenario_stats["violations"]:
        print(f"   Top violations:")
        for rule_id, count in sorted(scenario_stats["violations"].items(), key=lambda x: -x[1])[:5]:
            print(f"     - {rule_id}: {count} occurrences")
    
    print(f"\n📊 DIAGRAM:")
    print(f"   Total audits: {diagram_stats['total']}")
    print(f"   ✅ Compliant: {diagram_stats['compliant']} ({diagram_stats['compliant']/diagram_stats['total']*100:.1f}%)" if diagram_stats['total'] > 0 else "   ✅ Compliant: 0")
    print(f"   ❌ Non-compliant: {diagram_stats['non_compliant']} ({diagram_stats['non_compliant']/diagram_stats['total']*100:.1f}%)" if diagram_stats['total'] > 0 else "   ❌ Non-compliant: 0")
    if diagram_stats["violations"]:
        print(f"   Top violations:")
        for rule_id, count in sorted(diagram_stats["violations"].items(), key=lambda x: -x[1])[:5]:
            print(f"     - {rule_id}: {count} occurrences")
    
    return {
        "operation_model": op_model_stats,
        "scenario": scenario_stats,
        "diagram": diagram_stats
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python audit_all_runs.py <runs_directory>")
        sys.exit(1)
    
    runs_dir = Path(sys.argv[1])
    if not runs_dir.exists():
        print(f"ERROR: Directory does not exist: {runs_dir}")
        sys.exit(1)
    
    print(f"Auditing all runs in: {runs_dir}")
    
    all_runs = find_all_runs(runs_dir)
    if not all_runs:
        print("No run directories found!")
        sys.exit(1)
    
    print(f"Found {len(all_runs)} run directories")
    
    all_results = []
    for run_dir in all_runs:
        try:
            result = audit_run(run_dir)
            all_results.append(result)
            print_detailed_violations(result)
        except Exception as e:
            print(f"\n❌ ERROR processing {run_dir.name}: {str(e)}")
            traceback.print_exc()
    
    # Generate summary
    summary = summarize_all_results(all_results)
    
    # Save results to JSON
    output_file = runs_dir / "audit_all_runs_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "summary": summary,
            "detailed_results": all_results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Results saved to: {output_file}")


if __name__ == "__main__":
    main()

