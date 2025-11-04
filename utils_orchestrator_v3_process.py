#!/usr/bin/env python3
"""
Orchestrator V3 Process File Utility
Handles the processing of a single NetLogo file.
"""

import time
from typing import Dict, Any
from pathlib import Path

from utils_format import FormatUtils
from utils_orchestrator_v3_persona_config import load_netlogo_lucim_mapping
from utils_adk_workflow_steps_builder import build_v3_workflow_steps
from utils_adk_workflow_executor import execute_adk_workflow_steps
from agent_lucim_operation_auditor import audit_environment_model
from agent_lucim_scenario_auditor import audit_scenario_text
from utils_config_constants import LUCIM_RULES_FILE
from utils_task_loader import load_task_instruction
from utils_orchestrator_v3_persona_config import INPUT_PERSONA_DIR
from utils_audit_operation_model import audit_environment as py_audit_environment
from utils_audit_scenario import audit_scenario as py_audit_scenario
from utils_audit_diagram import audit_diagram as py_audit_diagram
from utils_audit_compare import compare_verdicts, log_comparison
import pathlib


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
    
    tv = orchestrator_instance.agent_configs["lucim_operation_synthesizer"].get("text_verbosity", "medium")
    reff = orchestrator_instance.agent_configs["lucim_operation_synthesizer"].get("reasoning_effort", "medium")
    run_dir = orchestrator_instance.fileio.create_run_directory(
        orchestrator_instance.timestamp, base_name, orchestrator_instance.model, 
        reff, tv, orchestrator_instance.selected_persona_set, version="v3-adk"
    )
    
    total_orchestration_start_time = time.time()
    orchestrator_instance.adk_monitor.start_monitoring()
    orchestrator_instance.logger.info(f"[ADK] Starting v3 pipeline processing for {base_name} (ADK mode)...")
    
    try:
        code_content = orchestrator_instance.fileio.read_netlogo_code(file_info["code_file"])
        lucim_dsl_content = orchestrator_instance.fileio.load_lucim_dsl_content()
        netlogo_lucim_mapping_content = load_netlogo_lucim_mapping(orchestrator_instance)
    except (FileNotFoundError, Exception) as e:
        orchestrator_instance.logger.error(f"MANDATORY INPUT MISSING: {e}")
        return {"error": f"MANDATORY INPUT MISSING: {e}", "results": {}}
    
    # Local helper to ensure a directory exists and return its Path
    def _ensure_dir(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path

    # Prepare stage roots per new folder structure
    env_root = _ensure_dir(run_dir / "lucim_operation")
    scen_root = _ensure_dir(run_dir / "lucim_scenario")
    puml_root = _ensure_dir(run_dir / "plantuml")

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

    # Iterative Step 1: Environment synth → audit (no corrector)
    env_attempt = 0
    while env_attempt <= getattr(orchestrator_instance, "max_correction", 2):
        # Operation Synthesizer output: lucim_operation/0_synthesizer
        env_base_dir = _ensure_dir(env_root / "0_synthesizer")
        # 1.1 Synthesizer
        env_result = orchestrator_instance.lucim_operation_synthesizer_agent.synthesize_lucim_operation_from_source_code(
            code_content, lucim_dsl_content, netlogo_lucim_mapping_content, output_dir=env_base_dir
        )
        orchestrator_instance.processed_results["lucim_operation_synthesizer"] = env_result
        try:
            orchestrator_instance.lucim_operation_synthesizer_agent.save_results(env_result, base_name, orchestrator_instance.model, step_number=1, output_dir=env_base_dir)
        except Exception:
            pass

        env_data = env_result.get("data") or {}
        # 1.2 Auditor — outputs under lucim_operation/<N>_iter/iter-N-auditor
        env_iter_dir = _ensure_dir(env_root / f"{env_attempt + 1}_iter")
        env_auditor_dir = _ensure_dir(env_iter_dir / f"iter-{env_attempt + 1}-auditor")
        # Write input-instructions.md with exact system_prompt (TASK + persona + DSL)
        try:
            persona_dir = INPUT_PERSONA_DIR / orchestrator_instance.selected_persona_set
            persona_operation_model_rules_path = persona_dir / "RULES_LUCIM_Operation_model.md"
            task_content_operation_model = load_task_instruction(1, "LUCIM Operation Model Auditor (step 1)")
            operation_model_rules_text = (
                persona_operation_model_rules_path.read_text(encoding="utf-8")
                if persona_operation_model_rules_path.exists() else ""
            )
            system_prompt_operation_model = f"{task_content_operation_model}\n\n{operation_model_rules_text}\n\n{lucim_dsl_content}"
            _dump_text(env_auditor_dir, "input-instructions.md", system_prompt_operation_model)
        except Exception:
            pass
        env_audit = audit_environment_model(env_data if isinstance(env_data, dict) else {})
        orchestrator_instance.processed_results["lucim_operation_auditor"] = {"data": env_audit}
        # Persist auditor outputs in iter folder using reference schema
        _dump_json(env_auditor_dir, "output-data.json", _normalize_audit_for_output(env_audit))
        _write_reasoning(env_auditor_dir, "Environment audit iteration report", env_audit.get("verdict"), env_audit.get("violations"))
        _dump_json(env_auditor_dir, "output-response.json", {"data": env_audit, "errors": []})
        _dump_json(env_auditor_dir, "output-raw_response.json", {"agent": "python-environment-auditor", "input_kind": "environment-data", "output": _normalize_audit_for_output(env_audit)})
        # Python deterministic audit (no-LLM)
        py_env_audit = py_audit_environment(env_data if isinstance(env_data, dict) else {})
        orchestrator_instance.processed_results.setdefault("python_audits", {})["environment"] = py_env_audit
        # Compare
        cmp_env = compare_verdicts(env_audit, py_env_audit)
        orchestrator_instance.processed_results.setdefault("auditor_vs_python", {})["environment"] = cmp_env
        log_comparison(orchestrator_instance.logger, "Environment", cmp_env)
        # Write markdown report listing non-compliant then compliant rules
        try:
            env_md_path = env_iter_dir / "output_python_environment.md"
            known_env_rules = {
                "AS1-SYS-UNIQUE","SS3-SYS-UNIQUE-IDENTITY","NAM1-ACT-INSTANCE-FORMAT","NAM2-ACT-TYPE-FORMAT",
                "AS3-SYS-ACT-ALLOWED-EVENTS","AS4-SYS-NO-SELF-LOOP","AS6-ACT-NO-ACT-ACT-EVENTS",
                "AS8-IE-EVENT-DIRECTION","AS9-OE-EVENT-DIRECTION"
            }
            violated = [v.get("id") for v in (py_env_audit or {}).get("violations", []) if v.get("id")]
            violated_set = set(violated)
            compliant = sorted(list(known_env_rules - violated_set))
            non_compliant = sorted(list(violated_set))
            lines = [
                "# Python Audit — Environment",
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
            env_md_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass
        if bool(env_audit.get("verdict", False)):
            break

        # No automatic corrector: abort after first failed audit to keep pipeline deterministic
        orchestrator_instance.logger.error("[ADK] Environment audit is non-compliant and no corrector is available. Ending workflow as FAIL.")
        orchestrator_instance.adk_monitor.stop_monitoring()
        return {"status": "FAIL", "stage": "environment", "results": orchestrator_instance.processed_results}

    # Step 2: Scenario synthesis → auditor → corrector loop
    scen_attempt = 0
    while scen_attempt <= getattr(orchestrator_instance, "max_correction", 2):
        # Scenario Synthesizer output: lucim_scenario/0_synthesizer
        scen_base_dir = _ensure_dir(scen_root / "0_synthesizer")
        # 2.1 Synthesizer
        scen_result = orchestrator_instance.lucim_scenario_synthesizer_agent.write_scenarios(
            orchestrator_instance.processed_results["lucim_operation_synthesizer"]["data"],
            lucim_dsl_content,
            output_dir=scen_base_dir
        )
        orchestrator_instance.processed_results["lucim_scenario_synthesizer"] = scen_result
        try:
            orchestrator_instance.lucim_scenario_synthesizer_agent.save_results(scen_result, base_name, orchestrator_instance.model, step_number=2, output_dir=scen_base_dir)
        except Exception:
            pass
        scen_data = scen_result.get("data")
        if scen_data is None:
            orchestrator_instance.logger.error("[ADK] Scenario synthesis produced no data.")
            orchestrator_instance.adk_monitor.stop_monitoring()
            return {"status": "FAIL", "stage": "scenario", "results": orchestrator_instance.processed_results}

        # 2.2 Auditor — create a simple textual serialization for audit_scenario_text
        scen_iter_dir = _ensure_dir(scen_root / f"{scen_attempt + 1}_iter")
        scen_auditor_dir = _ensure_dir(scen_iter_dir / f"iter-{scen_attempt + 1}-auditor")
        # Write input-instructions.md with exact system_prompt (TASK + persona + DSL + scenario text)
        try:
            persona_dir = INPUT_PERSONA_DIR / orchestrator_instance.selected_persona_set
            persona_scen_path = persona_dir / "RULES_LUCIM_Scenario.md"
            task_content_scen = load_task_instruction(2, "LUCIM Scenario Auditor (step 2)")
            persona_scen_text = persona_scen_path.read_text(encoding="utf-8") if persona_scen_path.exists() else ""
        except Exception:
            task_content_scen = ""
            persona_scen_text = ""
        try:
            # naive text: one scenario concatenated messages
            scen_text = "\n\n".join(
                [
                    "\n".join(
                        [
                            f"{m.get('from','')} -> {m.get('to','')} : {m.get('name','')}(...)" for m in item.get("scenario", {}).get("messages", [])
                        ]
                    ) for item in (scen_data or []) if isinstance(item, dict)
                ]
            )
        except Exception:
            scen_text = ""

        scen_audit = audit_scenario_text(scen_text)
        try:
            system_prompt_scen = f"{task_content_scen}\n\n{persona_scen_text}\n\n<SCENARIO-TEXT>\n{scen_text}\n</SCENARIO-TEXT>\n\n{lucim_dsl_content}"
            _dump_text(scen_auditor_dir, "input-instructions.md", system_prompt_scen)
        except Exception:
            pass
        orchestrator_instance.processed_results["lucim_scenario_auditor"] = {"data": scen_audit}
        # Persist scenario auditor outputs in iter folder using reference schema
        _dump_json(scen_auditor_dir, "output-data.json", _normalize_audit_for_output(scen_audit))
        _write_reasoning(scen_auditor_dir, "Scenario audit iteration report", scen_audit.get("verdict"), scen_audit.get("violations"))
        _dump_json(scen_auditor_dir, "output-response.json", {"data": scen_audit, "errors": []})
        _dump_json(scen_auditor_dir, "output-raw_response.json", {"agent": "python-scenario-auditor", "input_kind": "scenario-text", "output": _normalize_audit_for_output(scen_audit)})
        # Python deterministic audit (no-LLM)
        py_scen_audit = py_audit_scenario(scen_text)
        orchestrator_instance.processed_results.setdefault("python_audits", {})["scenario"] = py_scen_audit
        # Compare
        cmp_scen = compare_verdicts(scen_audit, py_scen_audit)
        orchestrator_instance.processed_results.setdefault("auditor_vs_python", {})["scenario"] = cmp_scen
        log_comparison(orchestrator_instance.logger, "Scenario", cmp_scen)
        # Write markdown report
        try:
            scen_md_path = scen_iter_dir / "output_python_scenario.md"
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
            scen_md_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass
        if bool(scen_audit.get("verdict", False)):
            break

        # 2.3 Corrector — outputs under lucim_scenario/<N>_iter/iter-N-corrector
        if scen_attempt >= getattr(orchestrator_instance, "max_correction", 2):
            orchestrator_instance.logger.error("[ADK] Scenario audit failed after max_correction attempts. Ending workflow as FAIL.")
            orchestrator_instance.adk_monitor.stop_monitoring()
            return {"status": "FAIL", "stage": "scenario", "results": orchestrator_instance.processed_results}

        scen_corrector_dir = _ensure_dir(scen_iter_dir / f"iter-{scen_attempt + 1}-corrector")
        corr_scen = orchestrator_instance.lucim_scenario_corrector_agent.correct_scenarios(
            scen_data if isinstance(scen_data, list) else [], scen_audit, lucim_dsl_content
        )
        orchestrator_instance.processed_results["lucim_scenario_corrector"] = corr_scen
        # Persist scenario corrector outputs in iter folder
        _dump_json(scen_corrector_dir, "output-data.json", corr_scen)
        _dump_text(scen_corrector_dir, "output-reasoning.md", "Scenario correction iteration report")
        _dump_json(scen_corrector_dir, "output-response.json", corr_scen)
        _dump_json(scen_corrector_dir, "output-raw_response.json", {"agent": "python-scenario-corrector", "input_kind": "scenario-audit+data", "output": corr_scen})
        scen_attempt += 1

    # Step 3: PlantUML writer → auditor → corrector loop
    puml_attempt = 0
    while puml_attempt <= getattr(orchestrator_instance, "max_correction", 2):
        # PlantUML Writer output: plantuml/0_writer
        writer_base_dir = _ensure_dir(puml_root / "0_writer")
        # Write input-instructions.md for writer with exact system_prompt (TASK + persona + DSL + scenario data)
        try:
            import json as _json
            persona_dir = INPUT_PERSONA_DIR / orchestrator_instance.selected_persona_set
            persona_writer_path = persona_dir / "PSN_LUCIM_PlantUML_Diagram_Generator.md"
            task_content_writer = load_task_instruction(5, "PlantUML Writer (step 5)")
            persona_writer_text = persona_writer_path.read_text(encoding="utf-8") if persona_writer_path.exists() else ""
            scen_data_json = _json.dumps(orchestrator_instance.processed_results["lucim_scenario_synthesizer"]["data"], indent=2, ensure_ascii=False)
            system_prompt_writer = f"{task_content_writer}\n\n{persona_writer_text}\n\n<SCENARIO-DATA>\n{scen_data_json}\n</SCENARIO-DATA>\n\n{lucim_dsl_content}"
            _dump_text(writer_base_dir, "input-instructions.md", system_prompt_writer)
        except Exception:
            pass
        # 3.1 PlantUML Writer
        puml_write = orchestrator_instance.plantuml_writer_agent.generate_plantuml_diagrams(
            orchestrator_instance.processed_results["lucim_scenario_synthesizer"]["data"],
        )
        orchestrator_instance.processed_results["plantuml_writer"] = puml_write
        try:
            orchestrator_instance.plantuml_writer_agent.save_results(puml_write, base_name, orchestrator_instance.model, step_number=3, output_dir=writer_base_dir)
        except Exception:
            pass

        # Resolve .puml path written by writer
        plantuml_file_path = orchestrator_instance.fileio.get_plantuml_file_path(writer_base_dir)
        if not plantuml_file_path or not orchestrator_instance.fileio.validate_plantuml_file(plantuml_file_path):
            orchestrator_instance.logger.error("[ADK] PlantUML file missing or invalid after writer. Ending workflow as FAIL.")
            orchestrator_instance.adk_monitor.stop_monitoring()
            return {"status": "FAIL", "stage": "plantuml_writer", "results": orchestrator_instance.processed_results}

        # 3.2 PlantUML Auditor — outputs under plantuml/<N>_iter/iter-N-auditor
        auditor_iter_parent = _ensure_dir(puml_root / f"{puml_attempt + 1}_iter")
        auditor_iter_dir = _ensure_dir(auditor_iter_parent / f"iter-{puml_attempt + 1}-auditor")
        audit_res = orchestrator_instance.plantuml_lucim_auditor_agent.audit_plantuml_diagrams(
            str(plantuml_file_path), str(LUCIM_RULES_FILE)
        )
        orchestrator_instance.processed_results["plantuml_lucim_auditor"] = audit_res
        try:
            orchestrator_instance.plantuml_lucim_auditor_agent.save_results(audit_res, base_name, orchestrator_instance.model, step_number=4, output_dir=auditor_iter_dir)
        except Exception:
            pass

        verdict = (audit_res or {}).get("data", {}).get("verdict")
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
        if verdict in ("compliant", True):
            break

        # No PlantUML corrector available: abort after failed audit
        orchestrator_instance.logger.error("[ADK] PlantUML audit is non-compliant and no corrector is available. Ending workflow as FAIL.")
        orchestrator_instance.adk_monitor.stop_monitoring()
        return {"status": "FAIL", "stage": "plantuml", "results": orchestrator_instance.processed_results}
    
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

