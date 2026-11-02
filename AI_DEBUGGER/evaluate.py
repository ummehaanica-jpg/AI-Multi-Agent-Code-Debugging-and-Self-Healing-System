"""
evaluate.py — Experimental Evaluation Script
Runs all dataset files through the full agent pipeline and reports:
  - Detection accuracy
  - Repair accuracy
  - Validation success rate
  - Average execution time per stage

Usage:
    python evaluate.py
"""
import os
import time
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from agents.error_detector import detect_errors
from agents.fixer import fix_code
from agents.validator import validate_code

# ── Collect all dataset files ─────────────────────────────────────────────────
DATASET_ROOT = os.path.join(os.path.dirname(__file__), "dataset")

# Each entry: (file_path, expected_error_type)
# expected_error_type="" means the file should be clean (no error expected)
DATASET: list[tuple[str, str]] = []

CATEGORY_MAP = {
    "syntax":       "SyntaxError",
    "runtime":      "NameError",       # runtime samples are NameError / ZeroDivisionError
    "typeerror":    "TypeError",
    "indexerror":   "IndexError",
    "attributeerror": "AttributeError",
}

for folder, expected_type in CATEGORY_MAP.items():
    folder_path = os.path.join(DATASET_ROOT, folder)
    if not os.path.isdir(folder_path):
        continue
    for fname in sorted(os.listdir(folder_path)):
        if fname.endswith(".py"):
            DATASET.append((os.path.join(folder_path, fname), expected_type))

# ── Run pipeline on every file ────────────────────────────────────────────────
records = []

for file_path, expected_type in DATASET:
    with open(file_path, encoding="utf-8") as f:
        code = f.read()

    # --- Detection ---
    t0 = time.perf_counter()
    detection = detect_errors(code)
    detect_ms = (time.perf_counter() - t0) * 1000

    detected_correctly = (
        detection["has_error"] and
        (detection["error_type"] == expected_type or
         # runtime folder has mixed error types; accept any error as correct
         expected_type == "NameError")
    )

    # --- Fix ---
    t0 = time.perf_counter()
    if detection["has_error"]:
        fix_result = fix_code(code, detection["error_type"], detection["error_msg"])
    else:
        fix_result = {"fixed_code": code, "method": "unchanged", "applied_rule": "none"}
    fix_ms = (time.perf_counter() - t0) * 1000

    fixed_code = fix_result["fixed_code"]
    repair_changed = fixed_code != code  # True if agent actually modified something

    # --- Validation ---
    t0 = time.perf_counter()
    validation = validate_code(fixed_code, timeout=5)
    validate_ms = (time.perf_counter() - t0) * 1000

    records.append({
        "file":              os.path.basename(file_path),
        "category":          os.path.basename(os.path.dirname(file_path)),
        "expected_error":    expected_type,
        "detected_error":    detection["error_type"] if detection["has_error"] else "none",
        "detected_correctly": detected_correctly,
        "fix_method":        fix_result["method"],
        "repair_attempted":  repair_changed,
        "validation_passed": validation["success"],
        "detect_ms":         round(detect_ms, 2),
        "fix_ms":            round(fix_ms, 2),
        "validate_ms":       round(validate_ms, 2),
        "total_ms":          round(detect_ms + fix_ms + validate_ms, 2),
    })

# ── Build DataFrame ───────────────────────────────────────────────────────────
df = pd.DataFrame(records)

# ── Compute summary metrics ───────────────────────────────────────────────────
total          = len(df)
detection_acc  = df["detected_correctly"].sum() / total * 100
repair_acc     = df["repair_attempted"].sum() / total * 100
validation_sr  = df["validation_passed"].sum() / total * 100
avg_detect_ms  = df["detect_ms"].mean()
avg_fix_ms     = df["fix_ms"].mean()
avg_validate_ms= df["validate_ms"].mean()
avg_total_ms   = df["total_ms"].mean()

print("=" * 60)
print("  AI Multi-Agent Debugger — Experimental Evaluation")
print("=" * 60)
print(f"  Total test cases       : {total}")
print(f"  Detection Accuracy     : {detection_acc:.1f}%")
print(f"  Repair Attempt Rate    : {repair_acc:.1f}%")
print(f"  Validation Success Rate: {validation_sr:.1f}%")
print(f"  Avg Detection Time     : {avg_detect_ms:.2f} ms")
print(f"  Avg Fix Time           : {avg_fix_ms:.2f} ms")
print(f"  Avg Validation Time    : {avg_validate_ms:.2f} ms")
print(f"  Avg Total Pipeline Time: {avg_total_ms:.2f} ms")
print("=" * 60)

# ── Per-category breakdown ────────────────────────────────────────────────────
print("\nPer-Category Breakdown:")
category_summary = (
    df.groupby("category")
    .agg(
        total=("file", "count"),
        detected=("detected_correctly", "sum"),
        validated=("validation_passed", "sum"),
        avg_ms=("total_ms", "mean"),
    )
    .reset_index()
)
category_summary["detect_%"] = (category_summary["detected"] / category_summary["total"] * 100).round(1)
category_summary["validate_%"] = (category_summary["validated"] / category_summary["total"] * 100).round(1)
print(category_summary.to_string(index=False))

# ── Save detailed results CSV ─────────────────────────────────────────────────
csv_path = os.path.join(os.path.dirname(__file__), "evaluation_results.csv")
df.to_csv(csv_path, index=False)
print(f"\nDetailed results saved → {csv_path}")

# ── Bar chart: metrics overview ───────────────────────────────────────────────
metrics = {
    "Detection\nAccuracy": detection_acc,
    "Repair\nAttempt Rate": repair_acc,
    "Validation\nSuccess Rate": validation_sr,
}
fig, axes = plt.subplots(1, 2, figsize=(12, 4))

# Chart 1 — accuracy bars
bars = axes[0].bar(metrics.keys(), metrics.values(), color=["#2196F3", "#4CAF50", "#FF9800"])
axes[0].set_ylim(0, 110)
axes[0].set_ylabel("Percentage (%)")
axes[0].set_title("Agent Performance Metrics")
for bar, val in zip(bars, metrics.values()):
    axes[0].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                 f"{val:.1f}%", ha="center", fontsize=10, fontweight="bold")

# Chart 2 — avg time breakdown
time_labels = ["Detection", "Fix", "Validation"]
time_vals   = [avg_detect_ms, avg_fix_ms, avg_validate_ms]
axes[1].bar(time_labels, time_vals, color=["#9C27B0", "#F44336", "#009688"])
axes[1].set_ylabel("Average Time (ms)")
axes[1].set_title("Average Pipeline Stage Time")

plt.tight_layout()
chart_path = os.path.join(os.path.dirname(__file__), "evaluation_chart.png")
fig.savefig(chart_path, dpi=120)
plt.close(fig)
print(f"Evaluation chart saved  → {chart_path}")
