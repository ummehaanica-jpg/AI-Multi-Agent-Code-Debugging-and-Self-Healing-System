"""
evaluation/metrics.py

Metric definitions for evaluating the AI debugger pipeline.

Every metric is based on actual validation results.
NO metric uses 'fixed_code != original_code' as a proxy for success.

Metrics computed:
1.  Error Detection Accuracy   — were errors correctly detected?
2.  Precision                  — TP / (TP + FP)
3.  Recall                     — TP / (TP + FN)
4.  F1 Score                   — harmonic mean of Precision and Recall
5.  Repair Success Rate        — validated repairs / repair attempts
6.  First-Attempt Repair Rate  — repairs that passed on attempt 1
7.  Average Repair Attempts    — mean attempts across all cases
8.  Execution Success Rate     — code runs without runtime error
9.  Test Pass Rate             — generated tests that passed
10. End-to-End Success Rate    — detected AND repaired AND validated
11. Average Processing Time    — mean pipeline time in ms
"""
from __future__ import annotations

from typing import Any


def compute_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute all evaluation metrics from a list of pipeline result records.

    Each record should have:
        expected_error      : str   — expected exception type, '' for clean code
        detected_error      : str   — detected exception type, '' if none
        has_error           : bool  — whether an error was detected
        validation_passed   : bool  — whether validation succeeded
        execution_success   : bool  — whether code ran without error
        tests_passed        : bool  — whether generated tests passed
        attempts            : int   — number of repair attempts
        first_attempt_pass  : bool  — whether repair passed on attempt 1
        total_ms            : float — pipeline time in milliseconds
    """
    if not records:
        return _empty_metrics()

    total = len(records)

    # ── Classification correctness ───────────────────────────────────────────
    # TP: error expected AND detected correctly
    # FP: error detected BUT code was clean (false alarm)
    # FN: error expected BUT not detected
    # TN: code is clean AND no error detected

    tp = sum(
        1 for r in records
        if r["expected_error"] != "" and r["detected_error"] == r["expected_error"]
    )
    fp = sum(
        1 for r in records
        if r["expected_error"] == "" and r["detected_error"] != ""
    )
    fn = sum(
        1 for r in records
        if r["expected_error"] != "" and r["detected_error"] == ""
    )
    tn = sum(
        1 for r in records
        if r["expected_error"] == "" and r["detected_error"] == ""
    )

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    detection_accuracy = (tp + tn) / total if total > 0 else 0.0

    # ── Repair metrics ────────────────────────────────────────────────────
    # Only consider cases where an error was actually present
    error_cases = [r for r in records if r["expected_error"] != ""]
    n_error = len(error_cases)

    validated_repairs = sum(
        1 for r in error_cases if r["validation_passed"]
    )
    repair_success_rate = validated_repairs / n_error if n_error > 0 else 0.0

    first_attempt_passes = sum(
        1 for r in error_cases
        if r.get("first_attempt_pass") and r["validation_passed"]
    )
    first_attempt_rate = first_attempt_passes / n_error if n_error > 0 else 0.0

    avg_attempts = (
        sum(r.get("attempts", 1) for r in error_cases) / n_error
        if n_error > 0 else 0.0
    )

    # ── Execution metrics ────────────────────────────────────────────────
    exec_successes = sum(
        1 for r in records if r.get("execution_success", False)
    )
    execution_success_rate = exec_successes / total if total > 0 else 0.0

    test_runs = [r for r in records if r.get("tests_passed") is not None]
    test_pass_count = sum(1 for r in test_runs if r.get("tests_passed"))
    test_pass_rate = test_pass_count / len(test_runs) if test_runs else 0.0

    # End-to-end success: error detected correctly AND repair validated
    e2e_successes = sum(
        1 for r in records
        if r["expected_error"] == r["detected_error"]
        and (r["expected_error"] == "" or r["validation_passed"])
    )
    e2e_success_rate = e2e_successes / total if total > 0 else 0.0

    # ── Timing ────────────────────────────────────────────────────────────
    times = [r["total_ms"] for r in records if r.get("total_ms", 0) > 0]
    avg_time_ms = sum(times) / len(times) if times else 0.0

    return {
        "total": total,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "error_cases": n_error,
        "detection_accuracy": round(detection_accuracy * 100, 1),
        "precision": round(precision * 100, 1),
        "recall": round(recall * 100, 1),
        "f1_score": round(f1 * 100, 1),
        "repair_success_rate": round(repair_success_rate * 100, 1),
        "first_attempt_rate": round(first_attempt_rate * 100, 1),
        "avg_attempts": round(avg_attempts, 2),
        "execution_success_rate": round(execution_success_rate * 100, 1),
        "test_pass_rate": round(test_pass_rate * 100, 1),
        "e2e_success_rate": round(e2e_success_rate * 100, 1),
        "avg_time_ms": round(avg_time_ms, 1),
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "total": 0, "tp": 0, "fp": 0, "fn": 0, "tn": 0, "error_cases": 0,
        "detection_accuracy": 0.0, "precision": 0.0, "recall": 0.0,
        "f1_score": 0.0, "repair_success_rate": 0.0, "first_attempt_rate": 0.0,
        "avg_attempts": 0.0, "execution_success_rate": 0.0,
        "test_pass_rate": 0.0, "e2e_success_rate": 0.0, "avg_time_ms": 0.0,
    }
