#!/usr/bin/env python3
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
TODAY_TAG = '20250827'

# Matches lines like:
# "✅ syntax_parser completed in 84.16s..."
COMP_LINE = re.compile(r'^.*completed in\s+([0-9]+\.[0-9]+|[0-9]+)s')
# Or AGENT EXECUTION DETAILS lines like:
# "syntax_parser             ✓ SUCCESS  84.16s ..."
DETAIL_LINE = re.compile(r'^.*SUCCESS\s+([0-9]+\.[0-9]+|[0-9]+)s')

STEP_ORDER = [
    ('lucim_operation_model_generator', 1),
    ('lucim_operation_model_auditor', 2),
    ('lucim_scenario_generator', 3),
    ('lucim_scenario_auditor', 4),
    ('lucim_plantuml_diagram_generator', 5),
    ('lucim_plantuml_diagram_auditor', 6)
]

# Accept any model token (no hard-coded names); model part excludes underscores
ORCH_RE = re.compile(r'^(.*?)_(\d{8})_(\d{4})_([^_]+)_orchestrator\.log$')


def extract_times_from_log(path):
    times = {i: 0 for i in range(1, 9)}
    mode = 'sequential'
    total_orchestration_seconds = None
    try:
        with open(path, 'r') as f:
            lines = f.readlines()
        # Detect execution mode and attempt to read total orchestration line
        for line in lines:
            if 'Starting parallel first stage' in line:
                mode = 'parallel'
            if 'Total orchestration time:' in line:
                m = COMP_LINE.search(line)
                if m:
                    try:
                        total_orchestration_seconds = round(float(m.group(1)))
                    except Exception:
                        total_orchestration_seconds = None
        # First, try DETAIL table
        detail_map = {}
        for line in lines:
            for name, step in STEP_ORDER:
                if name in line and 'SUCCESS' in line:
                    m = DETAIL_LINE.search(line)
                    if m:
                        val = m.group(1)
                        try:
                            sec = round(float(val))
                        except Exception:
                            sec = 0
                        detail_map[step] = sec
        if detail_map:
            times.update(detail_map)
            return times, mode, total_orchestration_seconds
        # Fallback to completed in lines in sequence
        current_step = 0
        for line in lines:
            if 'Step 1:' in line: current_step = 1
            elif 'Step 2:' in line: current_step = 2
            elif 'Step 3:' in line: current_step = 3
            elif 'Step 4:' in line: current_step = 4
            elif 'Step 5:' in line: current_step = 5
            elif 'Step 6:' in line: current_step = 6
            elif 'Step 7:' in line: current_step = 7
            elif 'Step 8:' in line: current_step = 8
            if 'completed in' in line and current_step:
                m = COMP_LINE.search(line)
                if m:
                    val = m.group(1)
                    try:
                        sec = round(float(val))
                    except Exception:
                        sec = 0
                    times[current_step] = sec
        return times, mode, total_orchestration_seconds
    except Exception:
        return times, mode, total_orchestration_seconds


def discover_orchestrators():
    logs = []
    for fname in os.listdir(OUTPUT_DIR):
        if fname.endswith('_orchestrator.log') and f'_{TODAY_TAG}_' in fname:
            logs.append(fname)
    return sorted(logs)


def main():
    logs = discover_orchestrators()
    rows = []
    for log in logs:
        m = ORCH_RE.match(log)
        if not m:
            continue
        base, date, time, model = m.groups()
        times, mode, total_orch = extract_times_from_log(os.path.join(OUTPUT_DIR, log))
        total = total_orch if total_orch is not None else sum(times[i] for i in range(1, 9))
        row = f"{base} & {model} & {mode} & {total} & " + ' & '.join(str(times[i]) for i in range(1, 9)) + " \\\\"
        rows.append(row)
    print("TABLE3_ROWS_START")
    for r in rows:
        print(r)
    print("TABLE3_ROWS_END")

if __name__ == '__main__':
    main()
