#!/usr/bin/env python3
"""
Orchestrator Logging Utilities
Centralized logging and print functions for the NetLogo to LUCIM orchestrator.

Note: All references to "messir" have been updated to "lucim" for consistency
with the LUCIM/UCI domain modeling approach.
"""

import logging
from typing import Dict, Any, List
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
        # Determine success status for each step
        netlogo_abstract_syntax_extractor_success = results.get("ast", {}).get("data") is not None
        behavior_extractor_success = results.get("semantics", {}).get("data") is not None
        lucim_environment_success = results.get("lucim_operation_synthesizer", {}).get("data") is not None
        lucim_scenario_synthesizer_success = results.get("lucim_scenario_synthesizer", {}).get("data") is not None
        plantuml_writer_success = results.get("plantuml_writer", {}).get("data") is not None
        plantuml_lucim_auditor_success = results.get("plantuml_lucim_auditor", {}).get("data") is not None
        plantuml_lucim_corrector_success = results.get("plantuml_lucim_corrector", {}).get("data") is not None
        plantuml_lucim_final_auditor_success = results.get("plantuml_lucim_final_auditor", {}).get("data") is not None
        
        # Check if optional steps were executed
        plantuml_lucim_corrector_executed = "plantuml_lucim_corrector" in results
        plantuml_lucim_final_auditor_executed = "plantuml_lucim_final_auditor" in results
        
        self.logger.info(f"{base_name} results:")
        self.logger.info(f"  Step 1 - Syntax Parser: {'✓' if netlogo_abstract_syntax_extractor_success else '✗'}")
        self.logger.info(f"  Step 2 - Behavior Extractor: {'✓' if behavior_extractor_success else '✗'}")
        self.logger.info(f"  Step 3 - LUCIM Operation Synthesizer: {'✓' if lucim_environment_success else '✗'}")
        self.logger.info(f"  Step 4 - LUCIM Scenario Synthesizer: {'✓' if lucim_scenario_synthesizer_success else '✗'}")
        self.logger.info(f"  Step 5 - PlantUML Writer: {'✓' if plantuml_writer_success else '✗'}")
        self.logger.info(f"  Step 6 - PlantUML LUCIM Auditor: {'✓' if plantuml_lucim_auditor_success else '✗'}")
        
        if plantuml_lucim_corrector_executed:
            self.logger.info(f"  Step 7 - PlantUML LUCIM Corrector: {'✓' if plantuml_lucim_corrector_success else '✗'}")
        if plantuml_lucim_final_auditor_executed:
            self.logger.info(f"  Step 8 - PlantUML LUCIM Final Auditor: {'✓' if plantuml_lucim_final_auditor_success else '✗'}")
        else:
            self.logger.info(f"  Step 7 - PlantUML LUCIM Corrector: SKIPPED (diagrams already compliant)")
    
    def log_error_details(self, results: Dict[str, Any]) -> None:
        """Log detailed error information for failed steps."""
        for step_name, result in results.items():
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
        
        # Determine status for each agent
        netlogo_abstract_syntax_extractor_success = results.get("ast", {}).get("data") is not None
        behavior_extractor_success = results.get("semantics", {}).get("data") is not None
        lucim_environment_success = results.get("lucim_operation_synthesizer", {}).get("data") is not None
        lucim_scenario_synthesizer_success = results.get("lucim_scenario_synthesizer", {}).get("data") is not None
        plantuml_writer_success = results.get("plantuml_writer", {}).get("data") is not None
        plantuml_lucim_auditor_success = results.get("plantuml_lucim_auditor", {}).get("data") is not None
        plantuml_lucim_corrector_success = results.get("plantuml_lucim_corrector", {}).get("data") is not None
        plantuml_lucim_final_auditor_success = results.get("plantuml_lucim_final_auditor", {}).get("data") is not None
        
        # Check if optional steps were executed
        plantuml_lucim_corrector_executed = "plantuml_lucim_corrector" in results
        plantuml_lucim_final_auditor_executed = "plantuml_lucim_final_auditor" in results
        
        self.logger.info(f"   Step 1 - Syntax Parser Agent: {'✓ SUCCESS' if netlogo_abstract_syntax_extractor_success else '✗ FAILED'}")
        self.logger.info(f"   Step 2 - Behavior Extractor Agent: {'✓ SUCCESS' if behavior_extractor_success else '✗ FAILED'}")
        self.logger.info(f"   Step 3 - LUCIM Operation Synthesizer Agent: {'✓ SUCCESS' if lucim_environment_success else '✗ FAILED'}")
        self.logger.info(f"   Step 4 - LUCIM Scenario Synthesizer Agent: {'✓ SUCCESS' if lucim_scenario_synthesizer_success else '✗ FAILED'}")
        self.logger.info(f"   Step 5 - PlantUML Writer Agent: {'✓ SUCCESS' if plantuml_writer_success else '✗ FAILED'}")
        self.logger.info(f"   Step 6 - PlantUML LUCIM Auditor Agent: {'✓ SUCCESS' if plantuml_lucim_auditor_success else '✗ FAILED'}")
        
        if not plantuml_lucim_corrector_executed:
            self.logger.info(f"   Step 7 - PlantUML LUCIM Corrector Agent: ⏭️  SKIPPED (diagrams already compliant)")
        else:
            self.logger.info(f"   Step 7 - PlantUML LUCIM Corrector Agent: {'✓ SUCCESS' if plantuml_lucim_corrector_success else '✗ FAILED'}")
        
        if not plantuml_lucim_final_auditor_executed:
            self.logger.info(f"   Step 8 - PlantUML LUCIM Final Auditor Agent: ⏭️  SKIPPED (corrector was skipped or not required)")
        else:
            self.logger.info(f"   Step 8 - PlantUML LUCIM Final Auditor Agent: {'✓ SUCCESS' if plantuml_lucim_final_auditor_success else '✗ FAILED'}")
    
    def log_output_files(self, base_name: str, timestamp: str, model: str, results: Dict[str, Any]) -> None:
        """Log information about generated output files."""
        self.logger.info(f"\n📁 OUTPUT FILES GENERATED:")
        
        for result_key, result_data in results.items():
            if result_data and isinstance(result_data, dict):
                agent_type = result_data.get("agent_type", "unknown")
                if agent_type == "netlogo_abstract_syntax_extractor":
                    self.logger.info(f"   • Syntax Parser: {base_name}_{timestamp}_{model}_1a_netlogo_abstract_syntax_extractor_v1_*.md")
                elif agent_type == "behavior_extractor":
                    self.logger.info(f"   • Behavior Extractor: {base_name}_{timestamp}_{model}_1b_behavior_extractor_v1_*.json/md")
                elif agent_type == "lucim_operation_synthesizer":
                    self.logger.info(f"   • LUCIM Operation Synthesizer: {base_name}_{timestamp}_{model}_2_lucim_operation_v1_*.json/md")
                elif agent_type == "lucim_scenario_synthesizer":
                    self.logger.info(f"   • Scenarios: {base_name}_{timestamp}_{model}_3_scenario_v1_*.md")
                elif agent_type == "plantuml_writer":
                    self.logger.info(f"   • PlantUML Diagrams: {base_name}_{timestamp}_{model}_4_plantuml_*.json/md/.puml")
                elif agent_type == "plantuml_lucim_auditor":
                    self.logger.info(f"   • PlantUML LUCIM Audit: {base_name}_{timestamp}_{model}_5_lucim_audit_*.json/md/.puml")
                elif agent_type == "plantuml_lucim_corrector":
                    self.logger.info(f"   • PlantUML LUCIM Corrector: {base_name}_{timestamp}_{model}_7_lucim_corrector_*.json/md/.puml")
                elif agent_type == "plantuml_lucim_final_auditor":
                    self.logger.info(f"   • PlantUML LUCIM Final Auditor: {base_name}_{timestamp}_{model}_8_lucim_final_auditor_*.json/md/.puml")
    
    def log_pipeline_completion(self, successful_agents: int, total_agents: int, final_compliance: Dict[str, Any] = None) -> None:
        """Log pipeline completion status.
        
        Args:
            successful_agents: Number of successfully executed agents
            total_agents: Total number of agents that were executed (not skipped)
            final_compliance: Optional compliance status dict with 'status' key
        """
        self.logger.info(f"\n🎯 PIPELINE COMPLETION:")
        
        # Determine success based on compliance status and critical agents
        # For limited-agents pipeline, core agents are 1-4 (lucim_env, lucim_scenario, plantuml_writer, plantuml_auditor)
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
        self.logger.info(
            "   • Precision={:.2%} Recall={:.2%} Specificity={:.2%} Accuracy={:.2%} F1={:.2%}".format(
                metrics["precision"], metrics["recall"], metrics["specificity"], metrics["accuracy"], metrics["f1"]
            )
        )
