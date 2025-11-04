# ADK-Based Complete Rule Coverage Strategy for PlantUML LUCIM Auditor

## Overview

This document describes the **fully LLM-based strategy** (no Python rule extraction) for ensuring the PlantUML LUCIM Auditor checks ALL rules from the LUCIM DSL definition file. The strategy leverages Google ADK features and advanced LLM prompting techniques.

## Strategy Principles

1. **Fully LLM-Based**: All rule parsing, extraction, and validation is performed by the LLM itself, not by Python code
2. **Systematic Workflow**: The persona enforces a strict multi-phase workflow that the LLM must follow
3. **Self-Verification**: The LLM is instructed to verify its own completeness before outputting results
4. **ADK Reasoning Mode**: Leverages OpenAI's reasoning capabilities to ensure thorough analysis

## Implementation Components

### 1. Enhanced Persona Instructions (`PSN_LUCIM_PlantUML_Diagram_Auditor.md`)

#### Primary Objectives - 4-Step Mandatory Workflow

1. **STEP 1 - RULE INVENTORY**: 
   - LLM must parse the entire `<LUCIM-DSL-DESCRIPTION>` section
   - Extract ALL rule identifiers in format `<CATEGORY><NUMBER>-<IDENTIFIER>`
   - Create a complete ordered checklist
   - Count total rules: `EXPECTED_TOTAL_RULES`

2. **STEP 2 - SYSTEMATIC AUDIT**:
   - Evaluate diagram against EACH rule from the checklist
   - Work through rules one by one in methodical order
   - Mark each rule as evaluated or not_applicable

3. **STEP 3 - VERIFICATION**:
   - Calculate: `ACTUAL_TOTAL = len(evaluated) + len(not_applicable)`
   - Verify: `ACTUAL_TOTAL == EXPECTED_TOTAL_RULES`
   - If mismatch, continue reasoning to find missing rules

4. **STEP 4 - REPORTING**:
   - Only output when coverage is 100% complete
   - Include complete coverage section in response

#### Special Instructions - Complete Rule Coverage Protocol

The persona includes a detailed **MANDATORY WORKFLOW** section with:

- **INITIAL RULE EXTRACTION PHASE**: Instructions for systematically scanning and extracting all rule tags
- **SYSTEMATIC EVALUATION PHASE**: Step-by-step process for evaluating each rule
- **COVERAGE VERIFICATION PHASE**: Critical verification step before output
- **FINAL OUTPUT PHASE**: Requirements for complete coverage reporting

**Critical Constraints:**
- `MUST NOT output until ACTUAL_TOTAL == EXPECTED_TOTAL_RULES`
- `missing_evaluation MUST be empty [] only when coverage is complete`

### 2. Enhanced Prompt in Agent Code (`agent_lucim_plantuml_diagram_auditor.py`)

The agent code adds a **CRITICAL PRE-AUDIT INSTRUCTION** section that:

- Reinforces the rule extraction requirement
- Provides explicit step-by-step instructions
- Emphasizes the mandatory checklist approach
- Requires verification before output

This instruction is prepended to the input, ensuring the LLM sees it prominently.

### 3. ADK Reasoning Configuration

The auditor uses OpenAI's reasoning capabilities via the Responses API:

```python
api_config = get_reasoning_config("plantuml_auditor")
api_config["reasoning"]["effort"] = self.reasoning_effort  # "medium" or "high"
api_config["reasoning"]["summary"] = self.reasoning_summary  # "auto" or "manual"
```

**Why Reasoning Mode Helps:**
- **Extended reasoning chains**: Allows LLM to work through the full rule list systematically
- **Self-checking capability**: LLM can verify its own work before final output
- **Iterative refinement**: Can continue reasoning if it discovers missing rules

**Recommended Configuration:**
- `reasoning_effort`: `"medium"` or `"high"` for thorough analysis
- `reasoning_summary`: `"auto"` to see reasoning steps that verify completeness

### 4. Structured Output Schema Enforcement

The persona defines a strict JSON schema that includes:

```json
{
  "data": {
    "coverage": {
      "evaluated": [...],           // Must include all evaluated rules
      "not_applicable": [...],      // Must include all N/A rules
      "missing_evaluation": [],     // Must be empty when complete
      "total_rules_in_dsl": "15"    // Must match sum of above
    }
  }
}
```

The schema itself enforces that the LLM must provide complete coverage information.

## How It Works

### Execution Flow

1. **Prompt Construction**:
   ```
   [Task Instructions] + [Persona with 4-Step Workflow] + [LUCIM DSL Full Definition] + [Pre-Audit Instructions] + [PlantUML Diagram]
   ```

2. **LLM Processing** (via Reasoning Mode):
   - **Phase 1**: LLM extracts all rule IDs from DSL (visible in reasoning)
   - **Phase 2**: LLM systematically evaluates each rule against diagram
   - **Phase 3**: LLM verifies completeness: `evaluated + not_applicable == total`
   - **Phase 4**: LLM outputs JSON only if verification passes

