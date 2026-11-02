"""
evaluate.py
End-to-End Evaluation for AI Multi-Agent Code Debugging System

Evaluates the actual DebuggingOrchestrator pipeline.

Metrics:
- Detection Accuracy
- Repair Success Rate
- First-Attempt Repair Rate
- Clean-Code Preservation
- Average Repair Attempts
- Average Pipeline Time
- Per-category performance

Results:
- evaluation_results.csv
- evaluation_chart.png
"""

from __future__ import annotations

import contextlib
import io
import os
import time

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from core.orchestrator import run_pipeline


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATASET_ROOT = os.path.join(PROJECT_ROOT, "dataset")

MAX_RETRIES = 3
TIMEOUT = 5


# ============================================================
# EXPECTED ERROR TYPES
# ============================================================

EXPECTED_TYPES = {
    "syntax": "SyntaxError",
    "typeerror": "TypeError",
    "indexerror": "IndexError",
    "attributeerror": "AttributeError",
    "keyerror": "KeyError",
    "valueerror": "ValueError",
    "zerodivision": "ZeroDivisionError",
    "runtime": "runtime",
    "clean": "clean",
    "logical": "logical",
}


# ============================================================
# FIND DATASET FILES
# ============================================================

dataset_files = []

if not os.path.isdir(DATASET_ROOT):
    print("ERROR: dataset folder was not found.")
    print(f"Expected location: {DATASET_ROOT}")
    raise SystemExit(1)


for root, _, files in os.walk(DATASET_ROOT):

    for filename in sorted(files):

        if not filename.endswith(".py"):
            continue

        if filename.startswith("__"):
            continue

        file_path = os.path.join(root, filename)

        relative_path = os.path.relpath(
            file_path,
            DATASET_ROOT,
        )

        category = os.path.basename(
            os.path.dirname(file_path)
        ).lower()

        dataset_files.append(
            (
                file_path,
                relative_path,
                category,
            )
        )


dataset_files.sort(
    key=lambda item: item[1].lower()
)


if not dataset_files:
    print("ERROR: No Python files were found inside dataset.")
    raise SystemExit(1)


print("=" * 70)
print(" AI MULTI-AGENT DEBUGGER — END-TO-END EVALUATION")
print("=" * 70)

print(f"Dataset location : {DATASET_ROOT}")
print(f"Test cases       : {len(dataset_files)}")
print(f"Max retries      : {MAX_RETRIES}")
print(f"Timeout          : {TIMEOUT} seconds")
print("=" * 70)


# ============================================================
# RUN EVALUATION
# ============================================================

records = []


