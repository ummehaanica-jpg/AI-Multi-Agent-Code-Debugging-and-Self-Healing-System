"""
Agent 2 - Code Analysis Agent

Performs AST-based structural and root-cause-oriented analysis of Python
source code.

The original public interface is preserved:
    analyze_code(code) -> dict

Additional analysis includes:
- function metadata
- class metadata
- imports
- variables
- function calls
- control-flow counts
- variable definitions and uses
- complexity estimates
- error-related source context
- possible root-cause hints

This module intentionally does not claim full semantic/type inference.
"""

from __future__ import annotations

import ast
from typing import Any


def analyze_code(
    code: str,
    error_type: str | None = None,
    error_msg: str | None = None,
    error_line: int | None = None,
) -> dict[str, Any]:
    """
    Analyze Python source code using the Abstract Syntax Tree.

    Existing keys are preserved for backward compatibility with app.py
    and architecture.py.

    Optional error information can be supplied later by the orchestrator
    to improve root-cause analysis.
    """

    result: dict[str, Any] = {
        # --------------------------------------------------------
        # Existing fields - DO NOT REMOVE
        # --------------------------------------------------------
        "functions": [],
        "classes": [],
        "imports": [],
        "variables": [],
        "total_lines": len(code.splitlines()),
        "parse_ok": False,

        # --------------------------------------------------------
        # New structural analysis
        # --------------------------------------------------------
        "function_details": [],
        "class_details": [],
        "function_calls": [],
        "control_flow": {
            "if_statements": 0,
            "for_loops": 0,
            "while_loops": 0,
            "try_blocks": 0,
            "with_blocks": 0,
            "match_statements": 0,
        },
        "return_statements": 0,
        "raise_statements": 0,
        "assert_statements": 0,

        # --------------------------------------------------------
        # Variable analysis
        # --------------------------------------------------------
        "defined_variables": [],
        "used_variables": [],
        "undefined_variable_candidates": [],

        # --------------------------------------------------------
        # Complexity
        # --------------------------------------------------------
        "complexity": {
            "total_decision_points": 0,
            "estimated_complexity": 1,
        },
        "function_complexity": {},

        # --------------------------------------------------------
        # Error/root-cause analysis
        # --------------------------------------------------------
        "error_context": {
            "error_type": error_type,
            "error_message": error_msg,
            "error_line": error_line,
            "source_line": "",
            "context_lines": [],
        },
        "root_cause": {
            "category": "Unknown",
            "summary": "",
            "evidence": [],
            "suggested_strategy": "",
        },

        # --------------------------------------------------------
        # Quality indicators
        # --------------------------------------------------------
        "warnings": [],
    }

    # ============================================================
    # PARSE AST
    # ============================================================

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        result["parse_ok"] = False

        result["error_context"].update(
            {
                "error_type": "SyntaxError",
                "error_message": exc.msg,
                "error_line": exc.lineno,
                "source_line": _get_source_line(code, exc.lineno),
                "context_lines": _get_context_lines(code, exc.lineno),
            }
        )

        result["root_cause"] = {
            "category": "Syntax",
            "summary": "The source code could not be parsed as valid Python.",
            "evidence": [
                f"Parser message: {exc.msg}",
                f"Line: {exc.lineno}",
            ],
            "suggested_strategy": (
                "Inspect the reported line and nearby syntax such as "
                "colons, parentheses, indentation, quotes, and delimiters."
            ),
        }

        return result

    result["parse_ok"] = True

    # ============================================================
    # FIRST PASS - BASIC AST STRUCTURE
    # ============================================================

    for node in ast.walk(tree):

        # --------------------------------------------------------
        # Functions
        # --------------------------------------------------------

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):

            result["functions"].append(node.name)

            function_info = _analyze_function(node)

            result["function_details"].append(function_info)

            result["function_complexity"][node.name] = (
                function_info["complexity"]
            )

        # --------------------------------------------------------
        # Classes
        # --------------------------------------------------------

        elif isinstance(node, ast.ClassDef):

            result["classes"].append(node.name)

            result["class_details"].append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "methods": [
                        child.name
                        for child in node.body
                        if isinstance(
                            child,
                            (ast.FunctionDef, ast.AsyncFunctionDef),
                        )
                    ],
                    "bases": [
                        _safe_unparse(base)
                        for base in node.bases
                    ],
                }
            )

        # --------------------------------------------------------
        # Imports
        # --------------------------------------------------------

        elif isinstance(node, ast.Import):

            for alias in node.names:
                result["imports"].append(alias.name)

        elif isinstance(node, ast.ImportFrom):

            module = node.module or ""

            for alias in node.names:

                if alias.name == "*":
                    result["imports"].append(f"{module}.*")
                else:
                    result["imports"].append(
                        f"{module}.{alias.name}"
                    )

        # --------------------------------------------------------
        # Variables
        # --------------------------------------------------------

        elif isinstance(node, ast.Assign):

            for target in node.targets:
                result["variables"].extend(
                    _extract_assigned_names(target)
                )

        elif isinstance(node, ast.AnnAssign):

            result["variables"].extend(
                _extract_assigned_names(node.target)
            )

        elif isinstance(node, ast.AugAssign):

            result["variables"].extend(
                _extract_assigned_names(node.target)
            )

        # --------------------------------------------------------
        # Function calls
        # --------------------------------------------------------

        elif isinstance(node, ast.Call):

            call_name = _get_call_name(node)

            if call_name:
                result["function_calls"].append(
                    {
                        "name": call_name,
                        "line": getattr(node, "lineno", None),
                    }
                )

        # --------------------------------------------------------
        # Control flow
        # --------------------------------------------------------

        elif isinstance(node, ast.If):
            result["control_flow"]["if_statements"] += 1

        elif isinstance(node, ast.For):
            result["control_flow"]["for_loops"] += 1

        elif isinstance(node, ast.While):
            result["control_flow"]["while_loops"] += 1

        elif isinstance(node, ast.Try):
            result["control_flow"]["try_blocks"] += 1

        elif isinstance(node, ast.With):
            result["control_flow"]["with_blocks"] += 1

        elif isinstance(node, ast.Match):
            result["control_flow"]["match_statements"] += 1

        elif isinstance(node, ast.Return):
            result["return_statements"] += 1

        elif isinstance(node, ast.Raise):
            result["raise_statements"] += 1

        elif isinstance(node, ast.Assert):
            result["assert_statements"] += 1

    # ============================================================
    # VARIABLE USE ANALYSIS
    # ============================================================

    defined = set()
    used = set()

    for node in ast.walk(tree):

        if isinstance(node, ast.Name):

            if isinstance(node.ctx, ast.Store):
                defined.add(node.id)

            elif isinstance(node.ctx, ast.Load):
                used.add(node.id)

    result["defined_variables"] = sorted(defined)
    result["used_variables"] = sorted(used)

    # Ignore common built-ins when finding candidates.
    builtins = _PYTHON_BUILTINS

    result["undefined_variable_candidates"] = sorted(
        used - defined - builtins
    )

    # Preserve the original "variables" field while making it cleaner.
    result["variables"] = list(
        dict.fromkeys(result["variables"])
    )

    # ============================================================
    # DEDUPLICATE COLLECTIONS
    # ============================================================

    result["functions"] = list(
        dict.fromkeys(result["functions"])
    )

    result["classes"] = list(
        dict.fromkeys(result["classes"])
    )

    result["imports"] = list(
        dict.fromkeys(result["imports"])
    )

    result["function_calls"] = _deduplicate_dicts(
        result["function_calls"]
    )

    # ============================================================
    # COMPLEXITY ESTIMATION
    # ============================================================

    decision_points = 0

    for node in ast.walk(tree):

        if isinstance(
            node,
            (
                ast.If,
                ast.For,
                ast.While,
                ast.Try,
                ast.ExceptHandler,
                ast.IfExp,
                ast.Match,
            ),
        ):
            decision_points += 1

        elif isinstance(node, ast.BoolOp):
            # "a and b and c" contains additional logical decisions.
            decision_points += max(1, len(node.values) - 1)

    result["complexity"] = {
        "total_decision_points": decision_points,
        "estimated_complexity": 1 + decision_points,
    }

    # ============================================================
    # SOURCE WARNINGS
    # ============================================================

    result["warnings"] = _detect_structural_warnings(
        tree,
        result,
    )

    # ============================================================
    # ERROR CONTEXT / ROOT CAUSE
    # ============================================================

    if error_type or error_msg or error_line:

        result["error_context"].update(
            {
                "error_type": error_type,
                "error_message": error_msg,
                "error_line": error_line,
                "source_line": _get_source_line(
                    code,
                    error_line,
                ),
                "context_lines": _get_context_lines(
                    code,
                    error_line,
                ),
            }
        )

        result["root_cause"] = _infer_root_cause(
            tree,
            code,
            error_type,
            error_msg,
            error_line,
            result,
        )

    else:

        result["root_cause"] = {
            "category": "Not specified",
            "summary": (
                "No specific error information was supplied. "
                "Structural analysis was completed."
            ),
            "evidence": [
                f"Functions detected: {len(result['functions'])}",
                f"Classes detected: {len(result['classes'])}",
                f"Function calls detected: {len(result['function_calls'])}",
            ],
            "suggested_strategy": (
                "Provide the detected exception and source line "
                "to perform targeted root-cause analysis."
            ),
        }

    return result


