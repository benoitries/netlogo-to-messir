#!/usr/bin/env python3
"""
Orchestrator V3 Process File Utility
Handles the processing of a single NetLogo file with iterative Generator→Auditor
loops for Operation Model, Scenario, and PlantUML Diagram stages. Each stage
persists artifacts per iteration under:

- lucim_operation_model/iter-<k>/{1-generator, 2-auditor}
- lucim_scenario/iter-<k>/{1-generator, 2-auditor}
- lucim_plantuml_diagram/iter-<k>/{1-generator, 2-auditor}

The Generator plays a dual role: initial artifact generation at iteration 1, and
audit-driven corrective updates at iterations >1 using the previous artifact and
previous audit report. The workflow stops early when compliant, or proceeds to
the next stage / ends when reaching MAX_AUDIT.
"""

import time
from typing import Dict, Any
from pathlib import Path

from utils_format import FormatUtils
from utils_orchestrator_v3_persona_config import load_netlogo_lucim_mapping
from agent_lucim_operation_auditor import audit_operation_model
from agent_lucim_scenario_auditor import audit_scenario_text
from utils_config_constants import (
    RULES_LUCIM_OPERATION_MODEL,
    RULES_LUCIM_SCENARIO,
)
from utils_orchestrator_v3_persona_config import INPUT_PERSONA_DIR
from utils_audit_operation_model import audit_operation_model as py_audit_environment
from utils_audit_scenario import audit_scenario as py_audit_scenario
from utils_audit_diagram import audit_diagram as py_audit_diagram
from utils_audit_compare import compare_verdicts, log_comparison
from utils_audit_core import extract_audit_core


