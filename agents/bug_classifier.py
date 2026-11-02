"""
Agents 3 — Bug Classifier Agent

Classifies detected Python errors into categories and estimates severity.

Design:
- Hybrid approach: exception type + error message + AST context + rules
- Does NOT claim to be a trained ML classifier
- Designed so an ML model can be plugged in later via classify_with_model()
- Returns structured classification result
"""
from __future__ import annotations

import re
from typing import Any


# ================================================================
# SEVERITY LEVELS
# ================================================================

SEVERITY_CRITICAL = "CRITICAL"  # Prevents parsing/import entirely
SEVERITY_HIGH = "HIGH"          # Causes program crash at runtime
SEVERITY_MEDIUM = "MEDIUM"      # Causes incorrect behaviour
SEVERITY_LOW = "LOW"            # Potential issue, code may still run


# ================================================================
# BUG CATEGORIES
# ================================================================

CATEGORY_MAP: dict[str, str] = {
    "SyntaxError": "syntax",
    "IndentationError": "indentation",
    "TabError": "indentation",
    "NameError": "name",
    "UnboundLocalError": "name",
    "TypeError": "type",
    "IndexError": "index",
    "KeyError": "key",
    "AttributeError": "attribute",
    "ImportError": "import",
    "ModuleNotFoundError": "import",
    "ZeroDivisionError": "zero_division",
    "ValueError": "runtime",
    "RuntimeError": "runtime",
    "RecursionError": "runtime",
    "OverflowError": "runtime",
    "MemoryError": "runtime",
    "TimeoutError": "infinite_loop",
    "OSError": "runtime",
    "FileNotFoundError": "runtime",
    "PermissionError": "runtime",
}


SEVERITY_MAP: dict[str, str] = {
    "SyntaxError": SEVERITY_CRITICAL,
    "IndentationError": SEVERITY_CRITICAL,
    "TabError": SEVERITY_CRITICAL,
    "NameError": SEVERITY_HIGH,
    "UnboundLocalError": SEVERITY_HIGH,
    "TypeError": SEVERITY_HIGH,
    "IndexError": SEVERITY_HIGH,
    "KeyError": SEVERITY_HIGH,
    "AttributeError": SEVERITY_HIGH,
    "ImportError": SEVERITY_HIGH,
    "ModuleNotFoundError": SEVERITY_HIGH,
    "ZeroDivisionError": SEVERITY_HIGH,
    "ValueError": SEVERITY_MEDIUM,
    "RuntimeError": SEVERITY_MEDIUM,
    "RecursionError": SEVERITY_MEDIUM,
    "OverflowError": SEVERITY_MEDIUM,
    "MemoryError": SEVERITY_HIGH,
    "TimeoutError": SEVERITY_HIGH,
    "OSError": SEVERITY_MEDIUM,
    "FileNotFoundError": SEVERITY_MEDIUM,
    "PermissionError": SEVERITY_MEDIUM,
}


# ================================================================
# PUBLIC API
# ================================================================


