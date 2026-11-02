"""
Agent 9 — Code Quality & Architecture Agent

Generates a comprehensive code quality report including:
- Structural metrics (functions, classes, imports, lines)
- Cyclomatic complexity per function
- Code smells and quality warnings
- Maintainability observations
- Refactoring suggestions
- Matplotlib complexity chart

Preserves backward compatibility with existing generate_report() interface.
Adds new generate_quality_report() function used by the orchestrator.
"""
from __future__ import annotations

import ast
import io
import re
from typing import Any

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — required for Streamlit
import matplotlib.pyplot as plt


# ================================================================
# PUBLIC API — NEW (used by orchestrator)
# ================================================================


def generate_quality_report(
    code: str,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate a comprehensive code quality report.

    Parameters
    ----------
    code:
        Python source code to analyze.
    analysis:
        Optional pre-computed analysis from analyzer.py.

    Returns
    -------
    dict with:
        report_text     : str  — markdown-formatted report
        chart_bytes     : bytes | None  — PNG complexity chart
        metrics         : dict — raw quality metrics
        code_smells     : list — detected code smell descriptions
        suggestions     : list — refactoring suggestions
        maintainability : str  — LOW / MEDIUM / HIGH
    """
    # Re-analyze if analysis not provided or parse failed
    if analysis is None or not analysis.get("parse_ok"):
        try:
            tree = ast.parse(code)
            parse_ok = True
        except SyntaxError:
            parse_ok = False
            tree = None
    else:
        try:
            tree = ast.parse(code)
            parse_ok = True
        except SyntaxError:
            tree = None
            parse_ok = False

    # Extract basic metrics
    lines = code.splitlines()
    total_lines = len(lines)
    non_blank = sum(1 for l in lines if l.strip())
    comment_lines = sum(1 for l in lines if l.strip().startswith("#"))

    # Function/class/import info from analysis or fresh parse
    if analysis and analysis.get("parse_ok"):
        functions = analysis.get("functions", [])
        classes = analysis.get("classes", [])
        imports = analysis.get("imports", [])
        variables = analysis.get("variables", [])
        function_details = analysis.get("function_details", [])
        complexity_data = analysis.get("function_complexity", {})
    else:
        functions, classes, imports, variables = [], [], [], []
        function_details = []
        complexity_data = {}
        if tree:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imports.append(f"{node.module}.{alias.name}")

    # Cyclomatic complexity per function
    complexity_scores = _count_complexity(code) if parse_ok else {}

    # Code smells
    code_smells = _detect_code_smells(
        code, lines, function_details, complexity_scores, analysis
    )

    # Refactoring suggestions
    suggestions = _generate_suggestions(code_smells, complexity_scores, functions)

    # Maintainability score
    maintainability = _estimate_maintainability(
        total_lines, len(functions), len(classes),
        complexity_scores, code_smells
    )

    # Build report text
    report_text = _build_report_text(
        total_lines, non_blank, comment_lines,
        functions, classes, imports, variables,
        complexity_scores, code_smells, suggestions, maintainability,
        parse_ok
    )

    # Chart
    chart_bytes = _build_chart(complexity_scores)

    metrics = {
        "total_lines": total_lines,
        "non_blank_lines": non_blank,
        "comment_lines": comment_lines,
        "function_count": len(functions),
        "class_count": len(classes),
        "import_count": len(imports),
        "variable_count": len(variables),
        "complexity_scores": complexity_scores,
        "maintainability": maintainability,
    }

    return {
        "report_text": report_text,
        "chart_bytes": chart_bytes,
        "metrics": metrics,
        "code_smells": code_smells,
        "suggestions": suggestions,
        "maintainability": maintainability,
    }


# ================================================================
# PUBLIC API — OLD (backward compatibility with app.py)
# ================================================================


def generate_report(analysis: dict, code: str) -> dict:
    """
    Backward-compatible interface.
    Calls generate_quality_report() internally.
    """
    result = generate_quality_report(code=code, analysis=analysis)
    return {
        "report_text": result["report_text"],
        "chart_bytes": result["chart_bytes"],
    }


# ================================================================
# COMPLEXITY
# ================================================================


def _count_complexity(code: str) -> dict[str, int]:
    """Count branches per function as a cyclomatic complexity proxy."""
    complexity: dict[str, int] = {}
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return complexity
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            count = sum(
                1 for child in ast.walk(node)
                if isinstance(
                    child,
                    (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.IfExp)
                )
            )
            complexity[node.name] = count + 1
    return complexity


# ================================================================
# CODE SMELL DETECTION
# ================================================================


def _detect_code_smells(
    code: str,
    lines: list[str],
    function_details: list[dict],
    complexity_scores: dict[str, int],
    analysis: dict[str, Any] | None,
) -> list[str]:
    """Detect common code smells and quality issues."""
    smells: list[str] = []

    # 1. Long functions (> 30 lines)
    if function_details:
        for func in function_details:
            start = func.get("line", 0)
            end = func.get("end_line", 0)
            if start and end:
                func_len = end - start
                if func_len > 30:
                    smells.append(
                        f"Long function '{func['name']}': {func_len} lines. "
                        "Consider breaking it into smaller functions."
                    )

    # 2. High complexity
    for fname, score in complexity_scores.items():
        if score > 10:
            smells.append(
                f"High cyclomatic complexity in '{fname}': {score}. "
                "Consider simplifying branching logic."
            )
        elif score > 6:
            smells.append(
                f"Moderate complexity in '{fname}': {score}."
            )

    # 3. Magic numbers (literal numbers other than 0, 1, 2)
    magic_pattern = re.compile(r"(?<!['\".\w])\b([3-9]\d+|\d{3,})\b")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        matches = magic_pattern.findall(stripped)
        if matches:
            smells.append(
                f"Magic number(s) {set(matches)} on line {i}. "
                "Consider using named constants."
            )
            break  # report only first occurrence to avoid noise

    # 4. Very long lines
    long_lines = [
        i + 1 for i, l in enumerate(lines)
        if len(l) > 100 and not l.strip().startswith("#")
    ]
    if long_lines:
        smells.append(
            f"Long lines detected at lines {long_lines[:5]}. "
            "PEP 8 recommends max 79 characters."
        )

    # 5. Missing docstrings in functions
    if analysis and analysis.get("parse_ok"):
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not (node.body and isinstance(node.body[0], ast.Expr) and
                            isinstance(node.body[0].value, ast.Constant)):
                        if not node.name.startswith("_"):
                            smells.append(
                                f"Function '{node.name}' has no docstring."
                            )
        except SyntaxError:
            pass

    # 6. Bare except
    for i, line in enumerate(lines, 1):
        if line.strip() == "except:":
            smells.append(
                f"Bare 'except:' clause on line {i}. "
                "Use specific exception types (e.g., except ValueError:)."
            )

    # 7. print() used for debugging (in functions)
    print_in_func = False
    if analysis and analysis.get("parse_ok"):
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for child in ast.walk(node):
                        if (
                            isinstance(child, ast.Call)
                            and isinstance(child.func, ast.Name)
                            and child.func.id == "print"
                        ):
                            print_in_func = True
                            break
        except SyntaxError:
            pass
    if print_in_func:
        smells.append(
            "print() used inside function bodies. "
            "Consider using logging for production code."
        )

    # 8. Mutable default arguments
    if analysis and analysis.get("parse_ok"):
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for default in node.args.defaults:
                        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                            smells.append(
                                f"Mutable default argument in '{node.name}'. "
                                "Use None as default and initialize inside function."
                            )
                            break
        except SyntaxError:
            pass

    return smells


# ================================================================
# SUGGESTIONS
# ================================================================


def _generate_suggestions(
    code_smells: list[str],
    complexity_scores: dict[str, int],
    functions: list[str],
) -> list[str]:
    """Generate refactoring suggestions based on detected smells."""
    suggestions: list[str] = []

    # High complexity suggestions
    for fname, score in complexity_scores.items():
        if score > 10:
            suggestions.append(
                f"Refactor '{fname}': extract smaller helper functions to reduce complexity."
            )

    # No functions — suggest modularization
    if not functions:
        suggestions.append(
            "Consider organizing code into functions for better reusability and testability."
        )

    # Based on smells
    if any("docstring" in smell for smell in code_smells):
        suggestions.append(
            "Add docstrings to public functions to improve code documentation."
        )
    if any("Magic number" in smell for smell in code_smells):
        suggestions.append(
            "Replace magic numbers with named constants at the top of the module."
        )
    if any("Bare 'except'" in smell for smell in code_smells):
        suggestions.append(
            "Replace bare 'except:' with specific exception types."
        )

    return suggestions


# ================================================================
# MAINTAINABILITY
# ================================================================


def _estimate_maintainability(
    total_lines: int,
    func_count: int,
    class_count: int,
    complexity_scores: dict[str, int],
    code_smells: list[str],
) -> str:
    """Estimate overall maintainability: HIGH / MEDIUM / LOW."""
    score = 100

    # Penalize for high complexity
    for c in complexity_scores.values():
        if c > 10:
            score -= 20
        elif c > 6:
            score -= 10

    # Penalize for many smells
    score -= len(code_smells) * 5

    # Penalize for very long files
    if total_lines > 300:
        score -= 15
    elif total_lines > 150:
        score -= 5

    if score >= 75:
        return "HIGH"
    elif score >= 45:
        return "MEDIUM"
    else:
        return "LOW"


# ================================================================
# REPORT TEXT
# ================================================================


def _build_report_text(
    total_lines: int,
    non_blank: int,
    comment_lines: int,
    functions: list,
    classes: list,
    imports: list,
    variables: list,
    complexity_scores: dict[str, int],
    code_smells: list[str],
    suggestions: list[str],
    maintainability: str,
    parse_ok: bool,
) -> str:
    parts = []
    parts.append("## 📊 Code Quality & Architecture Report")

    if not parse_ok:
        parts.append(
            "> ⚠️ Code could not be parsed (syntax error). "
            "Report is based on raw text analysis."
        )

    parts.append("\n### 📏 Code Metrics")
    parts.append(f"| Metric | Value |")
    parts.append(f"|--------|-------|")
    parts.append(f"| Total lines | {total_lines} |")
    parts.append(f"| Non-blank lines | {non_blank} |")
    parts.append(f"| Comment lines | {comment_lines} |")
    parts.append(f"| Functions | {len(functions)} |")
    parts.append(f"| Classes | {len(classes)} |")
    parts.append(f"| Imports | {len(imports)} |")
    parts.append(f"| Variables | {len(variables)} |")

    maint_emoji = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(maintainability, "🟡")
    parts.append(f"| Maintainability | {maint_emoji} {maintainability} |")

    if functions:
        parts.append(f"\n**Functions:** {', '.join(f'`{f}`' for f in functions)}")
    if classes:
        parts.append(f"**Classes:** {', '.join(f'`{c}`' for c in classes)}")
    if imports:
        parts.append(f"**Imports:** {', '.join(f'`{i}`' for i in imports[:10])}{'...' if len(imports) > 10 else ''}")

    if complexity_scores:
        parts.append("\n### 🧠 Cyclomatic Complexity (per function)")
        for fn, score in complexity_scores.items():
            if score <= 3:
                rating = "🟢 Low"
            elif score <= 7:
                rating = "🟡 Medium"
            else:
                rating = "🔴 High"
            parts.append(f"- `{fn}`: {score} {rating}")

    if code_smells:
        parts.append("\n### 🐞 Code Smells Detected")
        for smell in code_smells:
            parts.append(f"- ⚠️ {smell}")
    else:
        parts.append("\n### ✅ Code Smells")
        parts.append("No significant code smells detected.")

    if suggestions:
        parts.append("\n### 💡 Refactoring Suggestions")
        for s in suggestions:
            parts.append(f"- {s}")

    return "\n".join(parts)


# ================================================================
# CHART
# ================================================================


def _build_chart(complexity_scores: dict[str, int]) -> bytes | None:
    """Build a PNG bar chart of cyclomatic complexity."""
    if not complexity_scores:
        return None
    try:
        fig, ax = plt.subplots(figsize=(max(6, len(complexity_scores) * 1.2), 3))
        colors = [
            "#4CAF50" if v <= 3 else ("#FF9800" if v <= 7 else "#F44336")
            for v in complexity_scores.values()
        ]
        ax.bar(complexity_scores.keys(), complexity_scores.values(), color=colors)
        ax.set_xlabel("Function")
        ax.set_ylabel("Complexity Score")
        ax.set_title("Cyclomatic Complexity per Function")
        ax.set_ylim(0, max(complexity_scores.values()) + 2)
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100)
        plt.close(fig)
        return buf.getvalue()
    except Exception:
        return None
