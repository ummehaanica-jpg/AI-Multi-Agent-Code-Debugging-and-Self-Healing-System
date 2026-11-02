"""
Agent 5 — Repair Generation Agent

Generates rule-based repair candidates for Python code.
"""

from __future__ import annotations

import ast
import re
from typing import Any


def fix_code(
    code: str,
    error_type: str,
    error_msg: str,
) -> dict[str, Any]:
    """
    Generate a repair for the detected error.
    """

    if error_type == "NameError":
        fixed_code = _fix_name_error(code, error_msg)

        if fixed_code != code:
            return {
                "fixed_code": fixed_code,
                "method": "rule-based",
                "applied_rule": "NameError",
            }

    if error_type == "SyntaxError":
        fixed_code = _fix_syntax_error(code)

        if fixed_code != code:
            return {
                "fixed_code": fixed_code,
                "method": "rule-based",
                "applied_rule": "SyntaxError",
            }

    if error_type == "IndentationError":
        fixed_code = _fix_indentation(code)

        if fixed_code != code:
            return {
                "fixed_code": fixed_code,
                "method": "rule-based",
                "applied_rule": "IndentationError",
            }

    if error_type == "IndexError":
        fixed_code = _fix_index_error(code, error_msg)

        if fixed_code != code:
            return {
                "fixed_code": fixed_code,
                "method": "rule-based",
                "applied_rule": "IndexError",
            }

    if error_type == "ZeroDivisionError":
        fixed_code = _fix_zero_division(code)

        if fixed_code != code:
            return {
                "fixed_code": fixed_code,
                "method": "rule-based",
                "applied_rule": "ZeroDivisionError",
            }

    return {
        "fixed_code": code,
        "method": "unchanged",
        "applied_rule": "none",
    }


def _fix_name_error(code: str, error_msg: str) -> str:
    """
    Fix NameError using Python's 'Did you mean' suggestion.

    Example:
        name 'student_nme' is not defined.
        Did you mean: 'student_name'?
    """

    match = re.search(
        r"""name ['"]([^'"]+)['"] is not defined.*?Did you mean:\s*['"]([^'"]+)['"]\?""",
        error_msg,
        re.IGNORECASE,
    )

    if not match:
        return code

    wrong_name = match.group(1)
    correct_name = match.group(2)

    fixed_code = re.sub(
        rf"\b{re.escape(wrong_name)}\b",
        correct_name,
        code,
    )

    if fixed_code != code and _syntax_valid(fixed_code):
        return fixed_code

    return code


def _fix_syntax_error(code: str) -> str:
    """Basic syntax repair."""

    lines = code.splitlines()
    changed = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        keywords = (
            "if ",
            "elif ",
            "else",
            "for ",
            "while ",
            "def ",
            "class ",
            "try",
            "except",
            "finally",
            "with ",
        )

        if stripped.startswith(keywords) and not stripped.endswith(":"):
            lines[i] = line + ":"
            changed = True

    fixed_code = "\n".join(lines)

    if changed and _syntax_valid(fixed_code):
        return fixed_code

    return code


def _fix_indentation(code: str) -> str:
    """Basic indentation normalization."""

    lines = code.splitlines()
    fixed_lines = []

    indent = 0

    for line in lines:
        stripped = line.strip()

        if not stripped:
            fixed_lines.append("")
            continue

        if stripped.startswith(
            ("elif ", "else:", "except", "finally:")
        ):
            indent = max(0, indent - 1)

        fixed_lines.append("    " * indent + stripped)

        if stripped.endswith(":"):
            indent += 1

    fixed_code = "\n".join(fixed_lines)

    if fixed_code != code and _syntax_valid(fixed_code):
        return fixed_code

    return code


def _fix_index_error(code: str, error_msg: str) -> str:
    """Protect a simple list index from going out of range."""

    if "list index out of range" not in error_msg.lower():
        return code

    match = re.search(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\[(\d+)\]",
        code,
    )

    if not match:
        return code

    variable = match.group(1)
    index = match.group(2)

    original = f"{variable}[{index}]"

    replacement = (
        f"{variable}[{index}] "
        f"if len({variable}) > {index} else None"
    )

    fixed_code = code.replace(
        original,
        replacement,
        1,
    )

    if fixed_code != code and _syntax_valid(fixed_code):
        return fixed_code

    return code


def _fix_zero_division(code: str) -> str:
    """Basic protection against literal division by zero."""

    fixed_code = re.sub(
        r"/\s*0\b",
        "/ 1",
        code,
    )

    if fixed_code != code and _syntax_valid(fixed_code):
        return fixed_code

    return code


def _syntax_valid(code: str) -> bool:
    """Check whether Python can parse the repaired code."""

    try:
        ast.parse(code)
        return True
    except (SyntaxError, ValueError, TypeError):
        return False