for index, (file_path, relative_path, category) in enumerate(
    dataset_files,
    start=1,
):

    print(
        f"\n[{index}/{len(dataset_files)}] "
        f"Testing: {relative_path}"
    )

    # --------------------------------------------------------
    # Read source code
    # --------------------------------------------------------

    try:

        with open(
            file_path,
            "r",
            encoding="utf-8-sig",
        ) as file:

            code = file.read()

    except Exception as exc:

        print(f"  Could not read file: {exc}")

        records.append(
            {
                "file": os.path.basename(file_path),
                "category": category,
                "expected_error": EXPECTED_TYPES.get(
                    category,
                    category,
                ),
                "detected_error": "read_error",
                "detection_correct": False,
                "detection_evaluable": False,
                "repair_succeeded": False,
                "first_attempt_success": False,
                "clean_preserved": False,
                "repair_attempts": 0,
                "pipeline_time_ms": 0,
                "status": "READ_ERROR",
            }
        )

        continue

    # --------------------------------------------------------
    # Run actual multi-agent orchestrator
    # --------------------------------------------------------

    start_time = time.perf_counter()

    captured_output = io.StringIO()

    try:

        # Hide Fixer debug prints during evaluation.
        with contextlib.redirect_stdout(captured_output):

            state = run_pipeline(
                code=code,
                max_retries=MAX_RETRIES,
                timeout=TIMEOUT,
                use_llm=False,
            )

        pipeline_error = ""

    except Exception as exc:

        state = None
        pipeline_error = str(exc)

    elapsed_ms = (
        time.perf_counter() - start_time
    ) * 1000

    # --------------------------------------------------------
    # Handle pipeline failure
    # --------------------------------------------------------

    if state is None:

        print(
            f"  Pipeline error: {pipeline_error}"
        )

        records.append(
            {
                "file": os.path.basename(file_path),
                "category": category,
                "expected_error": EXPECTED_TYPES.get(
                    category,
                    category,
                ),
                "detected_error": "pipeline_error",
                "detection_correct": False,
                "detection_evaluable": True,
                "repair_succeeded": False,
                "first_attempt_success": False,
                "clean_preserved": False,
                "repair_attempts": 0,
                "pipeline_time_ms": round(
                    elapsed_ms,
                    2,
                ),
                "status": "PIPELINE_ERROR",
            }
        )

        continue

    # --------------------------------------------------------
    # Detection information
    # --------------------------------------------------------

    detection = state.detection or {}

    has_error = bool(
        detection.get(
            "has_error",
            False,
        )
    )

    detected_error = (
        detection.get(
            "error_type",
            "",
        )
        if has_error
        else "none"
    )

    expected_error = EXPECTED_TYPES.get(
        category,
        category,
    )

    # --------------------------------------------------------
    # Detection accuracy
    # --------------------------------------------------------

    detection_evaluable = True
    detection_correct = False

    if category == "logical":

        # The current orchestrator stops when there is
        # no runtime/syntax error, so logical bugs are
        # not automatically classified yet.
        detection_evaluable = False
        detection_correct = None

    elif category == "clean":

        detection_correct = not has_error

    elif category == "runtime":

        # Runtime folder intentionally contains different
        # runtime error types.
        detection_correct = has_error

    else:

        detection_correct = (
            has_error
            and detected_error == expected_error
        )

    # --------------------------------------------------------
    # Repair information
    # --------------------------------------------------------

    repair_succeeded = bool(
        state.repair_succeeded
    )

    repair_attempts = len(
        state.repair_attempts
    )

    first_attempt_success = False

    if repair_attempts > 0:

        first_attempt_success = bool(
            state.repair_attempts[0].passed
        )

    # --------------------------------------------------------
    # Clean-code preservation
    # --------------------------------------------------------

    clean_preserved = False

    if category == "clean":

        clean_preserved = (
            not has_error
            and state.current_code == code
        )

    # --------------------------------------------------------
    # Overall status
    # --------------------------------------------------------

    if category == "logical":

        status = "NOT_AUTO_EVALUATED"

    elif category == "clean":

        if clean_preserved:
            status = "PASS"
        else:
            status = "FAIL"

    elif repair_succeeded:

        status = "REPAIRED"

    elif has_error:

        status = "FAILED_REPAIR"

    else:

        status = "DETECTION_FAILED"

    # --------------------------------------------------------
    # Print case result
    # --------------------------------------------------------

    print(
        f"  Category       : {category}"
    )

    print(
        f"  Expected       : {expected_error}"
    )

    print(
        f"  Detected       : {detected_error}"
    )

    print(
        f"  Detection      : "
        f"{'PASS' if detection_correct is True else 'FAIL' if detection_correct is False else 'N/A'}"
    )

    print(
        f"  Repair         : "
        f"{'PASS' if repair_succeeded else 'FAIL'}"
    )

    print(
        f"  Attempts       : {repair_attempts}"
    )

    print(
        f"  Time           : {elapsed_ms:.2f} ms"
    )

    print(
        f"  Status         : {status}"
    )

    records.append(
        {
            "file": os.path.basename(file_path),
            "path": relative_path,
            "category": category,
            "expected_error": expected_error,
            "detected_error": detected_error,
            "detection_correct": detection_correct,
            "detection_evaluable": detection_evaluable,
            "repair_succeeded": repair_succeeded,
            "first_attempt_success": first_attempt_success,
            "clean_preserved": clean_preserved,
            "repair_attempts": repair_attempts,
            "pipeline_time_ms": round(
                elapsed_ms,
                2,
            ),
            "status": status,
        }
    )


# ============================================================
# DATAFRAME
# ============================================================

df = pd.DataFrame(records)


# ============================================================
# METRICS
# ============================================================

total_cases = len(df)


# ------------------------------------------------------------
# Detection accuracy
# ------------------------------------------------------------

detection_df = df[
    df["detection_evaluable"] == True
]

if len(detection_df) > 0:

    detection_accuracy = (
        detection_df["detection_correct"]
        .astype(bool)
        .mean()
        * 100
    )

else:

    detection_accuracy = 0.0


# ------------------------------------------------------------
# Error cases
# ------------------------------------------------------------

error_categories = [
    category
    for category in EXPECTED_TYPES
    if category not in [
        "clean",
        "logical",
    ]
]

error_df = df[
    df["category"].isin(error_categories)
]


# ------------------------------------------------------------
# Repair success
# ------------------------------------------------------------

if len(error_df) > 0:

    repair_success_rate = (
        error_df["repair_succeeded"]
        .mean()
        * 100
    )

else:

    repair_success_rate = 0.0


# ------------------------------------------------------------
# First-attempt success
# ------------------------------------------------------------