# ================================================================
# FUNCTION ANALYSIS
# ================================================================


def _analyze_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, Any]:

    complexity = 1

    for child in ast.walk(node):

        if isinstance(
            child,
            (
                ast.If,
                ast.For,
                ast.While,
                ast.Try,
                ast.ExceptHandler,
                ast.IfExp,
                ast.Match,
            ),
        ):
            complexity += 1

        elif isinstance(child, ast.BoolOp):
            complexity += max(1, len(child.values) - 1)

    arguments = []

    for arg in node.args.posonlyargs:
        arguments.append(arg.arg)

    for arg in node.args.args:
        arguments.append(arg.arg)

    for arg in node.args.kwonlyargs:
        arguments.append(arg.arg)

    if node.args.vararg:
        arguments.append("*" + node.args.vararg.arg)

    if node.args.kwarg:
        arguments.append("**" + node.args.kwarg.arg)

    return {
        "name": node.name,
        "line": getattr(node, "lineno", None),
        "end_line": getattr(node, "end_lineno", None),
        "arguments": arguments,
        "complexity": complexity,
        "returns": sum(
            isinstance(child, ast.Return)
            for child in ast.walk(node)
        ),
        "calls": [
            _get_call_name(child)
            for child in ast.walk(node)
            if isinstance(child, ast.Call)
            and _get_call_name(child)
        ],
    }


