"""
Agent 1 - Error Detection Agent

Detects Python syntax and runtime errors.

Design:
1. Parse the source with AST to detect syntax errors.
2. If syntax is valid, execute the program in a controlled subprocess.
3. Capture structured diagnostic information.
4. Never execute arbitrary user code directly inside the Streamlit process.

NOTE:
Subprocess execution improves isolation from the application process, but it
is NOT a complete security sandbox. Containerization is recommended for
production deployment.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tempfile
from typing import Any


DEFAULT_TIMEOUT = 5


def detect_errors(code: str, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """
    Detect syntax and runtime errors in Python source code.

    Returns:
        {
            "has_error": bool,
            "error_type": str,
            "error_msg": str,
            "line_no": int | None,
            "column_no": int | None,
            "source_line": str,
            "context_lines": list[str],
            "traceback": str,
            "stdout": str,
            "stderr": str,
            "phase": "syntax" | "runtime" | "none",
            "timed_out": bool,
            "raw_code": str
        }
    """

    result: dict[str, Any] = {
        "has_error": False,
        "error_type": "",
        "error_msg": "",
        "line_no": None,
        "column_no": None,
        "source_line": "",
        "context_lines": [],
        "traceback": "",
        "stdout": "",
        "stderr": "",
        "phase": "none",
        "timed_out": False,
        "raw_code": code,
    }

    # ============================================================
    # PHASE 1 — STATIC SYNTAX ANALYSIS
    # ============================================================

    try:
        ast.parse(code)

    except SyntaxError as exc:
        line_no = exc.lineno
        column_no = exc.offset

        result.update(
            {
                "has_error": True,
                "error_type": "SyntaxError",
                "error_msg": str(exc.msg),
                "line_no": line_no,
                "column_no": column_no,
                "source_line": _get_source_line(code, line_no),
                "context_lines": _get_context_lines(code, line_no),
                "traceback": "",
                "phase": "syntax",
            }
        )

        return result

    # ============================================================
    # PHASE 2 — RUNTIME ANALYSIS
    # ============================================================

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as temp_file:
            temp_file.write(code)
            temp_path = temp_file.name

        process = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.path.dirname(temp_path),
            stdin=subprocess.DEVNULL,
        )

        stdout = process.stdout.strip()
        stderr = process.stderr.strip()

        result["stdout"] = stdout
        result["stderr"] = stderr

        # --------------------------------------------------------
        # Program executed successfully
        # --------------------------------------------------------

        if process.returncode == 0:
            return result

        # --------------------------------------------------------
        # Program produced a runtime error
        # --------------------------------------------------------

        error_type, error_msg, line_no = _parse_traceback(stderr)

        result.update(
            {
                "has_error": True,
                "error_type": error_type,
                "error_msg": error_msg,
                "line_no": line_no,
                "column_no": None,
                "source_line": _get_source_line(code, line_no),
                "context_lines": _get_context_lines(code, line_no),
                "traceback": stderr,
                "phase": "runtime",
            }
        )

        return result

    except subprocess.TimeoutExpired as exc:
        stdout = ""

        if isinstance(exc.stdout, bytes):
            stdout = exc.stdout.decode("utf-8", errors="replace")
        elif isinstance(exc.stdout, str):
            stdout = exc.stdout

        result.update(
            {
                "has_error": True,
                "error_type": "TimeoutError",
                "error_msg": f"Program execution exceeded {timeout} seconds.",
                "line_no": None,
                "column_no": None,
                "source_line": "",
                "context_lines": [],
                "traceback": "",
                "stdout": stdout.strip(),
                "stderr": f"Execution timed out after {timeout} seconds.",
                "phase": "runtime",
                "timed_out": True,
            }
        )

        return result

    except Exception as exc:
        # This is an error in the detection infrastructure itself,
        # not necessarily an error in the user's program.
        result.update(
            {
                "has_error": True,
                "error_type": "DetectionError",
                "error_msg": str(exc),
                "phase": "runtime",
            }
        )

        return result

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


# ================================================================
# TRACEBACK PARSER
# ================================================================


def _parse_traceback(stderr: str) -> tuple[str, str, int | None]:
    """
    Extract:

        error type
        error message
        line number

    from a Python traceback.
    """

    if not stderr:
        return "RuntimeError", "Program exited with an unknown error.", None

    lines = [line.strip() for line in stderr.splitlines() if line.strip()]

    # Look for the final Python exception line.
    #
    # Examples:
    #
    # NameError: name 'total' is not defined
    # ZeroDivisionError: division by zero
    # TypeError: unsupported operand type(s)...
    #

    exception_pattern = re.compile(
        r"^(?P<type>[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)):\s*(?P<msg>.*)$"
    )

    error_type = "RuntimeError"
    error_msg = lines[-1] if lines else "Unknown runtime error."

    for line in reversed(lines):
        match = exception_pattern.match(line)

        if match:
            error_type = match.group("type")
            error_msg = match.group("msg").strip()
            break

    # Extract the final line number belonging to the user's temporary file.
    line_no = None

    line_pattern = re.compile(r'File ".*?", line (\d+)')

    for line in reversed(stderr.splitlines()):
        match = line_pattern.search(line)

        if match:
            try:
                line_no = int(match.group(1))
                break
            except ValueError:
                pass

    return error_type, error_msg, line_no


# ================================================================
# SOURCE CONTEXT HELPERS
# ================================================================


def _get_source_line(code: str, line_no: int | None) -> str:
    """Return the source line associated with an error."""

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
    """
    Return a small source-code window around the detected line.

    Example:
        line 5 with radius 2
        -> lines 3 through 7
    """

    if line_no is None:
        return []

    lines = code.splitlines()

    if not lines:
        return []

    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)

    context = []

    for number in range(start, end + 1):
        context.append(f"{number}: {lines[number - 1]}")

    return context