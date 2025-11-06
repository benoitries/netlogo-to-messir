import types
from pathlib import Path
import json
import asyncio
import sys
from pathlib import Path as _P

# Add project code directory to sys.path for imports without package hyphens
_CODE_DIR = _P(__file__).parent.parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from utils_orchestrator_v3_process import process_netlogo_file_v3_adk  # type: ignore


class _FakeFileIO:
    def __init__(self, tmpdir: Path):
        self.tmpdir = tmpdir
    def create_run_directory(self, ts, base_name, model, reff, tv, persona_set, version="v3-adk"):
        d = self.tmpdir / "runs" / base_name
        d.mkdir(parents=True, exist_ok=True)
        return d
    def read_netlogo_code(self, p):
        return "to setup\nend"
    def load_rules_operation_model(self):
        return "RULES-OP"
    def load_rules_scenario(self):
        return "RULES-SCEN"
    def load_rules_diagram(self):
        return "RULES-DIAG"
    def get_plantuml_file_path(self, writer_base_dir: Path):
        # The generator writes diagram in its own folder; emulate existence
        puml = writer_base_dir / "diagram.puml"
        if not puml.exists():
            puml.write_text("@startuml\n@enduml", encoding="utf-8")
        return puml
    def validate_plantuml_file(self, p):
        return True


class _NullLogger:
    def info(self, *a, **k):
        pass
    def warning(self, *a, **k):
        pass
    def error(self, *a, **k):
        pass


class _NullMonitor:
    def start_monitoring(self):
        pass
    def stop_monitoring(self):
        pass
    def log_summary(self):
        pass
    def get_metrics_summary(self):
        return {"total_agents_executed": 0, "successful_executions": 0, "failed_executions": 0, "total_retries": 0}


def _fake_operation_generator(verdict_sequence):
    state = {"prev": None, "i": 0, "audits": verdict_sequence}
    class _Gen:
        def generate_lucim_operation_model(self, code, mapping, auditor_feedback, previous_operation_model, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            # Generate minimal data with iteration index
            data = {"iteration": state["i"] + 1}
            return {"data": data}
        def save_results(self, res, base_name, model, step_number, output_dir):
            (output_dir / "output-data.json").write_text(json.dumps(res), encoding="utf-8")
    class _Aud:
        def __call__(self, data):
            i = state["i"]
            verdict = state["audits"][i]
            state["i"] += 1
            return {"verdict": verdict}
    return _Gen(), _Aud()


def _fake_scenario_generator(verdict_sequence):
    state = {"i": 0, "audits": verdict_sequence}
    class _Gen:
        def generate_scenarios(self, op_data, rules, scenario_auditor_feedback, previous_scenario, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            return {"data": [{"scenario": {"messages": []}}]}
        def save_results(self, res, base_name, model, step_number, output_dir):
            (output_dir / "output-data.json").write_text(json.dumps(res), encoding="utf-8")
    class _Aud:
        def __call__(self, text):
            i = state["i"]
            verdict = state["audits"][i]
            state["i"] += 1
            return {"verdict": verdict}
    return _Gen(), _Aud()


def _fake_plantuml_generator(verdict_sequence):
    state = {"i": 0, "audits": verdict_sequence}
    class _Gen:
        def generate_plantuml_diagrams(self, scen_data, *_):
            return {"data": {}}
        def save_results(self, res, base_name, model, step_number, output_dir):
            (output_dir / "diagram.puml").write_text("@startuml\n@enduml", encoding="utf-8")
    class _Aud:
        def audit_plantuml_diagrams(self, puml_path: str):
            i = state["i"]
            verdict = state["audits"][i]
            state["i"] += 1
            return {"data": {"verdict": verdict}}
        def save_results(self, res, base_name, model, step_number, output_dir):
            (output_dir / "output-data.json").write_text(json.dumps(res), encoding="utf-8")
    return _Gen(), _Aud()


async def _run_with(orchestrator, tmpdir: Path):
    file_info = {"base_name": "caseX", "code_file": tmpdir / "model.nlogo"}
    (tmpdir / "model.nlogo").write_text("to setup\nend", encoding="utf-8")
    return await process_netlogo_file_v3_adk(orchestrator, file_info)


def test_iterative_flows_cap_and_compliance(tmp_path: Path):
    # Build a minimal orchestrator instance with fakes
    orch = types.SimpleNamespace()
    orch.agent_configs = {"lucim_operation_model_generator": {"text_verbosity": "medium", "reasoning_effort": "medium"}}
    orch.timestamp = "2025-11-05"
    orch.model = "gpt-5-mini-2025-08-07"
    orch.selected_persona_set = "persona-v3-limited-agents"
    orch.fileio = _FakeFileIO(tmp_path)
    orch.logger = _NullLogger()
    orch.adk_monitor = _NullMonitor()
    orch.execution_times = {}
    orch.token_usage = {}
    orch.detailed_timing = {}
    # Cap
    orch.max_audit = 3

    # Fakes: Operation compliant at 2, Scenario cap reached (non-compliant), PlantUML compliant at 2
    op_gen, op_aud = _fake_operation_generator([False, True])
    scen_gen, scen_aud = _fake_scenario_generator([False, False, False])
    puml_gen, puml_aud = _fake_plantuml_generator([False, True])

    orch.lucim_operation_model_generator_agent = op_gen
    orch.lucim_scenario_generator_agent = scen_gen
    orch.lucim_plantuml_diagram_generator_agent = puml_gen

    # wrap auditors in expected API
    # Note: keep real imports available if needed later
    # from agent_lucim_operation_auditor import audit_operation_model as real_op_audit
    # from agent_lucim_scenario_auditor import audit_scenario_text as real_scen_audit
    # from agent_lucim_plantuml_diagram_auditor import PlantUMLDiagramAuditorAgent as RealDiagAud

    # Monkeypatch module-level functions/classes by injection via SimpleNamespace attributes
    import utils_orchestrator_v3_process as mod  # type: ignore
    mod.audit_operation_model = op_aud
    mod.audit_scenario_text = scen_aud
    orch.lucim_plantuml_diagram_auditor_agent = puml_aud

    # Run
    asyncio.run(_run_with(orch, tmp_path))

    # Assert per-iteration folders exist
    run_dir = tmp_path / "runs" / "caseX"
    assert (run_dir / "lucim_operation_model" / "iter-1" / "1-generator").exists()
    assert (run_dir / "lucim_operation_model" / "iter-1" / "2-auditor").exists()
    assert (run_dir / "lucim_operation_model" / "iter-2" / "1-generator").exists()
    assert (run_dir / "lucim_operation_model" / "iter-2" / "2-auditor").exists()

    assert (run_dir / "lucim_scenario" / "iter-1" / "1-generator").exists()
    assert (run_dir / "lucim_scenario" / "iter-1" / "2-auditor").exists()
    assert (run_dir / "lucim_scenario" / "iter-3" / "2-auditor").exists()

    assert (run_dir / "lucim_plantuml_diagram" / "iter-1" / "1-generator").exists()
    assert (run_dir / "lucim_plantuml_diagram" / "iter-2" / "2-auditor").exists()


