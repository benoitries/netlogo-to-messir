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
from utils_audit_operation_model import audit_environment as py_audit_environment
from utils_audit_scenario import audit_scenario as py_audit_scenario
from utils_audit_diagram import audit_diagram as py_audit_diagram
from utils_audit_compare import compare_verdicts, log_comparison


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

    def _normalize_audit_for_output(audit: Any) -> Dict[str, Any]:
        """Normalize any auditor dict to the reference schema used by PlantUML auditor.

        Output shape:
        {
          "verdict": "compliant"|"non-compliant",
          "non-compliant-rules": [ {"id": str, ...}, ... ] | [],
          "coverage": { "total_rules_in_dsl": "0", "evaluated": [], "not_applicable": [], "missing_evaluation": [] }
        }
        """
        try:
            verdict_raw = (audit or {}).get("verdict")
            if isinstance(verdict_raw, bool):
                verdict = "compliant" if verdict_raw else "non-compliant"
            else:
                verdict = str(verdict_raw) if verdict_raw in ("compliant", "non-compliant") else ("compliant" if verdict_raw else "non-compliant")
            # Map common field names
            rules = (audit or {}).get("non-compliant-rules")
            if rules is None:
                rules = (audit or {}).get("violations") or []
            coverage = (audit or {}).get("coverage") or {
                "total_rules_in_dsl": "0",
                "evaluated": [],
                "not_applicable": [],
                "missing_evaluation": []
            }
            return {
                "verdict": verdict,
                "non-compliant-rules": rules,
                "coverage": coverage
            }
        except Exception:
            return {
                "verdict": "non-compliant",
                "non-compliant-rules": [],
                "coverage": {
                    "total_rules_in_dsl": "0",
                    "evaluated": [],
                    "not_applicable": [],
                    "missing_evaluation": []
                }
            }

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
        # Delegate input-instructions.md writing to the auditor (includes persona + rules + OM JSON)
        operation_model_audit = audit_operation_model(
            operation_model_data if isinstance(operation_model_data, dict) else {},
            output_dir=str(operation_model_auditor_dir),
            model_name=orchestrator_instance.model
        )
        orchestrator_instance.processed_results["lucim_operation_model_auditor"] = {"data": operation_model_audit}
        # Persist auditor outputs in iter folder using reference schema
        _dump_json(operation_model_auditor_dir, "output-data.json", _normalize_audit_for_output(operation_model_audit))
        _write_reasoning(operation_model_auditor_dir, "Operation Model audit iteration report", operation_model_audit.get("verdict"), operation_model_audit.get("violations"))
        _dump_json(operation_model_auditor_dir, "output-response-full.json", {"data": operation_model_audit, "errors": []})
        # Use raw_response from audit function if available, otherwise fallback to simplified format
        raw_response_data = operation_model_audit.get("raw_response")
        if raw_response_data is not None:
            _dump_json(operation_model_auditor_dir, "output-response-raw.json", raw_response_data)
        else:
            _dump_json(operation_model_auditor_dir, "output-response-raw.json", {"agent": "python-operation-model-auditor", "input_kind": "operation-model-data", "output": _normalize_audit_for_output(operation_model_audit)})
        # Python deterministic audit (no-LLM)
        py_operation_model_audit = py_audit_environment(operation_model_data if isinstance(operation_model_data, dict) else {})
        orchestrator_instance.processed_results.setdefault("python_audits", {})["operation_model"] = py_operation_model_audit
        # Compare
        cmp_operation_model = compare_verdicts(operation_model_audit, py_operation_model_audit)
        orchestrator_instance.processed_results.setdefault("auditor_vs_python", {})["operation_model"] = cmp_operation_model
        log_comparison(orchestrator_instance.logger, "Operation Model", cmp_operation_model)
        # Write markdown report listing non-compliant then compliant rules
        try:
            operation_model_md_path = operation_model_auditor_dir / "output_python_operation_model.md"
            known_env_rules = {
                "AS1-SYS-UNIQUE","SS3-SYS-UNIQUE-IDENTITY","NAM1-ACT-INSTANCE-FORMAT","NAM2-ACT-TYPE-FORMAT",
                "AS3-SYS-ACT-ALLOWED-EVENTS","AS4-SYS-NO-SELF-LOOP","AS6-ACT-NO-ACT-ACT-EVENTS",
                "AS8-IE-EVENT-DIRECTION","AS9-OE-EVENT-DIRECTION"
            }
            violated = [v.get("id") for v in (py_operation_model_audit or {}).get("violations", []) if v.get("id")]
            violated_set = set(violated)
            compliant = sorted(list(known_env_rules - violated_set))
            non_compliant = sorted(list(violated_set))
            lines = [
                "# Python Audit — Operation Model",
                "",
                "## Non-compliant Rules",
            ]
            if non_compliant:
                lines += [f"- {rid}" for rid in non_compliant]
            else:
                lines.append("- None")
            lines += [
                "",
                "## Compliant Rules",
            ]
            if compliant:
                lines += [f"- {rid}" for rid in compliant]
            else:
                lines.append("- None (no rules recognized)")
            operation_model_md_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass
        # Decide to stop or continue
        is_compliant = bool(operation_model_audit.get("verdict", False)) or (
            (operation_model_audit or {}).get("verdict") == "compliant"
        )
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
            orchestrator_instance.processed_results["lucim_operation_model_generator"]["data"],
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
        try:
            # Build a readable message list: source -> target : event_name(params)
            lines: list[str] = []
            for item in (scen_data or []):
                if not isinstance(item, dict):
                    continue
                msgs = (item.get("scenario", {}) or {}).get("messages", [])
                if not isinstance(msgs, list):
                    continue
                for m in msgs:
                    if not isinstance(m, dict):
                        continue
                    src = m.get("source", "")
                    tgt = m.get("target", "")
                    name = m.get("event_name", m.get("name", ""))
                    params = m.get("parameters", "")
                    # Normalize params to a simple paren suffix
                    params_str = str(params).strip()
                    if params_str and not params_str.startswith("("):
                        params_str = f"({params_str})"
                    elif not params_str:
                        params_str = "()"
                    lines.append(f"{src} -> {tgt} : {name}{params_str}")
            scen_text = "\n".join(lines)
        except Exception:
            scen_text = ""

        scen_audit = audit_scenario_text(scen_text, model_name=orchestrator_instance.model)
        try:
            # Persona + scenario text + rules (insert rules once)
            system_prompt_scenario = f"{persona_scen_text}\n\n{scenario_rules_content}\n\n<SCENARIO-TEXT>\n{scen_text}\n</SCENARIO-TEXT>"
            _dump_text(scenario_auditor_dir, "input-instructions.md", system_prompt_scenario)
        except Exception:
            pass
        orchestrator_instance.processed_results["lucim_scenario_auditor"] = {"data": scen_audit}
        # Persist scenario auditor outputs in iter folder using reference schema
        _dump_json(scenario_auditor_dir, "output-data.json", _normalize_audit_for_output(scen_audit))
        _write_reasoning(scenario_auditor_dir, "Scenario audit iteration report", scen_audit.get("verdict"), scen_audit.get("violations"))
        _dump_json(scenario_auditor_dir, "output-response-full.json", {"data": scen_audit, "errors": []})
        # Use raw_response from audit function if available, otherwise fallback to simplified format
        raw_response_data = scen_audit.get("raw_response")
        if raw_response_data is not None:
            _dump_json(scenario_auditor_dir, "output-response-raw.json", raw_response_data)
        else:
            _dump_json(scenario_auditor_dir, "output-response-raw.json", {"agent": "python-scenario-auditor", "input_kind": "scenario-text", "output": _normalize_audit_for_output(scen_audit)})
        # Python deterministic audit (no-LLM)
        py_scen_audit = py_audit_scenario(scen_text)
        orchestrator_instance.processed_results.setdefault("python_audits", {})["scenario"] = py_scen_audit
        # Compare
        cmp_scen = compare_verdicts(scen_audit, py_scen_audit)
        orchestrator_instance.processed_results.setdefault("auditor_vs_python", {})["scenario"] = cmp_scen
        log_comparison(orchestrator_instance.logger, "Scenario", cmp_scen)
        # Write markdown report
        try:
            scenario_python_md_path = scenario_auditor_dir / "output_python_scenario.md"
            known_scen_rules = {
                "SS1-MESSAGE-DIRECTIONALITY","AS3-SYS-ACT-ALLOWED-EVENTS","AS4-SYS-NO-SELF-LOOP","AS6-ACT-NO-ACT-ACT-EVENTS",
                "TCS4-IE-SYNTAX","TCS5-OE-SYNTAX","AS8-IE-EVENT-DIRECTION","AS9-OE-EVENT-DIRECTION"
            }
            violated = [v.get("id") for v in (py_scen_audit or {}).get("violations", []) if v.get("id")]
            violated_set = set(violated)
            compliant = sorted(list(known_scen_rules - violated_set))
            non_compliant = sorted(list(violated_set))
            lines = [
                "# Python Audit — Scenario",
                "",
                "## Non-compliant Rules",
            ]
            if non_compliant:
                lines += [f"- {rid}" for rid in non_compliant]
            else:
                lines.append("- None")
            lines += [
                "",
                "## Compliant Rules",
            ]
            if compliant:
                lines += [f"- {rid}" for rid in compliant]
            else:
                lines.append("- None (no rules recognized)")
            scenario_python_md_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass
        is_compliant_scen = bool(scen_audit.get("verdict", False)) or ((scen_audit or {}).get("verdict") == "compliant")
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

        # Safely extract verdict, handling None audit_res or None data
        audit_data = (audit_res or {}).get("data") if audit_res else None
        if audit_data is None or not isinstance(audit_data, dict):
            audit_data = {}
        verdict = audit_data.get("verdict")
        # Python deterministic audit (no-LLM) on .puml text
        try:
            import pathlib
            puml_text = pathlib.Path(str(plantuml_file_path)).read_text(encoding="utf-8")
        except Exception:
            puml_text = ""
        py_puml_audit = py_audit_diagram(puml_text)
        orchestrator_instance.processed_results.setdefault("python_audits", {})["diagram"] = py_puml_audit
        # Compare agent 6 verdict vs python verdict
        cmp_puml = compare_verdicts((audit_res or {}).get("data"), py_puml_audit)
        orchestrator_instance.processed_results.setdefault("auditor_vs_python", {})["diagram"] = cmp_puml
        log_comparison(orchestrator_instance.logger, "Diagram", cmp_puml)
        # Write markdown report
        try:
            diag_md_path = auditor_iter_dir / "output_python_diagram.md"
            known_diag_rules = {
                "AS2-SYS-DECLARED-FIRST","AS5-ACT-DECLARED-AFTER-SYS","SS3-SYS-UNIQUE-IDENTITY","SS1-MESSAGE-DIRECTIONALITY",
                "AS4-SYS-NO-SELF-LOOP","AS6-ACT-NO-ACT-ACT-EVENTS","TCS10-AB-NO-ACTIVATION-BAR-ON-SYSTEM","TCS9-AB-SEQUENCE",
                "AS8-IE-EVENT-DIRECTION","AS9-OE-EVENT-DIRECTION"
            }
            violated = [v.get("id") for v in (py_puml_audit or {}).get("violations", []) if v.get("id")]
            violated_set = set(violated)
            compliant = sorted(list(known_diag_rules - violated_set))
            non_compliant = sorted(list(violated_set))
            lines = [
                "# Python Audit — Diagram",
                "",
                "## Non-compliant Rules",
            ]
            if non_compliant:
                lines += [f"- {rid}" for rid in non_compliant]
            else:
                lines.append("- None")
            lines += [
                "",
                "## Compliant Rules",
            ]
            if compliant:
                lines += [f"- {rid}" for rid in compliant]
            else:
                lines.append("- None (no rules recognized)")
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