if len(error_df) > 0:

    first_attempt_rate = (
        error_df["first_attempt_success"]
        .mean()
        * 100
    )

else:

    first_attempt_rate = 0.0


# ------------------------------------------------------------
# Clean preservation
# ------------------------------------------------------------

clean_df = df[
    df["category"] == "clean"
]

if len(clean_df) > 0:

    clean_preservation_rate = (
        clean_df["clean_preserved"]
        .mean()
        * 100
    )

else:

    clean_preservation_rate = None


# ------------------------------------------------------------
# Average repair attempts
# ------------------------------------------------------------

if len(error_df) > 0:

    avg_repair_attempts = (
        error_df["repair_attempts"]
        .mean()
    )

else:

    avg_repair_attempts = 0.0


# ------------------------------------------------------------
# Average pipeline time
# ------------------------------------------------------------

avg_pipeline_time = (
    df["pipeline_time_ms"].mean()
)


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n")
print("=" * 70)
print(" FINAL EVALUATION RESULTS")
print("=" * 70)

print(
    f"Total test cases              : {total_cases}"
)

print(
    f"Detection accuracy            : "
    f"{detection_accuracy:.1f}%"
)

print(
    f"Repair success rate           : "
    f"{repair_success_rate:.1f}%"
)

print(
    f"First-attempt repair rate     : "
    f"{first_attempt_rate:.1f}%"
)

if clean_preservation_rate is not None:

    print(
        f"Clean-code preservation       : "
        f"{clean_preservation_rate:.1f}%"
    )

else:

    print(
        "Clean-code preservation       : "
        "No clean cases"
    )

print(
    f"Average repair attempts       : "
    f"{avg_repair_attempts:.2f}"
)

print(
    f"Average pipeline time         : "
    f"{avg_pipeline_time:.2f} ms"
)

print("=" * 70)


# ============================================================
# PER-CATEGORY SUMMARY
# ============================================================

print("\nPER-CATEGORY PERFORMANCE")
print("=" * 70)


category_rows = []


for category, group in df.groupby(
    "category",
    sort=True,
):

    evaluable = group[
        group["detection_evaluable"] == True
    ]

    if len(evaluable) > 0:

        category_detection = (
            evaluable["detection_correct"]
            .astype(bool)
            .mean()
            * 100
        )

    else:

        category_detection = None

    category_repair = (
        group["repair_succeeded"].mean()
        * 100
    )

    category_rows.append(
        {
            "category": category,
            "cases": len(group),
            "detection_%": (
                round(
                    category_detection,
                    1,
                )
                if category_detection is not None
                else "N/A"
            ),
            "repair_%": round(
                category_repair,
                1,
            ),
            "avg_attempts": round(
                group["repair_attempts"].mean(),
                2,
            ),
            "avg_time_ms": round(
                group["pipeline_time_ms"].mean(),
                2,
            ),
        }
    )


category_summary = pd.DataFrame(
    category_rows
)

print(
    category_summary.to_string(
        index=False
    )
)


# ============================================================
# SAVE CSV
# ============================================================

csv_path = os.path.join(
    PROJECT_ROOT,
    "evaluation_results.csv",
)

df.to_csv(
    csv_path,
    index=False,
)

print(
    f"\nDetailed results saved to:"
)

print(csv_path)


# ============================================================
# CREATE CHART
# ============================================================

chart_labels = [
    "Detection Accuracy",
    "Repair Success",
    "First Attempt",
]

chart_values = [
    detection_accuracy,
    repair_success_rate,
    first_attempt_rate,
]


if clean_preservation_rate is not None:

    chart_labels.append(
        "Clean Preservation"
    )

    chart_values.append(
        clean_preservation_rate
    )


fig = plt.figure(
    figsize=(10, 6)
)

bars = plt.bar(
    chart_labels,
    chart_values,
)

plt.ylim(
    0,
    110,
)

plt.ylabel(
    "Percentage (%)"
)

plt.title(
    "AI Multi-Agent Debugger — Evaluation Metrics"
)


for bar, value in zip(
    bars,
    chart_values,
):

    plt.text(
        bar.get_x()
        + bar.get_width() / 2,
        value + 2,
        f"{value:.1f}%",
        ha="center",
        fontweight="bold",
    )


plt.tight_layout()


chart_path = os.path.join(
    PROJECT_ROOT,
    "evaluation_chart.png",
)

fig.savefig(
    chart_path,
    dpi=150,
)

plt.close(fig)


print(
    f"Evaluation chart saved to:"
)

print(chart_path)

print("\n")
print("=" * 70)
print(" EVALUATION COMPLETE")
print("=" * 70)