def classify_bug(
    error_type: str,
    error_msg: str = "",
    analysis: dict[str, Any] | None = None,
    code: str = "",
) -> dict[str, Any]:
    """
    Classify a detected Python bug.

    Parameters
    ----------
    error_type:
        Exception class name (e.g. "SyntaxError").
    error_msg:
        Error message string.
    analysis:
        Optional AST analysis from analyzer.py.
    code:
        Original source code for additional context.

    Returns
    -------
    dict with keys:
        category      : str   — bug category slug
        severity      : str   — LOW / MEDIUM / HIGH / CRITICAL
        is_fixable    : bool  — heuristic: can rule-based fixer attempt repair?
        requires_llm  : bool  — heuristic: is LLM assistance likely needed?
        is_logical    : bool  — True if no exception but potential logic bug
        confidence    : float — 0.0–1.0 classifier confidence
        reason        : str   — human-readable classification reason
        hints         : list  — actionable repair hints
    """

    if not error_type:
        return _no_error_classification()

    # ————————————————————————————————————————————————————————————
    # Step 1: map error_type to category and severity
    # ————————————————————————————————————————————————————————————
    category = CATEGORY_MAP.get(error_type, "unknown")
    severity = SEVERITY_MAP.get(error_type, SEVERITY_MEDIUM)
    confidence = 0.90 if error_type in CATEGORY_MAP else 0.50

    # ————————————————————————————————————————————————————————————
    # Step 2: refine with message context
    # ————————————————————————————————————————————————————————————
    msg_lower = error_msg.lower()

    # Detect infinite loop via timeout
    if "timeout" in msg_lower or "timed out" in msg_lower:
        category = "infinite_loop"
        severity = SEVERITY_HIGH
        confidence = 0.85

    # TypeError sub-classification
    if error_type == "TypeError":
        if "unsupported operand" in msg_lower or "can only concatenate" in msg_lower:
            confidence = 0.92
        elif "argument" in msg_lower and ("positional" in msg_lower or "required" in msg_lower):
            confidence = 0.92
        elif "not subscriptable" in msg_lower:
            confidence = 0.90
        elif "not callable" in msg_lower:
            confidence = 0.90

    # ————————————————————————————————————————————————————————————
    # Step 3: determine fixability
    # ————————————————————————————————————————————————————————————
    rule_fixable = {
        "syntax", "indentation", "name", "type", "index",
        "key", "attribute", "zero_division",
    }
    is_fixable = category in rule_fixable

    requires_llm = category in {"runtime", "unknown", "logical"}
    if error_type == "ValueError":
        requires_llm = True

    # ————————————————————————————————————————————————————————————
    # Step 4: build hints
    # ————————————————————————————————————————————————————————————
    hints = _get_hints(category, error_type, error_msg, analysis)

    # ————————————————————————————————————————————————————————————
    # Step 5: build reason string
    # ————————————————————————————————————————————————————————————
    reason = (
        f"Classified as '{category}' based on exception type '{error_type}'. "
        f"Severity: {severity}. "
        f"Rule-based fix available: {'Yes' if is_fixable else 'No'}."
    )

    return {
        "category": category,
        "severity": severity,
        "is_fixable": is_fixable,
        "requires_llm": requires_llm,
        "is_logical": False,
        "confidence": round(confidence, 2),
        "reason": reason,
        "hints": hints,
        "error_type": error_type,
    }