async def process_netlogo_file_v3_adk(orchestrator_instance, file_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single NetLogo file using ADK Sequential workflow.
    
    Args:
        orchestrator_instance: Orchestrator instance
        file_info: Dictionary containing file information
        
    Returns:
        Dictionary containing all processing results
    """
    base_name = file_info["base_name"]
    orchestrator_instance.processed_results = {}
    
    # Ensure reasoning_effort and text_verbosity are initialized (defensive check)
    if not hasattr(orchestrator_instance, "reasoning_effort"):
        orchestrator_instance.reasoning_effort = orchestrator_instance.agent_configs.get(
            "lucim_operation_model_generator", {}
        ).get("reasoning_effort", "medium")
    if not hasattr(orchestrator_instance, "text_verbosity"):
        orchestrator_instance.text_verbosity = orchestrator_instance.agent_configs.get(
            "lucim_operation_model_generator", {}
        ).get("text_verbosity", "medium")
    
    tv = orchestrator_instance.agent_configs["lucim_operation_model_generator"].get("text_verbosity", "medium")
    reff = orchestrator_instance.agent_configs["lucim_operation_model_generator"].get("reasoning_effort", "medium")
    run_dir = orchestrator_instance.fileio.create_run_directory(
        orchestrator_instance.timestamp, base_name, orchestrator_instance.model, 
        reff, tv, orchestrator_instance.selected_persona_set, version="v3-adk"
    )
    
    total_orchestration_start_time = time.time()
    orchestrator_instance.adk_monitor.start_monitoring()
    orchestrator_instance.logger.info(f"[ADK] Starting v3 pipeline processing for {base_name} (ADK mode)...")
    
    try:
        code_content = orchestrator_instance.fileio.read_netlogo_code(file_info["code_file"])
        operation_rules_content = orchestrator_instance.fileio.load_rules_operation_model()
        scenario_rules_content = orchestrator_instance.fileio.load_rules_scenario()
        netlogo_lucim_mapping_content = load_netlogo_lucim_mapping(orchestrator_instance)
    except (FileNotFoundError, Exception) as e:
        orchestrator_instance.logger.error(f"MANDATORY INPUT MISSING: {e}")
        return {"error": f"MANDATORY INPUT MISSING: {e}", "results": {}}
    
    # Local helper to ensure a directory exists and return its Path
    def _ensure_dir(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path

    # Prepare stage roots per new folder structure (prefixed with execution order)
    operation_model_root = _ensure_dir(run_dir / "1_lucim_operation_model")
    scenario_root = _ensure_dir(run_dir / "2_lucim_scenario")
    lucim_plantuml_diagram_root = _ensure_dir(run_dir / "3_lucim_plantuml_diagram")

    # Lightweight writers for per-iteration artifacts
    def _dump_json(folder: Path, filename: str, obj: Any) -> None:
        try:
            import json
            (folder / filename).write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    def _dump_text(folder: Path, filename: str, text: str) -> None:
        try:
            (folder / filename).write_text(text or "", encoding="utf-8")
        except Exception:
            pass

    def _write_reasoning(folder: Path, title: str, verdict_value: Any, violations_list: Any) -> None:
        try:
            verdict_str = "compliant" if (verdict_value is True or verdict_value == "compliant") else "non-compliant"
            vlist = violations_list if isinstance(violations_list, list) else []
            lines = [
                f"# {title}",
                "",
                f"- verdict: {verdict_str}",
                f"- violations: {len(vlist)}",
            ]
            if vlist:
                lines.append("")
                lines.append("## Violations")
                for v in vlist:
                    vid = (v or {}).get("id") or "unknown"
                    msg = (v or {}).get("message") or ""
                    loc = (v or {}).get("location") or (v or {}).get("line")
                    extra = f" (at {loc})" if loc is not None else ""
                    lines.append(f"- {vid}: {msg}{extra}")
            _dump_text(folder, "output-reasoning.md", "\n".join(lines))
        except Exception:
            _dump_text(folder, "output-reasoning.md", title)

    # Iterative Step 1: Operation Model (Generator → Auditor), with per-iteration persistence
    operation_model_attempt = 0
    prev_operation_model = None
    prev_operation_audit = None
    max_audit = getattr(orchestrator_instance, "max_audit", 3)
    while operation_model_attempt < max_audit:
        iter_index = operation_model_attempt + 1
        operation_model_iter_dir = _ensure_dir(operation_model_root / f"iter-{iter_index}")
        # New naming convention: subfolders under iter-<k>
        operation_model_generator_dir = _ensure_dir(operation_model_iter_dir / "1-generator")
        # 1.1 Generator (dual role: initial generation or corrective update)
        operation_model_result = orchestrator_instance.lucim_operation_model_generator_agent.generate_lucim_operation_model(
            code_content,
            netlogo_lucim_mapping_content,
            auditor_feedback=prev_operation_audit,
            previous_operation_model=prev_operation_model,
            output_dir=operation_model_generator_dir,
        )
        orchestrator_instance.processed_results["lucim_operation_model_generator"] = operation_model_result
        try:
            orchestrator_instance.lucim_operation_model_generator_agent.save_results(
                operation_model_result, base_name, orchestrator_instance.model, step_number=1, output_dir=operation_model_generator_dir
            )
        except Exception:
            pass

        operation_model_data = operation_model_result.get("data") or {}
        # 1.2 Auditor — outputs under lucim_operation_model/iter-<k>/2-auditor
        operation_model_auditor_dir = _ensure_dir(operation_model_iter_dir / "2-auditor")
        # Read raw content from generator's output-data.json (don't assume it's valid JSON)
        operation_model_raw_content = ""
        try:
            output_data_file = operation_model_generator_dir / "output-data.json"
            if output_data_file.exists():
                operation_model_raw_content = output_data_file.read_text(encoding="utf-8")
        except Exception:
            operation_model_raw_content = ""
        # Delegate input-instructions.md writing to the auditor (includes persona + rules + OM raw content)
        operation_model_audit = audit_operation_model(
            operation_model_raw_content,
            output_dir=str(operation_model_auditor_dir),
            model_name=orchestrator_instance.model
        )
        operation_model_core = extract_audit_core(operation_model_audit)
        orchestrator_instance.processed_results["lucim_operation_model_auditor"] = {
            "data": operation_model_core["data"],
            "verdict": operation_model_core["verdict"],
            "non-compliant-rules": operation_model_core["non_compliant_rules"],
            "coverage": operation_model_core["coverage"],
            "errors": operation_model_core["errors"],
        }
        # Persist auditor outputs using write_all_output_files (same as generator)
        from utils_response_dump import write_all_output_files
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        
        # Prepare results dict with all required fields for write_all_output_files
        auditor_results = {
            "reasoning_summary": operation_model_audit.get("reasoning_summary", ""),
            "data": operation_model_audit.get("data", {}),
            "errors": operation_model_audit.get("errors", []),
            "tokens_used": operation_model_audit.get("tokens_used", 0),
            "input_tokens": operation_model_audit.get("input_tokens", 0),
            "total_output_tokens": operation_model_audit.get("total_output_tokens", 0),
            "reasoning_tokens": operation_model_audit.get("reasoning_tokens", 0),
            "visible_output_tokens": operation_model_audit.get("visible_output_tokens", 0),
            "raw_usage": operation_model_audit.get("raw_usage", {}),
            "raw_response": operation_model_audit.get("raw_response", {})
        }
        
        write_all_output_files(
            output_dir=operation_model_auditor_dir,
            results=auditor_results,
            agent_type="lucim_operation_model_auditor",
            base_name=base_name,
            model=orchestrator_instance.model,
            timestamp=timestamp,
            reasoning_effort=reff,
            step_number=1
        )
        
        # Keep the old _write_reasoning call for backward compatibility
        _write_reasoning(
            operation_model_auditor_dir,
            "Operation Model audit iteration report",
            operation_model_core["verdict"],
            operation_model_audit.get("violations") or operation_model_core["non_compliant_rules"],
        )
        # Python deterministic audit (no-LLM)
        # Pass raw_content for LOM0-JSON-BLOCK-ONLY validation
        py_operation_model_audit = py_audit_environment(
            operation_model_data if isinstance(operation_model_data, dict) else {},
            raw_content=operation_model_raw_content
        )
        orchestrator_instance.processed_results.setdefault("python_audits", {})["operation_model"] = py_operation_model_audit
        # Build dict for compare_verdicts (maps non-compliant-rules to violations)
        operation_model_audit_for_compare = {
            "verdict": operation_model_audit.get("verdict"),
            "violations": operation_model_audit.get("non-compliant-rules") or []  # Map non-compliant-rules to violations for compare_verdicts
        }
        # Compare
        cmp_operation_model = compare_verdicts(operation_model_audit_for_compare, py_operation_model_audit)
        orchestrator_instance.processed_results.setdefault("auditor_vs_python", {})["operation_model"] = cmp_operation_model
        log_comparison(orchestrator_instance.logger, "Operation Model", cmp_operation_model)
        # Write markdown report listing non-compliant rules (dynamic extraction, no hardcoding)
        try:
            operation_model_md_path = operation_model_auditor_dir / "output_python_operation_model.md"
            violations_list = (py_operation_model_audit or {}).get("violations", [])
            violated = [v.get("id") for v in violations_list if v.get("id")]
            non_compliant = sorted(list(set(violated)))
            lines = [
                "# Python Audit — Operation Model",
                "",
                "## Non-compliant Rules",
            ]
            if non_compliant:
                # Group violations by rule ID and include extracted values
                violations_by_rule = {}
                for v in violations_list:
                    rule_id = v.get("id")
                    if rule_id:
                        if rule_id not in violations_by_rule:
                            violations_by_rule[rule_id] = []
                        violations_by_rule[rule_id].append(v)
                for rid in non_compliant:
                    rule_violations = violations_by_rule.get(rid, [])
                    lines.append(f"- {rid}")
                    for v in rule_violations:
                        extracted = v.get("extracted_values", {})
                        msg = v.get("message", "")
                        if extracted:
                            # Display line content prominently if available
                            line_content = extracted.get("line_content") or extracted.get("actor_content") or extracted.get("event_content")
                            if line_content:
                                # For JSON content (operation model), format as code block
                                if "actor_content" in extracted or "event_content" in extracted:
                                    lines.append(f"  - **Location**: {v.get('location', 'N/A')}")
                                    lines.append(f"  - **Content**:")
                                    lines.append(f"    ```json")
                                    for content_line in line_content.split("\n"):
                                        lines.append(f"    {content_line}")
                                    lines.append(f"    ```")
                                else:
                                    # For text content (scenario/diagram), show line number and content
                                    line_num = v.get("line", "?")
                                    lines.append(f"  - **Line {line_num}**: `{line_content}`")
                            # Show other extracted values if any
                            other_values = {k: v for k, v in extracted.items() if k not in ("line_content", "actor_content", "event_content")}
                            if other_values:
                                values_str = ", ".join([f"{k}: `{v}`" for k, v in other_values.items()])
                                lines.append(f"  - Additional info: {values_str}")
                        if msg:
                            lines.append(f"  - Message: {msg}")
            else:
                lines.append("- None")
            operation_model_md_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass
        # Decide to stop or continue
        is_compliant = operation_model_core["verdict"] == "compliant"
        if is_compliant:
            orchestrator_instance.logger.info(f"[ADK] Operation Model compliant at iteration {iter_index}; proceeding to Scenario stage.")
            break
        # Not compliant: if reached cap, proceed anyway per workflow rule
        if iter_index >= max_audit:
            orchestrator_instance.logger.warning(
                f"[ADK] Operation Model still non-compliant at cap (iteration {iter_index}); proceeding to Scenario stage as per MAX_AUDIT policy."
            )
            break
        # Prepare next iteration inputs
        prev_operation_model = operation_model_data
        prev_operation_audit = operation_model_audit
        operation_model_attempt += 1
        continue
    # end Operation Model loop

    # Validate Operation Model Generator output before proceeding to Scenario stage
    operation_model_data_for_scenario = orchestrator_instance.processed_results.get("lucim_operation_model_generator", {}).get("data")
    if not operation_model_data_for_scenario:
        orchestrator_instance.logger.error("[ADK] Operation Model Generator produced no valid data; cannot proceed to Scenario stage.")
        orchestrator_instance.adk_monitor.stop_monitoring()
        return {"status": "FAIL", "stage": "operation_model", "results": orchestrator_instance.processed_results}

    # Step 2: Scenario (Generator → Auditor) with iterations
    scen_attempt = 0
    prev_scenario = None
    prev_scenario_audit = None
    while scen_attempt < max_audit:
        iter_index = scen_attempt + 1
        scenario_iterator_dir = _ensure_dir(scenario_root / f"iter-{iter_index}")
        # New naming convention: subfolders under iter-<k>
        scenario_generator_dir = _ensure_dir(scenario_iterator_dir / "1-generator")
        # 2.1 Generator (dual role)
        scen_result = orchestrator_instance.lucim_scenario_generator_agent.generate_scenarios(
            operation_model_data_for_scenario,
            scenario_rules_content,
            scenario_auditor_feedback=prev_scenario_audit,
            previous_scenario=prev_scenario,
            output_dir=scenario_generator_dir
        )
        orchestrator_instance.processed_results["lucim_scenario_generator"] = scen_result
        try:
            orchestrator_instance.lucim_scenario_generator_agent.save_results(scen_result, base_name, orchestrator_instance.model, step_number=2, output_dir=scenario_generator_dir)
        except Exception:
            pass
        scen_data = scen_result.get("data")
        if scen_data is None:
            orchestrator_instance.logger.error("[ADK] Scenario synthesis produced no data.")
            orchestrator_instance.adk_monitor.stop_monitoring()
            return {"status": "FAIL", "stage": "scenario", "results": orchestrator_instance.processed_results}

        # 2.2 Auditor — outputs under lucim_scenario/iter-<k>/2-auditor
        scenario_auditor_dir = _ensure_dir(scenario_iterator_dir / "2-auditor")
        # Write input-instructions.md with exact system_prompt (TASK + persona + DSL + scenario text)
        try:
            # Load Scenario Auditor persona from persona set
            persona_scen_path = INPUT_PERSONA_DIR / orchestrator_instance.selected_persona_set / "PSN_LUCIM_Scenario_Auditor.md"
            persona_scen_text = persona_scen_path.read_text(encoding="utf-8") if persona_scen_path.exists() else ""
        except Exception:
            persona_scen_text = ""
        
        # Read raw content from generator's output-data.json (don't assume it's valid JSON)
        scen_raw_content = ""
        try:
            output_data_file = scenario_generator_dir / "output-data.json"
            if output_data_file.exists():
                scen_raw_content = output_data_file.read_text(encoding="utf-8")
        except Exception:
            scen_raw_content = ""
        
        # Also build PlantUML text for Python fallback auditor (if needed)
        scen_text = ""
        try:
            lines: list[str] = []
            # Handle new JSON format: { "data": { "scenario": {...} }, "errors": [] }
            scenario_to_process = None
            if isinstance(scen_data, dict):
                # New format: extract scenario from data.scenario
                if "data" in scen_data and isinstance(scen_data.get("data"), dict):
                    data_node = scen_data.get("data")
                    if "scenario" in data_node:
                        scenario_to_process = data_node.get("scenario")
                # Old format fallback: check if scen_data itself is a scenario dict or contains scenario key
                elif "scenario" in scen_data:
                    scenario_to_process = scen_data.get("scenario")
                # Also handle list format (old format)
                elif isinstance(scen_data, list) and len(scen_data) > 0:
                    # Old format: list of scenario objects
                    for item in scen_data:
                        if isinstance(item, dict) and "scenario" in item:
                            scenario_to_process = item.get("scenario")
                            break
            elif isinstance(scen_data, list):
                # Old format: list of scenario objects
                for item in scen_data:
                    if isinstance(item, dict) and "scenario" in item:
                        scenario_to_process = item.get("scenario")
                        break
            
            # Extract messages from scenario
            if scenario_to_process and isinstance(scenario_to_process, dict):
                msgs = scenario_to_process.get("messages", [])
                if isinstance(msgs, list):
                    for m in msgs:
                        if not isinstance(m, dict):
                            continue
                        src = m.get("source", "")
                        tgt = m.get("target", "")
                        name = m.get("event_name", m.get("name", ""))
                        params = m.get("parameters", "")
                        event_type = m.get("event_type", "")
                        # Determine arrow type based on event_type
                        # input_event: system --> actor (dashed)
                        # output_event: actor -> system (solid)
                        arrow = "-->" if event_type == "input_event" else "->"
                        # Normalize params to a simple paren suffix
                        params_str = str(params).strip()
                        if params_str and not params_str.startswith("("):
                            params_str = f"({params_str})"
                        elif not params_str:
                            params_str = "()"
                        lines.append(f"{src} {arrow} {tgt} : {name}{params_str}")
            scen_text = "\n".join(lines)
        except Exception as e:
            orchestrator_instance.logger.warning(f"[ADK] Failed to build PlantUML text from scenario: {e}")
            scen_text = ""

        # Pass raw content from output-data.json to LLM auditor (per LSC0 rule: scenario must be JSON only)
        # Note: We pass the raw file content as-is, without assuming it's valid JSON
        scen_audit = audit_scenario_text(scen_raw_content, output_dir=scenario_auditor_dir, model_name=orchestrator_instance.model)
        try:
            # Persona + scenario raw content + rules (insert rules once)
            # Note: scen_raw_content is the raw text from output-data.json, may or may not be valid JSON
            system_prompt_scenario = f"{persona_scen_text}\n\n{scenario_rules_content}\n\n<SCENARIO-TEXT>\n{scen_raw_content}\n</SCENARIO-TEXT>"
            _dump_text(scenario_auditor_dir, "input-instructions.md", system_prompt_scenario)
        except Exception:
            pass
        scen_core = extract_audit_core(scen_audit)
        orchestrator_instance.processed_results["lucim_scenario_auditor"] = {
            "data": scen_core["data"],
            "verdict": scen_core["verdict"],
            "non-compliant-rules": scen_core["non_compliant_rules"],
            "coverage": scen_core["coverage"],
            "errors": scen_core["errors"],
        }
        # Persist auditor outputs using write_all_output_files (same as generator)
        from utils_response_dump import write_all_output_files
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        
        # Prepare results dict with all required fields for write_all_output_files
        auditor_results = {
            "reasoning_summary": scen_audit.get("reasoning_summary", ""),
            "data": scen_audit.get("data", {}),
            "errors": scen_audit.get("errors", []),
            "tokens_used": scen_audit.get("tokens_used", 0),
            "input_tokens": scen_audit.get("input_tokens", 0),
            "total_output_tokens": scen_audit.get("total_output_tokens", 0),
            "reasoning_tokens": scen_audit.get("reasoning_tokens", 0),
            "visible_output_tokens": scen_audit.get("visible_output_tokens", 0),
            "raw_usage": scen_audit.get("raw_usage", {}),
            "raw_response": scen_audit.get("raw_response", {})
        }
        
        write_all_output_files(
            output_dir=scenario_auditor_dir,
            results=auditor_results,
            agent_type="lucim_scenario_auditor",
            base_name=base_name,
            model=orchestrator_instance.model,
            timestamp=timestamp,
            reasoning_effort=reff,
            step_number=2
        )
        
        # Keep the old _write_reasoning call for backward compatibility
        _write_reasoning(
            scenario_auditor_dir,
            "Scenario audit iteration report",
            scen_core["verdict"],
            scen_audit.get("violations") or scen_core["non_compliant_rules"],
        )
        # Python deterministic audit (no-LLM)
        # Pass JSON raw content first (preferred), fallback to PlantUML text
        # The audit_scenario function will automatically detect JSON vs PlantUML text
        # Pass operation model for rules requiring it (LSC5, LSC6, LSC12-LSC17)
        py_scen_audit = py_audit_scenario(
            scen_raw_content if scen_raw_content else scen_text,
            operation_model=operation_model_data_for_scenario
        )
        orchestrator_instance.processed_results.setdefault("python_audits", {})["scenario"] = py_scen_audit
        # Build dict for compare_verdicts (maps non-compliant-rules to violations)
        scen_audit_for_compare = {
            "verdict": scen_audit.get("verdict"),
            "violations": scen_audit.get("non-compliant-rules") or []  # Map non-compliant-rules to violations for compare_verdicts
        }
        # Compare
        cmp_scen = compare_verdicts(scen_audit_for_compare, py_scen_audit)
        orchestrator_instance.processed_results.setdefault("auditor_vs_python", {})["scenario"] = cmp_scen
        log_comparison(orchestrator_instance.logger, "Scenario", cmp_scen)
        # Write markdown report (dynamic extraction, no hardcoding)
        try:
            scenario_python_md_path = scenario_auditor_dir / "output_python_scenario.md"
            violations_list = (py_scen_audit or {}).get("violations", [])
            violated = [v.get("id") for v in violations_list if v.get("id")]
            non_compliant = sorted(list(set(violated)))
            lines = [
                "# Python Audit — Scenario",
                "",
                "## Non-compliant Rules",
            ]
            if non_compliant:
                # Group violations by rule ID and include extracted values
                violations_by_rule = {}
                for v in violations_list:
                    rule_id = v.get("id")
                    if rule_id:
                        if rule_id not in violations_by_rule:
                            violations_by_rule[rule_id] = []
                        violations_by_rule[rule_id].append(v)
                for rid in non_compliant:
                    rule_violations = violations_by_rule.get(rid, [])
                    lines.append(f"- {rid}")
                    for v in rule_violations:
                        extracted = v.get("extracted_values", {})
                        msg = v.get("message", "")
                        line_num = v.get("line", "?")
                        if extracted:
                            # Display line content prominently
                            line_content = extracted.get("line_content")
                            if line_content:
                                lines.append(f"  - **Line {line_num}**: `{line_content}`")
                            # Show other extracted values if any
                            other_values = {k: v for k, v in extracted.items() if k != "line_content"}
                            if other_values:
                                values_str = ", ".join([f"{k}: `{v}`" for k, v in other_values.items()])
                                lines.append(f"  - Additional info: {values_str}")
                        if msg:
                            lines.append(f"  - Message: {msg}")
            else:
                lines.append("- None")
            scenario_python_md_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass
        is_compliant_scen = scen_core["verdict"] == "compliant"
        if is_compliant_scen:
            orchestrator_instance.logger.info(f"[ADK] Scenario compliant at iteration {iter_index}; proceeding to PlantUML stage.")
            break
        if iter_index >= max_audit:
            orchestrator_instance.logger.warning(
                f"[ADK] Scenario still non-compliant at cap (iteration {iter_index}); proceeding to PlantUML as per MAX_AUDIT policy."
            )
            break
        prev_scenario = scen_result.get("data")
        prev_scenario_audit = scen_audit
        scen_attempt += 1
        continue

    # Step 3: PlantUML Diagram (Generator → Auditor) with iterations
    puml_attempt = 0
    prev_puml_audit = None
    prev_puml_diagram = None
    while puml_attempt < max_audit:
        iter_index = puml_attempt + 1
        puml_iter_dir = _ensure_dir(lucim_plantuml_diagram_root / f"iter-{iter_index}")
        # New naming convention: subfolders under iter-<k>
        writer_base_dir = _ensure_dir(puml_iter_dir / "1-generator")
        # Write input-instructions.md for writer with exact system_prompt (TASK + persona + DSL + scenario data)
        try:
            import json as _json
            persona_dir = INPUT_PERSONA_DIR / orchestrator_instance.selected_persona_set
            persona_writer_path = persona_dir / "PSN_LUCIM_PlantUML_Diagram_Generator.md"
            persona_writer_text = persona_writer_path.read_text(encoding="utf-8") if persona_writer_path.exists() else ""
            scen_data_json = _json.dumps(orchestrator_instance.processed_results["lucim_scenario_generator"]["data"], indent=2, ensure_ascii=False)
            diagram_rules_content = orchestrator_instance.fileio.load_rules_diagram()
            system_prompt_writer = f"{persona_writer_text}\n\n<SCENARIO-DATA>\n{scen_data_json}\n</SCENARIO-DATA>\n\n{diagram_rules_content}"
            _dump_text(writer_base_dir, "input-instructions.md", system_prompt_writer)
        except Exception:
            pass
        # 3.1 PlantUML Generator
        puml_write = orchestrator_instance.lucim_plantuml_diagram_generator_agent.generate_plantuml_diagrams(
            orchestrator_instance.processed_results["lucim_scenario_generator"]["data"],
            prev_puml_audit,
            prev_puml_diagram,
            output_dir=writer_base_dir,
        )
        orchestrator_instance.processed_results["lucim_plantuml_diagram_generator"] = puml_write
        try:
            orchestrator_instance.lucim_plantuml_diagram_generator_agent.save_results(puml_write, base_name, orchestrator_instance.model, step_number=3, output_dir=writer_base_dir)
        except Exception:
            pass

        # Resolve .puml path written by writer
        plantuml_file_path = orchestrator_instance.fileio.get_plantuml_file_path(writer_base_dir)
        if not plantuml_file_path or not orchestrator_instance.fileio.validate_plantuml_file(plantuml_file_path):
            orchestrator_instance.logger.error("[ADK] PlantUML file missing or invalid after writer. Ending workflow as FAIL.")
            orchestrator_instance.adk_monitor.stop_monitoring()
            return {"status": "FAIL", "stage": "lucim_plantuml_diagram_generator", "results": orchestrator_instance.processed_results}

        # 3.2 PlantUML Auditor — outputs under plantuml/iter-<k>/2-auditor
        auditor_iter_dir = _ensure_dir(puml_iter_dir / "2-auditor")
        audit_res = orchestrator_instance.lucim_plantuml_diagram_auditor_agent.audit_plantuml_diagrams(
            str(plantuml_file_path),
            output_dir=auditor_iter_dir
        )
        orchestrator_instance.processed_results["lucim_plantuml_diagram_auditor"] = audit_res
        try:
            orchestrator_instance.lucim_plantuml_diagram_auditor_agent.save_results(audit_res, base_name, orchestrator_instance.model, step_number=4, output_dir=auditor_iter_dir)
        except Exception:
            pass

        # Extract audit core (handles raw text in data field)
        puml_core = extract_audit_core(audit_res)
        orchestrator_instance.processed_results["lucim_plantuml_diagram_auditor"] = {
            "data": puml_core["data"],
            "verdict": puml_core["verdict"],
            "non-compliant-rules": puml_core["non_compliant_rules"],
            "coverage": puml_core["coverage"],
            "errors": puml_core["errors"],
        }
        # Build dict for compare_verdicts (maps non-compliant-rules to violations)
        puml_audit_for_compare = {
            "verdict": puml_core["verdict"],
            "violations": puml_core["non_compliant_rules"]  # Map non-compliant-rules to violations for compare_verdicts
        }
        verdict = puml_core["verdict"]
        # Python deterministic audit (no-LLM) on .puml text
        # Read raw content for LDR0-PLANTUML-BLOCK-ONLY validation
        try:
            import pathlib
            puml_text = pathlib.Path(str(plantuml_file_path)).read_text(encoding="utf-8")
            puml_raw_content = puml_text  # Use same content as raw for LDR0 validation
        except Exception:
            puml_text = ""
            puml_raw_content = ""
        # Pass raw_content for LDR0-PLANTUML-BLOCK-ONLY validation
        py_puml_audit = py_audit_diagram(puml_text, raw_content=puml_raw_content)
        orchestrator_instance.processed_results.setdefault("python_audits", {})["diagram"] = py_puml_audit
        # Compare agent 6 verdict vs python verdict (use puml_audit_for_compare with proper structure)
        cmp_puml = compare_verdicts(puml_audit_for_compare, py_puml_audit)
        orchestrator_instance.processed_results.setdefault("auditor_vs_python", {})["diagram"] = cmp_puml
        log_comparison(orchestrator_instance.logger, "Diagram", cmp_puml)
        # Write markdown report (dynamic extraction, no hardcoding)
        try:
            diag_md_path = auditor_iter_dir / "output_python_diagram.md"
            violations_list = (py_puml_audit or {}).get("violations", [])
            violated = [v.get("id") for v in violations_list if v.get("id")]
            non_compliant = sorted(list(set(violated)))
            lines = [
                "# Python Audit — Diagram",
                "",
                "## Non-compliant Rules",
            ]
            if non_compliant:
                # Group violations by rule ID and include extracted values
                violations_by_rule = {}
                for v in violations_list:
                    rule_id = v.get("id")
                    if rule_id:
                        if rule_id not in violations_by_rule:
                            violations_by_rule[rule_id] = []
                        violations_by_rule[rule_id].append(v)
                for rid in non_compliant:
                    rule_violations = violations_by_rule.get(rid, [])
                    lines.append(f"- {rid}")
                    for v in rule_violations:
                        extracted = v.get("extracted_values", {})
                        msg = v.get("message", "")
                        line_num = v.get("line", "?")
                        if extracted:
                            # Display line content prominently
                            line_content = extracted.get("line_content")
                            if line_content:
                                lines.append(f"  - **Line {line_num}**: `{line_content}`")
                            # Show other extracted values if any
                            other_values = {k: v for k, v in extracted.items() if k != "line_content"}
                            if other_values:
                                values_str = ", ".join([f"{k}: `{v}`" for k, v in other_values.items()])
                                lines.append(f"  - Additional info: {values_str}")
                        if msg:
                            lines.append(f"  - Message: {msg}")
            else:
                lines.append("- None")
            diag_md_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass
        is_compliant_puml = verdict in ("compliant", True)
        if is_compliant_puml:
            orchestrator_instance.logger.info(f"[ADK] PlantUML Diagram compliant at iteration {iter_index}; ending workflow.")
            break
        if iter_index >= max_audit:
            orchestrator_instance.logger.warning(
                f"[ADK] PlantUML Diagram still non-compliant at cap (iteration {iter_index}); ending workflow as per MAX_AUDIT policy."
            )
            break
        # Prepare next iteration: pass full audit report and previous diagram text/data
        prev_puml_audit = (audit_res or {}).get("data")
        try:
            prev_puml_diagram = plantuml_file_path.read_text(encoding="utf-8")
        except Exception:
            prev_puml_diagram = None
        puml_attempt += 1
        continue
    
    total_orchestration_time = time.time() - total_orchestration_start_time
    orchestrator_instance.execution_times["total_orchestration"] = total_orchestration_time
    
    orchestrator_instance.logger.info(f"[ADK] Workflow execution completed in {total_orchestration_time:.2f}s")
    orchestrator_instance.adk_monitor.stop_monitoring()
    orchestrator_instance.logger.info(f"[ADK] Generating ADK monitoring summary...")
    orchestrator_instance.adk_monitor.log_summary()
    
    orchestrator_instance.logger.info(f"Completed processing for {base_name}")
    orchestrator_instance.logger.info(f"Total orchestration time: {FormatUtils.format_duration(total_orchestration_time)}")
    
    orchestrator_instance.processed_results["execution_times"] = orchestrator_instance.execution_times.copy()
    orchestrator_instance.processed_results["token_usage"] = orchestrator_instance.token_usage.copy()
    orchestrator_instance.processed_results["detailed_timing"] = orchestrator_instance.detailed_timing.copy()
    
    adk_metrics_summary = orchestrator_instance.adk_monitor.get_metrics_summary()
    orchestrator_instance.processed_results["adk_metrics"] = adk_metrics_summary
    orchestrator_instance.logger.info(
        f"[ADK] ADK metrics summary: {adk_metrics_summary.get('total_agents_executed', 0)} agents executed, "
        f"{adk_metrics_summary.get('successful_executions', 0)} successful, "
        f"{adk_metrics_summary.get('failed_executions', 0)} failed, "
        f"{adk_metrics_summary.get('total_retries', 0)} retries"
    )
    
    return orchestrator_instance.processed_results