# ================================================================
# ROOT CAUSE ANALYSIS
# ================================================================


def _infer_root_cause(
    tree: ast.AST,
    code: str,
    error_type: str | None,
    error_msg: str | None,
    error_line: int | None,
    analysis: dict[str, Any],
) -> dict[str, Any]:

    error_type = error_type or ""
    error_msg = error_msg or ""

    source_line = _get_source_line(
        code,
        error_line,
    )

    # ------------------------------------------------------------
    # NameError
    # ------------------------------------------------------------

    if error_type == "NameError":

        candidates = analysis["undefined_variable_candidates"]

        return {
            "category": "Undefined Name",
            "summary": (
                "A variable or identifier is being referenced "
                "without a valid definition in the analyzed scope."
            ),
            "evidence": [
                f"Source line: {source_line}",
                f"Undefined-name candidates: {candidates}",
            ],
            "suggested_strategy": (
                "Check spelling, variable initialization, scope, "
                "and whether the identifier should be imported."
            ),
        }

    # ------------------------------------------------------------
    # TypeError
    # ------------------------------------------------------------

    if error_type == "TypeError":

        return {
            "category": "Type Mismatch",
            "summary": (
                "An operation or function call received an "
                "incompatible value or argument type."
            ),
            "evidence": [
                f"Source line: {source_line}",
                f"Runtime message: {error_msg}",
            ],
            "suggested_strategy": (
                "Inspect the operands and function arguments and "
                "make their types compatible with the operation."
            ),
        }

    # ------------------------------------------------------------
    # IndexError
    # ------------------------------------------------------------

    if error_type == "IndexError":

        return {
            "category": "Invalid Index",
            "summary": (
                "A sequence or collection is being accessed using "
                "an index outside its valid range."
            ),
            "evidence": [
                f"Source line: {source_line}",
                f"Runtime message: {error_msg}",
            ],
            "suggested_strategy": (
                "Inspect the collection length and index value. "
                "Use valid bounds or explicit boundary checks."
            ),
        }

    # ------------------------------------------------------------
    # AttributeError
    # ------------------------------------------------------------

    if error_type == "AttributeError":

        return {
            "category": "Invalid Attribute Access",
            "summary": (
                "The program attempts to access an attribute or "
                "method that is not available on the target object."
            ),
            "evidence": [
                f"Source line: {source_line}",
                f"Runtime message: {error_msg}",
            ],
            "suggested_strategy": (
                "Check the object's type, attribute spelling, "
                "and available methods."
            ),
        }

    # ------------------------------------------------------------
    # ZeroDivisionError
    # ------------------------------------------------------------

    if error_type == "ZeroDivisionError":

        return {
            "category": "Invalid Arithmetic Operation",
            "summary": (
                "The program attempts to divide or perform modulo "
                "operation using zero as the divisor."
            ),
            "evidence": [
                f"Source line: {source_line}",
                f"Runtime message: {error_msg}",
            ],
            "suggested_strategy": (
                "Validate the divisor before performing the "
                "operation."
            ),
        }

    # ------------------------------------------------------------
    # KeyError
    # ------------------------------------------------------------

    if error_type == "KeyError":

        return {
            "category": "Missing Dictionary Key",
            "summary": (
                "A dictionary key was requested but was not present."
            ),
            "evidence": [
                f"Source line: {source_line}",
                f"Runtime message: {error_msg}",
            ],
            "suggested_strategy": (
                "Check key existence or use an appropriate default "
                "lookup mechanism."
            ),
        }

    # ------------------------------------------------------------
    # ValueError
    # ------------------------------------------------------------

    if error_type == "ValueError":

        return {
            "category": "Invalid Value",
            "summary": (
                "A function or operation received a value of an "
                "acceptable type but an inappropriate value."
            ),
            "evidence": [
                f"Source line: {source_line}",
                f"Runtime message: {error_msg}",
            ],
            "suggested_strategy": (
                "Validate the value before passing it to the "
                "operation."
            ),
        }

    # ------------------------------------------------------------
    # ImportError / ModuleNotFoundError
    # ------------------------------------------------------------

    if error_type in {
        "ImportError",
        "ModuleNotFoundError",
    }:

        return {
            "category": "Import Dependency",
            "summary": (
                "The program could not resolve a required import."
            ),
            "evidence": [
                f"Source line: {source_line}",
                f"Runtime message: {error_msg}",
            ],
            "suggested_strategy": (
                "Check the module name, installed dependencies, "
                "and import path."
            ),
        }

    # ------------------------------------------------------------
    # UnboundLocalError
    # ------------------------------------------------------------

    if error_type == "UnboundLocalError":

        return {
            "category": "Variable Scope",
            "summary": (
                "A local variable is being referenced before a "
                "valid local assignment."
            ),
            "evidence": [
                f"Source line: {source_line}",
                f"Runtime message: {error_msg}",
            ],
            "suggested_strategy": (
                "Check local variable initialization and assignment "
                "order inside the function."
            ),
        }

    # ------------------------------------------------------------
    # SyntaxError
    # ------------------------------------------------------------

    if error_type == "SyntaxError":

        return {
            "category": "Syntax",
            "summary": (
                "Python could not parse the source code."
            ),
            "evidence": [
                f"Source line: {source_line}",
                f"Parser message: {error_msg}",
            ],
            "suggested_strategy": (
                "Inspect punctuation, indentation, delimiters, "
                "quotes, and required syntax tokens."
            ),
        }

    # ------------------------------------------------------------
    # Generic runtime error
    # ------------------------------------------------------------

    return {
        "category": "Runtime",
        "summary": (
            "A runtime failure was detected, but the analyzer "
            "does not have a specialized root-cause rule for it."
        ),
        "evidence": [
            f"Source line: {source_line}",
            f"Runtime message: {error_msg}",
        ],
        "suggested_strategy": (
            "Use the traceback and surrounding source context "
            "to determine the failing operation."
        ),
    }