def classify_logical_issue(
    code: str,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Heuristic detection of potential logical errors in code that
    executes without raising an exception.

    WARNING: This is heuristic-based, not definitive.
    False positives are possible. The result should be treated
    as a suggestion for manual review, not automatic modification.
    """
    issues: list[str] = []

    if analysis and analysis.get("parse_ok"):
        import ast
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"is_logical": False, "issues": [], "recommendation": ""}

        # Check for functions that never return a value but are assigned
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                returns = [
                    child for child in ast.walk(node)
                    if isinstance(child, ast.Return) and child.value is not None
                ]
                if not returns:
                    # Function has no return — may be intentional (procedures)
                    pass

        # Check for operator precedence issues in return statements
        # e.g. return a + b / 2  (likely meant (a+b)/2)
        for node in ast.walk(tree):
            if isinstance(node, ast.Return) and node.value:
                val = node.value
                if isinstance(val, ast.BinOp) and isinstance(val.op, ast.Add):
                    right = val.right
                    if isinstance(right, ast.BinOp) and isinstance(right.op, ast.Div):
                        issues.append(
                            "Potential operator precedence issue: "
                            "'a + b / 2' computes as 'a + (b/2)', not '(a+b)/2'. "
                            "Consider adding parentheses if average is intended."
                        )

        # Check for = instead of == in condition (can't detect reliably via AST alone)
        # Check for off-by-one in range
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                if isinstance(node.iter, ast.Call):
                    func = node.iter
                    if isinstance(func.func, ast.Name) and func.func.id == "range":
                        args = func.args
                        if len(args) == 1 and isinstance(args[0], ast.Constant):
                            pass  # range(n) — normal pattern

    if issues:
        return {
            "is_logical": True,
            "category": "logical",
            "severity": SEVERITY_MEDIUM,
            "issues": issues,
            "recommendation": (
                "Potential logical issue detected — manual review recommended. "
                "The system will NOT automatically modify code for logical issues "
                "without explicit confirmation."
            ),
            "confidence": 0.60,
        }

    return {
        "is_logical": False,
        "issues": [],
        "recommendation": "",
    }


# ================================================================
# INTERNAL HELPERS
# ================================================================


def _get_hints(
    category: str,
    error_type: str,
    error_msg: str,
    analysis: dict[str, Any] | None,
) -> list[str]:
    """Return actionable repair hints for the given category."""
    hints: list[str] = []

    if category == "syntax":
        hints = [
            "Check for missing colons (:) after if/for/while/def/class",
            "Check for mismatched brackets () [] {}",
            "Check for unclosed string quotes",
            "Check for missing comma between function arguments",
        ]

    elif category == "indentation":
        hints = [
            "Check that all code inside blocks is consistently indented (4 spaces recommended)",
            "Do not mix tabs and spaces",
            "Ensure function/class body is indented one level deeper than the def/class line",
        ]

    elif category == "name":
        undefined = []
        if analysis:
            undefined = analysis.get("undefined_variable_candidates", [])
        hints = [
            "Check variable spelling and casing",
            "Ensure the variable is defined before it is used",
            "Check if a required import is missing",
        ]
        if undefined:
            hints.append(f"Possible undefined names: {', '.join(undefined[:5])}")

    elif category == "type":
        hints = [
            "Check operand types before operations (str + int is not allowed directly)",
            "Use str(), int(), float() to convert types explicitly",
            "Check function argument count and types",
        ]

    elif category == "index":
        hints = [
            "Check list/tuple length before accessing by index",
            "Python lists are zero-indexed (first element is index 0)",
            "Use len() to check the collection size",
            "Consider using a conditional check: if index < len(list):",
        ]

    elif category == "key":
        hints = [
            "Use dict.get(key) instead of dict[key] to avoid KeyError",
            "Check if the key exists: if key in dict:",
            "Print dict.keys() to see what keys are available",
        ]

    elif category == "attribute":
        hints = [
            "Check attribute spelling (Python is case-sensitive)",
            "Check the object type — is it the type you expect?",
            "Use dir(obj) to see available attributes",
        ]

    elif category == "import":
        module_match = re.search(r"No module named '([^']+)'", error_msg)
        if module_match:
            module = module_match.group(1)
            hints = [
                f"Run: pip install {module}",
                f"Check that '{module}' is spelled correctly",
                "Verify the package is installed in the active virtual environment",
            ]
        else:
            hints = [
                "Check module name spelling",
                "Install missing packages with pip install <package>",
            ]

    elif category == "zero_division":
        hints = [
            "Add a guard before dividing: if denominator != 0:",
            "Use a conditional expression: result = a / b if b != 0 else 0",
        ]

    elif category == "infinite_loop":
        hints = [
            "Check loop termination condition",
            "Ensure the loop variable is updated inside the loop",
            "Add a maximum iteration counter as a safety guard",
        ]

    elif category == "logical":
        hints = [
            "Manual review recommended",
            "Add unit tests to verify expected vs actual output",
            "Check operator precedence (especially + - * /)",
            "Check loop bounds (off-by-one errors)",
        ]

    return hints


def _no_error_classification() -> dict[str, Any]:
    return {
        "category": "none",
        "severity": "NONE",
        "is_fixable": False,
        "requires_llm": False,
        "is_logical": False,
        "confidence": 1.0,
        "reason": "No error detected in this code.",
        "hints": [],
        "error_type": "",
    }
