#!/usr/bin/env python3
"""
Compliance metrics utilities for auditor comparison.

Computes confusion-matrix style metrics (TP, FP, TN, FN) by comparing
the initial PlantUML LUCIM auditor (step 6) against the final auditor (step 8).

Convention: positive = compliant (can be flipped by parameter).
"""

from typing import Any, Dict, List, Tuple

from utils_auditor_schema import normalize_auditor_like_response


def _extract_rule_sets(audit: Dict[str, Any]) -> Tuple[set, set, set, int]:
    """Extract rule sets from a normalized auditor payload.

    Returns:
        non_compliant_rules: set of rule IDs flagged non-compliant
        evaluated_rules: set of rule IDs evaluated (if available)
        not_applicable_rules: set of rule IDs marked not applicable (if available)
        total_rules: integer total declared in coverage
    """
    data = (audit or {}).get("data", {})
    ncr_list: List[Dict[str, Any]] = data.get("non-compliant-rules", []) or []
    non_compliant_rules = {
        str(item.get("rule", "")).strip()
        for item in ncr_list
        if isinstance(item, dict) and str(item.get("rule", "")).strip()
    }

    coverage = data.get("coverage", {}) if isinstance(data.get("coverage"), dict) else {}
    evaluated = coverage.get("evaluated", []) or []
    not_applicable = coverage.get("not_applicable", []) or []
    total_rules_raw = coverage.get("total_rules_in_dsl", "0")
    try:
        total_rules = int(str(total_rules_raw))
    except Exception:
        total_rules = 0

    evaluated_rules = {str(r).strip() for r in evaluated if str(r).strip()}
    not_applicable_rules = {str(r).strip() for r in not_applicable if str(r).strip()}
    return non_compliant_rules, evaluated_rules, not_applicable_rules, total_rules


def compute_audit_confusion_metrics(
    initial_audit: Any,
    final_audit: Any,
    *,
    positive_label: str = "compliant",
) -> Dict[str, Any]:
    """Compute TP/FP/TN/FN comparing initial vs final auditor per-rule.

    Args:
        initial_audit: Any-like object convertible to auditor payload
        final_audit: Any-like object convertible to auditor payload (ground truth)
        positive_label: "compliant" or "non-compliant"; determines which class is treated as positive

    Returns:
        Dict with counts and derived metrics, plus metadata (universe sizes).
    """
    if positive_label not in ("compliant", "non-compliant"):
        positive_label = "compliant"

    init_norm = normalize_auditor_like_response(initial_audit)
    final_norm = normalize_auditor_like_response(final_audit)

    (init_ncr, init_eval, init_na, init_total) = _extract_rule_sets(init_norm)
    (final_ncr, final_eval, final_na, final_total) = _extract_rule_sets(final_norm)

    # Define universe of comparable rules: those evaluated or marked N/A by at least one
    universe = (init_eval | init_na | final_eval | final_na)

    # If universe is empty, fallback to union of non-compliant rule IDs
    if not universe:
        universe = (init_ncr | final_ncr)

    # If still empty, nothing to compare
    if not universe:
        return {
            "tp": 0,
            "fp": 0,
            "tn": 0,
            "fn": 0,
            "precision": 0.0,
            "recall": 0.0,
            "specificity": 0.0,
            "accuracy": 0.0,
            "f1": 0.0,
            "universe_size": 0,
            "initial_total_rules": init_total,
            "final_total_rules": final_total,
            "positive_label": positive_label,
        }

    # For each rule: predicted label from initial, true label from final
    # Label definition based on membership in non-compliant list
    def is_compliant(ncr_set: set, rule: str) -> bool:
        return rule not in ncr_set

    tp = fp = tn = fn = 0
    for rule in universe:
        pred_compliant = is_compliant(init_ncr, rule)
        true_compliant = is_compliant(final_ncr, rule)

        if positive_label == "compliant":
            if pred_compliant and true_compliant:
                tp += 1
            elif pred_compliant and not true_compliant:
                fp += 1
            elif (not pred_compliant) and (not true_compliant):
                tn += 1
            else:
                fn += 1
        else:  # positive = non-compliant
            pred_nc = not pred_compliant
            true_nc = not true_compliant
            if pred_nc and true_nc:
                tp += 1
            elif pred_nc and not true_nc:
                fp += 1
            elif (not pred_nc) and (not true_nc):
                tn += 1
            else:
                fn += 1

    total = max(len(universe), 1)
    precision = (tp / (tp + fp)) if (tp + fp) else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) else 0.0
    specificity = (tn / (tn + fp)) if (tn + fp) else 0.0
    accuracy = ((tp + tn) / (tp + tn + fp + fn)) if (tp + tn + fp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "accuracy": accuracy,
        "f1": f1,
        "universe_size": len(universe),
        "initial_total_rules": init_total,
        "final_total_rules": final_total,
        "positive_label": positive_label,
    }