3. **Verification**:
   - Output JSON includes `coverage` section
   - If `missing_evaluation` is non-empty, coverage is incomplete
   - If `len(evaluated) + len(not_applicable) != total_rules_in_dsl`, coverage is incomplete

### Self-Correction Mechanism

The persona instructions include explicit self-correction:

> **If ACTUAL_TOTAL < EXPECTED_TOTAL_RULES:**
> - Identify missing rules: MISSING = EXPECTED_TOTAL_RULES - ACTUAL_TOTAL
> - Review your RULE_INVENTORY_CHECKLIST
> - For each missing rule, evaluate it NOW and add it to the appropriate list
> - Repeat verification until ACTUAL_TOTAL = EXPECTED_TOTAL_RULES

This allows the LLM to catch and fix its own mistakes during reasoning.

## ADK Features Utilized

### 1. Reasoning Mode (OpenAI Responses API)

- **Purpose**: Allow LLM extended reasoning chains for systematic rule checking
- **Configuration**: Via `get_reasoning_config("plantuml_auditor")`
- **Benefit**: LLM can work through long checklists methodically

### 2. Structured Prompting

- **Purpose**: Enforce systematic workflow through clear phase separation
- **Implementation**: Multi-step instructions in persona and pre-audit prompt
- **Benefit**: Reduces likelihood of skipping rules

### 3. Schema Enforcement

- **Purpose**: Force complete coverage reporting in output format
- **Implementation**: JSON schema in persona with required coverage fields
- **Benefit**: Makes incomplete coverage immediately visible

### 4. Self-Verification Instructions

- **Purpose**: Enable LLM to verify its own completeness
- **Implementation**: Explicit verification steps in persona workflow
- **Benefit**: Catches missing rules before output

## Monitoring and Validation

### Checking Completeness

After audit execution, check:

1. **Coverage Completeness**:
   ```python
   coverage = audit_result["data"]["coverage"]
   total = int(coverage["total_rules_in_dsl"])
   evaluated = len(coverage["evaluated"])
   not_applicable = len(coverage["not_applicable"])
   missing = len(coverage.get("missing_evaluation", []))
   
   is_complete = (evaluated + not_applicable == total) and (missing == 0)
   ```

2. **Reasoning Verification**:
   - Check `output-reasoning.md` for evidence of rule extraction phase
   - Look for phrases like "RULE_INVENTORY_CHECKLIST" or "EXPECTED_TOTAL_RULES"
   - Verify reasoning shows systematic evaluation of each rule

### Handling Incomplete Coverage

If coverage is incomplete:

1. **Review Reasoning**: Check if LLM attempted rule extraction
2. **Increase Reasoning Effort**: Try `reasoning_effort="high"`
3. **Enhance Instructions**: Add more explicit examples in persona
4. **Manual Retry**: Re-run audit with same configuration

## Best Practices

### For Optimal Coverage

1. **Use Medium or High Reasoning Effort**:
   - Low effort may skip verification steps
   - Medium/high allows thorough systematic checking

2. **Enable Reasoning Summary**:
   - Set `reasoning_summary="auto"` to see LLM's thought process
   - Helps verify that rule extraction occurred

3. **Verify Output Schema**:
   - Always check that `coverage` section is complete
   - Ensure `missing_evaluation` is empty when audit is complete

4. **Monitor First Runs**:
   - Review initial audit outputs carefully
   - Adjust persona instructions if patterns of incompleteness emerge

## Limitations and Considerations

### Known Limitations

1. **LLM Variability**: Different models may interpret instructions differently
2. **Large Rule Sets**: Very large DSL files (>50 rules) may challenge systematic checking
3. **Reasoning Tokens**: Extended reasoning uses more tokens (cost consideration)

### Mitigation Strategies

1. **Clear, Explicit Instructions**: Persona uses numbered steps and explicit requirements
2. **Structured Format**: JSON schema enforces required fields
3. **Self-Verification**: Instructions require LLM to verify before output
4. **Reasoning Mode**: Allows LLM sufficient "thinking time" to be thorough

## Future Enhancements

### Potential Improvements

1. **ADK Retry Logic**: Automatically retry if `missing_evaluation` is non-empty
2. **Rule Counting Validation**: Add post-processing validation (optional, not required)
3. **Interactive Feedback**: Allow LLM to ask clarifying questions (if needed)
4. **Tiered Verification**: Multi-pass verification for critical audits

### ADK Features to Explore

- **ADK Structured Output**: Force JSON schema compliance at API level (if available)
- **ADK Multi-Agent**: Split rule extraction and evaluation across agents (if needed)
- **ADK Monitoring**: Track rule coverage metrics across runs

## Conclusion

This strategy provides a **fully LLM-based approach** to ensuring complete rule coverage without requiring Python-based rule extraction. By leveraging:

- **Systematic workflow instructions** in the persona
- **ADK reasoning capabilities** for thorough analysis
- **Self-verification mechanisms** built into the prompt
- **Structured output requirements** that enforce completeness

The auditor should achieve high completeness rates while remaining fully LLM-driven and adaptable to changes in the LUCIM DSL definition.