# ================================================================
# STRUCTURAL WARNINGS
# ================================================================


def _detect_structural_warnings(
    tree: ast.AST,
    analysis: dict[str, Any],
) -> list[str]:

    warnings = []

    if not analysis["functions"] and not analysis["classes"]:
        warnings.append(
            "No user-defined functions or classes were detected."
        )

    if analysis["complexity"]["estimated_complexity"] > 10:
        warnings.append(
            "The estimated overall control-flow complexity is relatively high."
        )

    for name, complexity in analysis["function_complexity"].items():

        if complexity > 8:
            warnings.append(
                f"Function '{name}' has relatively high estimated complexity ({complexity})."
            )

    if analysis["undefined_variable_candidates"]:
        warnings.append(
            "Some loaded identifiers are not defined within the analyzed source. "
            "They may be built-ins, imports, globals, or genuine undefined names."
        )

    return warnings


# ================================================================
# AST HELPERS
# ================================================================


def _extract_assigned_names(
    target: ast.AST,
) -> list[str]:

    names = []

    if isinstance(target, ast.Name):
        names.append(target.id)

    elif isinstance(target, (ast.Tuple, ast.List)):

        for element in target.elts:
            names.extend(
                _extract_assigned_names(element)
            )

    elif isinstance(target, ast.Starred):

        names.extend(
            _extract_assigned_names(target.value)
        )

    return names


