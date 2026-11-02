"""
Agents 6 — Test Generator Agent

Generates basic test cases for repaired Python functions.

Design:
- Uses AST to find function signatures
- Generates test cases based on function names, argument patterns, and error context
- Does NOT execute arbitrary code to generate test values (safety)
- Generates runnable Python test code that the Validator can execute
- Supports LLM-assisted test generation when API key is available

IMPORTANT:
- Tests are generated as heuristics, not guarantees of correctness
- Logical errors may require human-written tests
- Generated tests are simple sanity checks, not comprehensive test suites
"""
from __future__ import annotations

import ast
import re
from typing import Any


# ================================================================
# PUBLIC API
# ================================================================


def generate_tests(
    code: str,
    error_type: str = "",
    error_msg: str = "",
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate test cases for the given code.

    Returns:
    {
        "tests": list of test dicts,
        "test_code": runnable Python test code string,
        "test_count": int,
        "source": "rule-based" | "llm",
        "note": str
    }
    """
    tests: list[dict[str, Any]] = []

    # Extract functions from code
    functions = _extract_functions(code)

    if not functions:
        return {
            "tests": [],
            "test_code": "",
            "test_count": 0,
            "source": "rule-based",
            "note": "No testable functions found in the code.",
        }

    # Generate tests for each function
    for func_info in functions:
        func_tests = _generate_function_tests(
            func_info, code, error_type, error_msg
        )
        tests.extend(func_tests)

    # Build runnable test code
    test_code = _build_test_code(code, tests)

    return {
        "tests": tests,
        "test_code": test_code,
        "test_count": len(tests),
        "source": "rule-based",
        "note": (
            "Tests are heuristic sanity checks. "
            "They verify basic execution and expected output patterns. "
            "Logical correctness requires human-written tests."
        ),
    }


# ================================================================
# FUNCTION EXTRACTION
# ================================================================


def _extract_functions(code: str) -> list[dict[str, Any]]:
    """Extract function signatures from code using AST."""
    functions = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Skip private/dunder methods for simplicity
            if node.name.startswith("__"):
                continue

            args = []
            for arg in node.args.args:
                args.append(arg.arg)

            # Get default values
            defaults = []
            for default in node.args.defaults:
                try:
                    defaults.append(ast.literal_eval(default))
                except Exception:
                    defaults.append(None)

            # Detect return type hint
            return_annotation = ""
            if node.returns:
                try:
                    return_annotation = ast.unparse(node.returns)
                except Exception:
                    pass

            # Check if function has a return statement with a value
            has_return = any(
                isinstance(child, ast.Return) and child.value is not None
                for child in ast.walk(node)
            )

            # Check for docstring
            docstring = ""
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
            ):
                docstring = str(node.body[0].value.value)

            functions.append({
                "name": node.name,
                "args": args,
                "defaults": defaults,
                "has_return": has_return,
                "return_annotation": return_annotation,
                "docstring": docstring,
                "line": node.lineno,
            })

    return functions


# ================================================================
# TEST GENERATION PER FUNCTION
# ================================================================


def _generate_function_tests(
    func_info: dict[str, Any],
    code: str,
    error_type: str,
    error_msg: str,
) -> list[dict[str, Any]]:
    """Generate test cases for a single function."""
    tests = []
    name = func_info["name"]
    args = func_info["args"]
    # Remove 'self' from args for methods
    args = [a for a in args if a != "self"]

    if not args and not func_info["has_return"]:
        # Function with no args and no return — just test it doesn't crash
        tests.append({
            "name": f"test_{name}_no_crash",
            "function": name,
            "inputs": {},
            "call": f"{name}()",
            "expected": "no_exception",
            "description": f"Verify {name}() runs without raising an exception.",
        })
        return tests

    # Infer sample values for arguments
    sample_values = _infer_arg_values(args, name, error_type, error_msg)

    if not sample_values:
        return tests

    # Test 1: basic call with inferred values
    call_args = ", ".join(
        repr(sample_values.get(arg, 0)) for arg in args
    )
    call_str = f"{name}({call_args})"

    tests.append({
        "name": f"test_{name}_basic",
        "function": name,
        "inputs": sample_values,
        "call": call_str,
        "expected": "no_exception",
        "description": f"Verify {name}({call_args}) runs without raising an exception.",
    })

    # Test 2: check for special logical patterns
    logical_test = _check_logical_pattern(func_info, name, args, code)
    if logical_test:
        tests.append(logical_test)

    return tests


def _infer_arg_values(
    args: list[str],
    func_name: str,
    error_type: str,
    error_msg: str,
) -> dict[str, Any]:
    """
    Infer safe sample values for function arguments.
    Uses argument name heuristics.
    """
    sample_values: dict[str, Any] = {}

    # Detect number-like argument names
    number_keywords = {
        "n", "num", "number", "count", "size", "length", "total",
        "value", "val", "amount", "score", "x", "y", "z",
        "a", "b", "c", "i", "j", "k", "width", "height",
        "age", "salary", "price", "radius",
    }
    string_keywords = {
        "name", "text", "message", "msg", "s", "string",
        "word", "label", "title", "description",
    }
    list_keywords = {
        "lst", "list", "items", "arr", "array", "data",
        "numbers", "values",
    }
    dict_keywords = {"d", "dictionary", "mapping", "config", "settings"}

    for arg in args:
        arg_lower = arg.lower()
        if any(kw in arg_lower for kw in number_keywords):
            sample_values[arg] = 5  # safe non-zero positive integer
        elif any(kw in arg_lower for kw in string_keywords):
            sample_values[arg] = "test"
        elif any(kw in arg_lower for kw in list_keywords):
            sample_values[arg] = [1, 2, 3]
        elif any(kw in arg_lower for kw in dict_keywords):
            sample_values[arg] = {"key": "value"}
        else:
            # Default: use integer 1 for unknown args
            sample_values[arg] = 1

    return sample_values


def _check_logical_pattern(
    func_info: dict[str, Any],
    name: str,
    args: list[str],
    code: str,
) -> dict[str, Any] | None:
    """
    Check for known logical error patterns and generate a revealing test.
    
    Example: average(a, b) returning a + b/2 instead of (a+b)/2
    We generate a test that would catch this.
    """
    if not func_info["has_return"]:
        return None

    # Detect average-like function names
    avg_names = {"average", "avg", "mean", "compute_average", "calc_average"}
    if name.lower() in avg_names and len(args) == 2:
        a_name = args[0]
        b_name = args[1]
        # Test: average(10, 20) should be 15
        # If implementation is a + b/2 = 10 + 10 = 20, it will fail
        return {
            "name": f"test_{name}_correct_average",
            "function": name,
            "inputs": {a_name: 10, b_name: 20},
            "call": f"{name}(10, 20)",
            "expected": 15,
            "expected_type": "value",
            "description": (
                f"Verify {name}(10, 20) == 15. "
                "Detects operator-precedence logical error: "
                "'a + b/2' gives 20 instead of 15."
            ),
        }

    # Detect division/ratio functions
    div_names = {"divide", "ratio", "quotient", "fraction"}
    if name.lower() in div_names and len(args) >= 2:
        return {
            "name": f"test_{name}_nonzero_denominator",
            "function": name,
            "inputs": {args[0]: 10, args[1]: 2},
            "call": f"{name}(10, 2)",
            "expected": 5,
            "expected_type": "value",
            "description": f"Verify {name}(10, 2) == 5.",
        }

    return None


# ================================================================
# TEST CODE BUILDER
# ================================================================



def _build_test_code(original_code: str, tests: list[dict[str, Any]]) -> str:
    """
    Build a runnable test script.
    The repaired code will be supplied separately by the validator.
    """
    if not tests:
        return ""

    lines = [
        "# Auto-generated test code by Test Generator Agent",
        "# Heuristic tests, not a comprehensive test suite",
        "import sys",
        "_PASS = 0",
        "_FAIL = 0",
        "",
    ]

    for test in tests:
        test_name = test["name"]
        call = test["call"]
        expected = test.get("expected", "no_exception")
        expected_type = test.get("expected_type", "no_exception")
        description = test.get("description", "")

        lines.append(f"# Test: {test_name}")
        lines.append(f"# {description}")
        lines.append("try:")

        if expected != "no_exception" and expected_type == "value":
            lines.append(f"    _result = {call}")
            lines.append(f"    if _result == {expected!r}:")
            lines.append(f"        print('PASS: {test_name}')")
            lines.append("        _PASS += 1")
            lines.append("    else:")
            lines.append(
                f"        print(f'FAIL: {test_name} - expected {expected!r}, got {{_result}}')"
            )
            lines.append("        _FAIL += 1")
        else:
            lines.append(f"    _result = {call}")
            lines.append(f"    print('PASS: {test_name}')")
            lines.append("    _PASS += 1")

        lines.append("except Exception as _e:")
        lines.append(
            f"    print(f'FAIL: {test_name} - raised {{type(_e).__name__}}: {{_e}}')"
        )
        lines.append("    _FAIL += 1")
        lines.append("")

    lines.append("print(f'Test Summary: {_PASS} passed, {_FAIL} failed')")
    lines.append("if _FAIL > 0:")
    lines.append("    sys.exit(1)")

    return "\n".join(lines)
