#!/usr/bin/env python3
"""
Orchestrator Logging Utilities
Centralized logging and print functions for the NetLogo to LUCIM orchestrator.

Note: All references to "messir" have been updated to "lucim" for consistency
with the LUCIM/UCI domain modeling approach.
"""

import logging
import re
from typing import Dict, Any, List, Set
from utils_format import FormatUtils


class OrchestratorLogger:
    """Centralized logging utilities for the orchestrator."""
    
    def __init__(self, logger: logging.Logger):
        """
        Initialize the orchestrator logger.
        
        Args:
            logger: The logger instance to use
        """
        self.logger = logger
    
    def log_agent_start(self, agent_name: str) -> None:
        """Log the start of an agent execution."""
        self.logger.info(f"🚀 Starting {agent_name} agent execution...")
    
    def log_agent_completion(self, agent_name: str, duration: float, 
                           tokens_used: int = 0, input_tokens: int = 0, 
                           output_tokens: int = 0, reasoning_tokens: int = 0) -> None:
        """
        Log the completion of an agent execution with token usage.
        
        Args:
            agent_name: Name of the agent
            duration: Execution duration in seconds
            tokens_used: Total tokens used
            input_tokens: Input tokens
            output_tokens: Output tokens
            reasoning_tokens: Reasoning tokens
        """
        self.logger.info(f"✅ {agent_name} completed in {FormatUtils.format_duration(duration)}")
        
        if tokens_used > 0:
            # Calculate visible output tokens
            visible_output_tokens = max(output_tokens - reasoning_tokens, 0)
            total_output_tokens = visible_output_tokens + reasoning_tokens
            
            self.logger.info(f"   Input Tokens = {input_tokens:,}")
            self.logger.info(f"   Output Tokens = {total_output_tokens:,} (reasoning = {reasoning_tokens:,}, visibleOutput={visible_output_tokens:,})")
            self.logger.info(f"   Total Tokens = {tokens_used:,}")
        else:
            self.logger.info(f"   Token usage: Not available")
    
    def log_agent_error(self, agent_name: str, duration: float, error: str) -> None:
        """Log an agent execution error."""
        self.logger.error(f"❌ {agent_name} failed after {FormatUtils.format_duration(duration)}: {error}")
    
    def log_file_warning(self, message: str) -> None:
        """Log a file-related warning."""
        self.logger.warning(message)
    
    def log_config_success(self, message: str) -> None:
        """Log a configuration success message."""
        self.logger.info(f"OK: {message}")
    
    def log_config_warning(self, message: str) -> None:
        """Log a configuration warning message."""
        self.logger.warning(f"[WARNING] {message}")
    
    def log_heartbeat(self, base_name: str) -> None:
        """Log a heartbeat message during parallel processing."""
        self.logger.info(f"[heartbeat] Parallel first stage still running for {base_name}...")
    
    def log_early_exit(self, reason: str) -> None:
        """Log an early exit from the orchestration."""
        self.logger.info(f"Step 6 verdict is compliant. Ending flow gracefully. {reason}")
    
    def log_workflow_status(self, base_name: str, results: Dict[str, Any]) -> None:
        """
        Log the workflow status for a base name.
        
        Args:
            base_name: The base name being processed
            results: The results dictionary
        """
        # When a stage fails early, the orchestrator returns
        # {"status":"FAIL", "stage": "...", "results": <actual-per-agent-results>}
        # Normalize to the inner results so status checks are correct
        normalized_results = results.get("results") if isinstance(results, dict) and "results" in results else results
        # Determine success status for each step (v3 6-step workflow)
        op_model_gen_success = normalized_results.get("lucim_operation_model_generator", {}).get("data") is not None
        op_model_audit_success = normalized_results.get("lucim_operation_model_auditor", {}).get("data") is not None
        scenario_gen_success = normalized_results.get("lucim_scenario_generator", {}).get("data") is not None
        scenario_audit_success = normalized_results.get("lucim_scenario_auditor", {}).get("data") is not None
        plantuml_gen_success = normalized_results.get("lucim_plantuml_diagram_generator", {}).get("data") is not None
        plantuml_audit_success = normalized_results.get("lucim_plantuml_diagram_auditor", {}).get("data") is not None
        
        # No corrector/final auditor in v3 pipeline
        
        self.logger.info(f"{base_name} results:")
        self.logger.info(f"  Step 1 - LUCIM Operation Model Generator: {'✓' if op_model_gen_success else '✗'}")
        self.logger.info(f"  Step 2 - LUCIM Operation Model Auditor: {'✓' if op_model_audit_success else '✗'}")
        self.logger.info(f"  Step 3 - LUCIM Scenario Generator: {'✓' if scenario_gen_success else '✗'}")
        self.logger.info(f"  Step 4 - LUCIM Scenario Auditor: {'✓' if scenario_audit_success else '✗'}")
        self.logger.info(f"  Step 5 - LUCIM PlantUML Diagram Generator: {'✓' if plantuml_gen_success else '✗'}")
        self.logger.info(f"  Step 6 - LUCIM PlantUML Diagram Auditor: {'✓' if plantuml_audit_success else '✗'}")
    
    def log_error_details(self, results: Dict[str, Any]) -> None:
        """Log detailed error information for failed steps."""
        normalized_results = results.get("results") if isinstance(results, dict) and "results" in results else results
        for step_name, result in normalized_results.items():
            if result and isinstance(result, dict) and result.get("errors"):
                error_count = len(result["errors"])
                self.logger.warning(f"    {step_name} errors: {error_count} found")
    
    def log_execution_timing(self, execution_times: Dict[str, float]) -> None:
        """Log execution timing breakdown."""
        self.logger.info(f"\n⏱️  EXECUTION TIMING:")
        total_time = execution_times.get("total_orchestration", 0)
        self.logger.info(f"   Total Orchestration Time: {FormatUtils.format_duration(total_time)}")
        
        # Calculate and display individual agent times
        total_agent_time = 0
        agent_times = []
        
        for agent_name, duration in execution_times.items():
            if agent_name != "total_orchestration" and duration > 0:
                agent_times.append((agent_name, duration))
                total_agent_time += duration
        
        # Sort agents by execution time (descending)
        agent_times.sort(key=lambda x: x[1], reverse=True)
        
        self.logger.info(f"   Total Agent Execution Time: {FormatUtils.format_duration(total_agent_time)}")
        self.logger.info(f"   Overhead Time: {FormatUtils.format_duration(total_time - total_agent_time)}")
        
        if agent_times:
            self.logger.info(f"   \n   📈 AGENT TIMING BREAKDOWN:")
            for agent_name, agent_time in agent_times:
                percentage = (agent_time / total_agent_time * 100) if total_agent_time > 0 else 0
                self.logger.info(f"      {agent_name}: {FormatUtils.format_duration(agent_time)} ({percentage:.1f}%)")
    
    def log_detailed_agent_status(self, results: Dict[str, Any]) -> None:
        """Log detailed agent status information."""
        self.logger.info(f"\n🔍 DETAILED AGENT STATUS:")
        
        # Determine status for each agent (v3 6-step workflow)
        normalized_results = results.get("results") if isinstance(results, dict) and "results" in results else results
        op_model_gen_success = normalized_results.get("lucim_operation_model_generator", {}).get("data") is not None
        op_model_audit_success = normalized_results.get("lucim_operation_model_auditor", {}).get("data") is not None
        scenario_gen_success = normalized_results.get("lucim_scenario_generator", {}).get("data") is not None
        scenario_audit_success = normalized_results.get("lucim_scenario_auditor", {}).get("data") is not None
        plantuml_gen_success = normalized_results.get("lucim_plantuml_diagram_generator", {}).get("data") is not None
        plantuml_audit_success = normalized_results.get("lucim_plantuml_diagram_auditor", {}).get("data") is not None
        
        def _verdict_text(agent_key: str) -> str:
            """Return 'compliant' | 'non-compliant' | 'N/A' from auditor data."""
            data = (normalized_results.get(agent_key) or {}).get("data")
            if not isinstance(data, dict):
                return "N/A"
            verdict = data.get("verdict")
            if not isinstance(verdict, str):
                return "N/A"
            v = verdict.strip().lower()
            if v in ("compliant", "non-compliant"):
                return v
            return "N/A"
        
        # No corrector/final auditor in v3 pipeline
        
        self.logger.info(f"   Step 1 - LUCIM Operation Model Generator Agent: {'✓ SUCCESS' if op_model_gen_success else '✗ FAILED'}")
        self.logger.info(
            f"   Step 2 - LUCIM Operation Model Auditor Agent: {'✓ SUCCESS' if op_model_audit_success else '✗ FAILED'}"
            f" [{_verdict_text('lucim_operation_model_auditor')}]"
        )
        self.logger.info(f"   Step 3 - LUCIM Scenario Generator Agent: {'✓ SUCCESS' if scenario_gen_success else '✗ FAILED'}")
        self.logger.info(
            f"   Step 4 - LUCIM Scenario Auditor Agent: {'✓ SUCCESS' if scenario_audit_success else '✗ FAILED'}"
            f" [{_verdict_text('lucim_scenario_auditor')}]"
        )
        self.logger.info(f"   Step 5 - LUCIM PlantUML Diagram Generator Agent: {'✓ SUCCESS' if plantuml_gen_success else '✗ FAILED'}")
        self.logger.info(
            f"   Step 6 - LUCIM PlantUML Diagram Auditor Agent: {'✓ SUCCESS' if plantuml_audit_success else '✗ FAILED'}"
            f" [{_verdict_text('lucim_plantuml_diagram_auditor')}]"
        )
    
    def log_audit_analysis(self, results: Dict[str, Any]) -> None:
        """Log a consolidated AUDIT ANALYSIS comparing agent vs python auditors with TP/TN/FP/FN.

        Notes:
        - Classification is defined with positive = compliant.
          TP: agent=compliant,     python=compliant
          TN: agent=non-compliant, python=non-compliant
          FP: agent=compliant,     python=non-compliant
          FN: agent=non-compliant, python=compliant
        - If a side is missing (agent or python), classification is shown as N/A.
        """
        try:
            def _to_bool(verdict_value: Any) -> bool:
                # Normalize to bool compliance: True means compliant
                if isinstance(verdict_value, bool):
                    return verdict_value
                if isinstance(verdict_value, str):
                    v = verdict_value.strip().lower()
                    if v in ("compliant", "true", "yes", "ok", "pass"):
                        return True
                    if v in ("non-compliant", "false", "no", "fail"):
                        return False
                # Fallback: consider falsy as non-compliant
                return bool(verdict_value)

            def _extract_agent_bool(stage_key: str) -> Any:
                data = (results.get(stage_key) or {}).get("data") or {}
                verdict = data.get("verdict")
                if verdict is None:
                    return None
                return _to_bool(verdict)

            def _extract_python_bool(py_key: str) -> Any:
                py_audits = results.get("python_audits") or {}
                py = py_audits.get(py_key)
                if not isinstance(py, dict):
                    return None
                verdict = py.get("verdict")
                if verdict is None:
                    return None
                return _to_bool(verdict)

            def _cls(agent_ok: Any, py_ok: Any) -> tuple[str, str]:
                # agent_ok/py_ok are booleans where True=compliant
                if agent_ok is None or py_ok is None:
                    return ("N/A", "➖")
                # Positive = compliant
                if agent_ok and py_ok:
                    return ("TRUE POSITIVE", "✅")
                if (not agent_ok) and (not py_ok):
                    return ("TRUE NEGATIVE", "❎")
                if agent_ok and (not py_ok):
                    return ("FALSE POSITIVE", "🟥")
                # else: (not agent_ok) and py_ok
                return ("FALSE NEGATIVE", "❌")

            self.logger.info("\n📊 AUDIT ANALYSIS:")
            tp = tn = fp = fn = 0
            stages = [
                ("Operation Model", "lucim_operation_model_auditor", "operation_model"),
                ("Scenario", "lucim_scenario_auditor", "scenario"),
                ("Diagram", "lucim_plantuml_diagram_auditor", "diagram"),
            ]
            # Preload python auditors data (deterministic)
            python_audits = results.get("python_audits") or {}

            # Dynamically infer rule universe per stage by parsing auditors' docstrings
            def _infer_rule_universe_for(py_key: str) -> Set[str]:
                """Infer the set of rule IDs implemented by the deterministic auditor for a stage.

                Strategy: import module and parse its module-level docstring list of rules.
                This avoids hard-coding and adapts automatically if auditors evolve.
                """
                module_map = {
                    "operation_model": "utils_audit_operation_model",
                    "scenario": "utils_audit_scenario",
                    "diagram": "utils_audit_diagram",
                }
                mod_name = module_map.get(py_key)
                if not mod_name:
                    return set()
                try:
                    mod = __import__(mod_name, fromlist=["*"])
                    doc = getattr(mod, "__doc__", None) or ""
                except Exception:
                    return set()
                rules: Set[str] = set()
                try:
                    for raw_line in (doc or "").splitlines():
                        line = raw_line.strip()
                        if not line.startswith("-"):
                            continue
                        # Try to extract rule id token appearing first in the line
                        # Examples: "- LEM1-ACT-TYPE-FORMAT: ...", "- SS1-MESSAGE-DIRECTIONALITY: ..."
                        token = line.lstrip("- ").split()[0]
                        # Trim trailing punctuation like ':' if present
                        token = token.rstrip(":")
                        # Validate token shape (must contain an uppercase rule-like pattern)
                        if re.match(r"^[A-Z]{2,}[A-Z0-9-]*$", token):
                            rules.add(token)
                except Exception:
                    return set()
                return rules

            for title, agent_key, py_key in stages:
                agent_ok = _extract_agent_bool(agent_key)
                py_ok = _extract_python_bool(py_key)
                cls_text, emoji = _cls(agent_ok, py_ok)
                def _fmt(v: Any) -> str:
                    if v is None:
                        return "N/A"
                    return "compliant" if v else "non-compliant"
                self.logger.info(
                    f" - {title}: agent={_fmt(agent_ok)}, python={_fmt(py_ok)} — {emoji} {cls_text}"
                )

                # Per-stage deterministic python auditor details
                try:
                    py_stage = python_audits.get(py_key) or {}
                    violations_list = py_stage.get("violations") or []
                    # Count per rule id (frequency of occurrences)
                    freq: Dict[str, int] = {}
                    distinct_ids: set = set()
                    for v in violations_list:
                        rid = str((v or {}).get("id") or "").strip()
                        if not rid:
                            continue
                        distinct_ids.add(rid)
                        freq[rid] = freq.get(rid, 0) + 1
                    # Denominator inferred dynamically from auditor docstring
                    universe = _infer_rule_universe_for(py_key)
                    total_rules = len(universe)
                    non_compliant_rules = len({r for r in distinct_ids if (not universe) or (r in universe)})

                    # Sorted by descending frequency, then by id
                    sorted_rules: List[str] = []
                    if freq:
                        sorted_pairs = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
                        sorted_rules = [f"{rid} ({count})" for rid, count in sorted_pairs]

                    # Emit compact lines under each stage line
                    if total_rules > 0:
                        self.logger.info(
                            f"   • Python non-compliant: {non_compliant_rules}/{total_rules} rules"
                        )
                    else:
                        self.logger.info(
                            f"   • Python non-compliant: {non_compliant_rules} rules"
                        )
                    if sorted_rules:
                        # Grouping is implicit by stage title; list most violated first
                        self.logger.info(
                            f"   • Top violations: {', '.join(sorted_rules)}"
                        )
                except Exception:
                    # Keep summary resilient — do not break if structure differs
                    pass
                if cls_text == "TRUE POSITIVE":
                    tp += 1
                elif cls_text == "TRUE NEGATIVE":
                    tn += 1
                elif cls_text == "FALSE POSITIVE":
                    fp += 1
                elif cls_text == "FALSE NEGATIVE":
                    fn += 1

            # Totals
            self.logger.info("")
            self.logger.info(f"   Totals: TP = {tp}, TN = {tn}, FP = {fp}, FN = {fn}")
            self.logger.info(f"   True Positive = {tp}")
            self.logger.info(f"   True Negative = {tn}")
            self.logger.info(f"   False Positive = {fp}")
            self.logger.info(f"   False Negative = {fn}")
            # Derived metrics (positive = compliant)
            try:
                # Compute numeric values when denominators exist; otherwise mark as N/A
                denom_p = (tp + fp)
                denom_r = (tp + fn)
                precision_val = (tp / denom_p) if denom_p > 0 else None
                recall_val = (tp / denom_r) if denom_r > 0 else None
                if precision_val is not None and recall_val is not None and (precision_val + recall_val) > 0:
                    f1_val = (2 * precision_val * recall_val / (precision_val + recall_val))
                else:
                    f1_val = None

                def _fmt_pct(v: Any) -> str:
                    if v is None:
                        return "N/A"
                    return f"{v:.2%}"

                self.logger.info(
                    "   Metrics: Precision=TP/(TP+FP), Recall=TP/(TP+FN), F1=2PR/(P+R)"
                )
                self.logger.info(
                    "   Precision = {p}, Recall = {r}, F1-score = {f}".format(
                        p=_fmt_pct(precision_val), r=_fmt_pct(recall_val), f=_fmt_pct(f1_val)
                    )
                )
                # Short natural-language interpretation
                try:
                    def _grade(v: float) -> str:
                        if v >= 0.80:
                            return "high"
                        if v >= 0.60:
                            return "good"
                        if v >= 0.40:
                            return "fair"
                        return "low"

                    # Only emit interpretation when precision/recall exist
                    if precision_val is None or recall_val is None:
                        raise Exception("insufficient data for interpretation")
                    pr_diff = precision_val - recall_val
                    balance_note = None
                    if pr_diff >= 0.20:
                        balance_note = "Precision notably higher than recall (more conservative)."
                    elif pr_diff <= -0.20:
                        balance_note = "Recall notably higher than precision (more permissive)."

                    summary = f"P={_grade(precision_val)}, R={_grade(recall_val)}, F1={_grade(f1_val) if f1_val is not None else 'n/a'}."
                    if balance_note:
                        interpretation = f"{summary} {balance_note}"
                    else:
                        interpretation = summary

                    # Log scoring ranges used for grading
                    self.logger.info(
                        "   Scoring ranges: high>=0.80, good>=0.60, fair>=0.40, else low"
                    )
                    self.logger.info(f"   Interpretation: {interpretation}")
                except Exception:
                    pass
            except Exception:
                # Never break logging due to metric computation edge cases
                pass
        except Exception:
            # Do not break orchestration summary on logging failures
            self.logger.info("\n📊 AUDIT ANALYSIS: (unavailable)")
    
    def log_output_files(self, base_name: str, timestamp: str, model: str, results: Dict[str, Any]) -> None:
        """Log information about generated output files."""
        self.logger.info(f"\n📁 OUTPUT FILES GENERATED:")
        
        normalized_results = results.get("results") if isinstance(results, dict) and "results" in results else results
        for result_key, result_data in normalized_results.items():
            if result_data and isinstance(result_data, dict):
                agent_type = result_data.get("agent_type", "unknown")
                if agent_type == "lucim_operation_model_generator":
                    self.logger.info(f"   • Operation Model: output-data.json")
                elif agent_type == "lucim_operation_model_auditor":
                    self.logger.info(f"   • Operation Model Audit: output-data.json")
                elif agent_type == "lucim_scenario_generator":
                    self.logger.info(f"   • Scenarios: output-data.json")
                elif agent_type == "lucim_scenario_auditor":
                    self.logger.info(f"   • Scenario Audit: output-data.json")
                elif agent_type == "lucim_plantuml_diagram_generator":
                    self.logger.info(f"   • PlantUML Diagram: diagram.puml + output-data.json")
                elif agent_type == "lucim_plantuml_diagram_auditor":
                    self.logger.info(f"   • PlantUML Diagram Audit: output-data.json")
    
    def log_pipeline_completion(self, successful_agents: int, total_agents: int, final_compliance: Dict[str, Any] = None) -> None:
        """Log pipeline completion status.
        
        Args:
            successful_agents: Number of successfully executed agents
            total_agents: Total number of agents that were executed (not skipped)
            final_compliance: Optional compliance status dict with 'status' key
        """
        self.logger.info(f"\n🎯 PIPELINE COMPLETION:")
        
        # Determine success based on compliance status and critical agents
        # For limited-agents pipeline, core agents are 1-4 (lucim_env, lucim_scenario, lucim_plantuml_diagram_generator, plantuml_auditor)
        core_agents_count = 4
        compliance_verified = final_compliance and final_compliance.get("status") == "VERIFIED"
        
        if successful_agents == total_agents:
            self.logger.info(f"   🎉 FULL SUCCESS: All {total_agents} agents completed successfully!")
            self.logger.info(f"   📋 Final output includes LUCIM-compliant PlantUML sequence diagrams")
        elif compliance_verified and successful_agents >= core_agents_count:
            # Success: compliance verified with all core agents completed (conditional agents may be skipped)
            self.logger.info(f"   🎉 SUCCESS: Core pipeline completed with LUCIM compliance verified!")
            self.logger.info(f"   📋 {successful_agents}/{total_agents} agents executed (conditional steps may have been skipped)")
            self.logger.info(f"   ✅ Compliance status: VERIFIED")
        elif successful_agents >= 6:  # At least full pipeline completed (all 6 agents)
            self.logger.info(f"   ⚠️  PARTIAL SUCCESS: {successful_agents}/{total_agents} agents completed")
            self.logger.info(f"   📋 Some outputs available, but pipeline incomplete")
        else:
            self.logger.info(f"   ❌ PIPELINE FAILED: Only {successful_agents}/{total_agents} agents completed")
            self.logger.info(f"   📋 Limited outputs available")
    
    def log_compliance_status(self, final_compliance: Dict[str, Any]) -> None:
        """Log final compliance status."""
        self.logger.info(f"\n🔍 COMPLIANCE STATUS:")
        if final_compliance["status"] == "VERIFIED":
            self.logger.info(f"   ✅ FINAL COMPLIANCE: VERIFIED")
            self.logger.info(f"   🎯 Result: Final audit confirms LUCIM compliance")
        elif final_compliance["status"] == "NON-COMPLIANT":
            self.logger.info(f"   ❌ FINAL COMPLIANCE: NON-COMPLIANT")
            self.logger.info(f"   📊 Result: One or more LUCIM rules were violated")
        else:
            self.logger.info(f"   ❓ COMPLIANCE STATUS: UNKNOWN")
            self.logger.info(f"   ⚠️  Result: No authoritative compliance verdict available")

    def log_auditor_metrics(self, initial_audit: Dict[str, Any], final_audit: Dict[str, Any]) -> None:
        """Compute and log confusion-matrix metrics comparing step 6 vs step 8 auditors.

        Convention: positive = compliant.
        """
        try:
            from utils_metrics import compute_audit_confusion_metrics
            metrics = compute_audit_confusion_metrics(initial_audit, final_audit, positive_label="compliant")
        except Exception as e:
            self.logger.warning(f"Failed to compute auditor metrics: {e}")
            return

        self.logger.info("\n📊 AUDITOR METRICS (positive = compliant)")
        self.logger.info(
            f"   • TP={metrics['tp']} FP={metrics['fp']} TN={metrics['tn']} FN={metrics['fn']} (universe={metrics['universe_size']})"
        )
        def _fmt_pct(v: Any) -> str:
            try:
                return f"{float(v):.2%}"
            except Exception:
                return "N/A"
        # If there is no universe to compare, percentages are not meaningful
        if (metrics.get("universe_size") or 0) <= 0:
            self.logger.info(
                "   • Precision=N/A Recall=N/A Specificity=N/A Accuracy=N/A F1=N/A"
            )
        else:
            self.logger.info(
                "   • Precision={p} Recall={r} Specificity={s} Accuracy={a} F1={f}".format(
                    p=_fmt_pct(metrics.get("precision")),
                    r=_fmt_pct(metrics.get("recall")),
                    s=_fmt_pct(metrics.get("specificity")),
                    a=_fmt_pct(metrics.get("accuracy")),
                    f=_fmt_pct(metrics.get("f1")),
                )
            )