def _get_call_name(
    node: ast.Call,
) -> str | None:

    if isinstance(node.func, ast.Name):
        return node.func.id

    if isinstance(node.func, ast.Attribute):

        parts = []

        current: ast.AST | None = node.func

        while isinstance(current, ast.Attribute):

            parts.append(current.attr)
            current = current.value

        if isinstance(current, ast.Name):
            parts.append(current.id)
            return ".".join(reversed(parts))

    return None


def _safe_unparse(node: ast.AST) -> str:

    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def _get_source_line(
    code: str,
    line_no: int | None,
) -> str:

    if line_no is None:
        return ""

    lines = code.splitlines()

    if 1 <= line_no <= len(lines):
        return lines[line_no - 1]

    return ""


def _get_context_lines(
    code: str,
    line_no: int | None,
    radius: int = 2,
) -> list[str]:

    if line_no is None:
        return []

    lines = code.splitlines()

    if not lines:
        return []

    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)

    return [
        f"{number}: {lines[number - 1]}"
        for number in range(start, end + 1)
    ]


def _deduplicate_dicts(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    seen = set()
    result = []

    for item in items:

        key = (
            item.get("name"),
            item.get("line"),
        )

        if key not in seen:
            seen.add(key)
            result.append(item)

    return result


# ================================================================
# COMMON PYTHON BUILTINS
# ================================================================

_PYTHON_BUILTINS = {
    "abs",
    "all",
    "any",
    "ascii",
    "bin",
    "bool",
    "breakpoint",
    "bytearray",
    "bytes",
    "callable",
    "chr",
    "classmethod",
    "compile",
    "complex",
    "delattr",
    "dict",
    "dir",
    "divmod",
    "enumerate",
    "eval",
    "exec",
    "filter",
    "float",
    "format",
    "frozenset",
    "getattr",
    "globals",
    "hasattr",
    "hash",
    "help",
    "hex",
    "id",
    "input",
    "int",
    "isinstance",
    "issubclass",
    "iter",
    "len",
    "list",
    "locals",
    "map",
    "max",
    "memoryview",
    "min",
    "next",
    "object",
    "oct",
    "open",
    "ord",
    "pow",
    "print",
    "property",
    "range",
    "repr",
    "reversed",
    "round",
    "set",
    "setattr",
    "slice",
    "sorted",
    "staticmethod",
    "str",
    "sum",
    "super",
    "tuple",
    "type",
    "vars",
    "zip",
    "__import__",
    "True",
    "False",
    "None",
}