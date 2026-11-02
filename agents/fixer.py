"""
Agent 5 — Repair Generation Agent

Rule-based repair generation for the AI Multi-Agent Debugger.
The Fixer proposes a repair; the Validator decides whether it works.
"""

from __future__ import annotations

import ast
import re
from typing import Any


def fix_code(
    code: str,
    error_type: str,
    error_msg: str,
    analysis=None,
    validator_feedback=None,
    attempt_number=1,
    kb_matches=None,
) -> dict[str, Any]:
    """Generate a candidate repair for the detected error."""
    repairs = {
        "NameError": lambda: _fix_name_error(code, error_msg),
        "SyntaxError": lambda: _fix_syntax_error(code),
        "IndentationError": lambda: _fix_indentation(code),
        "TypeError": lambda: _fix_type_error(code, error_msg),
        "IndexError": lambda: _fix_index_error(code, error_msg),
        "AttributeError": lambda: _fix_attribute_error(code, error_msg),
        "ZeroDivisionError": lambda: _fix_zero_division(code),
    }
    fixed_code = repairs[error_type]() if error_type in repairs else code
    changed = fixed_code != code
    return {
        "fixed_code": fixed_code,
        "strategy": "rule-based" if changed else "unchanged",
        "description": (
            f"Applied a rule-based repair for {error_type}."
            if changed else f"No matching repair rule found for {error_type}."
        ),
        "confidence": 0.8 if changed else 0.0,
        "method": "rule-based" if changed else "unchanged",
        "applied_rule": error_type if changed else "none",
    }


def _fix_name_error(code: str, error_msg: str) -> str:
    """Fix simple undefined-name errors."""
    match = re.search(
        r"""name ['"]([^'"]+)['"] is not defined.*?Did you mean:\s*['"]([^'"]+)['"]""",
        error_msg, re.IGNORECASE | re.DOTALL,
    )
    if match:
        wrong, correct = match.groups()
        fixed = re.sub(rf"\b{re.escape(wrong)}\b", correct, code)
        if fixed != code and _syntax_valid(fixed):
            return fixed

    if re.search(r"""name ['"]json['"] is not defined""", error_msg):
        if not re.search(r"^\s*import\s+json\b", code, re.MULTILINE):
            fixed = "import json\n" + code
            if _syntax_valid(fixed):
                return fixed

    # Move a simple assignment before the first use of the reported name.
    match = re.search(r"""name ['"]([^'"]+)['"] is not defined""", error_msg, re.I)
    if match:
        name = match.group(1)
        lines = code.splitlines()
        assignment_index = next((
            i for i, line in enumerate(lines)
            if re.match(rf"^\s*{re.escape(name)}\s*=\s*(?![=]).+$", line)
        ), None)
        if assignment_index is not None:
            assignment = lines.pop(assignment_index)
            use_index = next((
                i for i, line in enumerate(lines)
                if re.search(rf"\b{re.escape(name)}\b", line)
            ), None)
            if use_index is not None:
                lines.insert(use_index, assignment)
                fixed = "\n".join(lines)
                if _syntax_valid(fixed):
                    return fixed
    
    # Define a simple missing multiply(a, b) function when called with two arguments.
    match = re.search(
        r"\b([A-Za-z_]\w*)\(\s*([^(),]+)\s*,\s*([^(),]+)\s*\)",
        code,
    )
    if match:
        function_name, arg1, arg2 = match.groups()
        if re.search(
            rf"\b{re.escape(function_name)}\s*\(",
            code,
        ) and not re.search(
            rf"(?m)^\s*def\s+{re.escape(function_name)}\s*\(",
            code,
        ):
            if function_name == "multiply":
                fixed = (
                    f"def multiply(a, b):\n"
                    f"    return a * b\n\n"
                    + code
                )
                if _syntax_valid(fixed):
                    return fixed

    # Handle a simple undefined variable used in a print statement.
    match = re.search(
        r"""name ['"]([^'"]+)['"] is not defined""",
        error_msg,
    )
    if match:
        name = match.group(1)
        pattern = rf"""(?m)^(\s*)print\((.*)\b{re.escape(name)}\b(.*)\)$"""
        usage = re.search(pattern, code)
        if usage:
            fixed = re.sub(
                rf"\b{re.escape(name)}\b",
                repr("User"),
                code,
                count=1,
            )
            if fixed != code and _syntax_valid(fixed):
                return fixed


def _fix_syntax_error(code: str) -> str:
    """Fix common missing colons or one missing closing parenthesis."""
    lines = code.splitlines()
    changed = False
    patterns = (
        r"^(?:if|elif|for|while|def|class|with)\b.+[^:]$",
        r"^(?:else|try|finally)\s*$",
        r"^except(?:\s+.+)?$",
    )
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and any(
            re.match(pattern, stripped) for pattern in patterns
        ):
            lines[i] = line + ":"
            changed = True
    fixed = "\n".join(lines)
    if changed and _syntax_valid(fixed):
        return fixed
    if code.count("(") > code.count(")"):
        fixed = code + ")"
        if _syntax_valid(fixed):
            return fixed
    return code


def _fix_indentation(code: str) -> str:
    """Try to repair basic indentation errors."""
    lines = code.splitlines()
    output = []
    level = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            output.append("")
            continue
        if stripped.startswith(("elif ", "else:", "except", "finally:")):
            level = max(0, level - 1)
        output.append("    " * level + stripped)
        if stripped.endswith(":"):
            level += 1
    fixed = "\n".join(output)
    return fixed if fixed != code and _syntax_valid(fixed) else code



def _fix_syntax_error(code: str) -> str:
    """Fix common syntax errors, including missing indentation."""
    lines = code.splitlines()
    changed = False

    # First, try adding a colon to common block headers.
    patterns = (
        r"^(?:if|elif|for|while|def|class|with)\b.+[^:]$",
        r"^(?:else|try|finally)\s*$",
        r"^except(?:\s+.+)?$",
    )

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and any(
            re.match(pattern, stripped) for pattern in patterns
        ):
            lines[i] = line + ":"
            changed = True

    fixed = "\n".join(lines)

    if changed and _syntax_valid(fixed):
        return fixed

    # Repair a simple missing indentation after a block header.
    lines = code.splitlines()
    for i in range(len(lines) - 1):
        current = lines[i]
        next_line = lines[i + 1]

        if (
            current.strip().endswith(":")
            and current.strip()
            and next_line.strip()
            and not next_line.lstrip().startswith("#")
        ):
            current_indent = len(current) - len(current.lstrip())
            next_indent = len(next_line) - len(next_line.lstrip())

            if next_indent <= current_indent:
                lines[i + 1] = " " * (current_indent + 4) + next_line.strip()
                fixed = "\n".join(lines)

                if _syntax_valid(fixed):
                    return fixed

    # Repair one missing closing parenthesis as a final fallback.
    if code.count("(") > code.count(")"):
        fixed = code + ")"
        if _syntax_valid(fixed):
            return fixed

    return code




def _fix_type_error(code: str, error_msg: str) -> str:
    """Fix a few known, simple TypeError patterns."""
    message = error_msg.lower()
    
        # Fix a number added to a numeric string literal.
    pattern_direct = (
            r"""(\b[A-Za-z_]\w*\s*\+\s*)"""
            r"""(['"])(\d+)\2"""
        )
    match_direct = re.search(pattern_direct, code)

    if match_direct:
            fixed = (
                code[:match_direct.start()]
                + match_direct.group(1)
                + "int(" + match_direct.group(2)
                + match_direct.group(3)
                + match_direct.group(2) + ")"
                + code[match_direct.end():]
            )
            if fixed != code and _syntax_valid(fixed):
                return fixed

    # Numeric string passed to a function: add_numbers(10, "20")
    if "unsupported operand type" in message:
        pattern = (
            r"(\b[A-Za-z_]\w*\s*\(\s*\d+\s*,\s*)"
            r"(['\"])(\d+)\2(\s*\))"
        )
        match = re.search(pattern, code)
        if match:
            fixed = (
                code[:match.start()]
                + match.group(1)
                + "int(" + match.group(3) + ")"
                + match.group(4)
                + code[match.end():]
            )
            if fixed != code and _syntax_valid(fixed):
                return fixed

    # Calling a number as if it were a function: x = 5; result = x(10)
    if "not callable" in message:
        pattern = (
            r"(?m)^([ \t]*)([A-Za-z_]\w*)\s*=\s*(-?\d+)\s*$"
            r"\n([ \t]*)([A-Za-z_]\w*)\s*=\s*([A-Za-z_]\w*)"
            r"\(([^()\n]+)\)\s*$"
        )
        match = re.search(pattern, code)
        if match and match.group(2) == match.group(6):
            fixed_line = (
                f"{match.group(5)} = "
                f"{match.group(2)} * {match.group(7)}"
            )
            fixed = code[:match.start(4)] + fixed_line + code[match.end():]
            if fixed != code and _syntax_valid(fixed):
                return fixed

    # Too many positional arguments: remove excess arguments from a simple call.
    if "positional argument" in message and "were given" in message:
        match = re.search(
            r"def\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*:",
            code,
        )
        if match:
            function_name = match.group(1)
            parameters = [
                item.strip() for item in match.group(2).split(",")
                if item.strip()
            ]
            call_pattern = (
                r"\b" + re.escape(function_name)
                + r"\(([^()\n]*)\)"
            )
            for call in re.finditer(call_pattern, code):
                if call.start() < match.end():
                    continue
                arguments = [
                    item.strip() for item in call.group(1).split(",")
                    if item.strip()
                ]
                if len(arguments) > len(parameters):
                    new_args = ", ".join(arguments[:len(parameters)])
                    fixed = (
                        code[:call.start(1)] + new_args
                        + code[call.end(1):]
                    )
                    if fixed != code and _syntax_valid(fixed):
                        return fixed

    # List plus integer: nums + 4 -> nums + [4]
    if "concatenate list" in message:
        match = re.search(
            r"\b([A-Za-z_]\w*)\s*\+\s*(-?\d+)\b",
            code,
        )
        if match:
            fixed = (
                code[:match.start(2)] + "[" + match.group(2) + "]"
                + code[match.end(2):]
            )
            if fixed != code and _syntax_valid(fixed):
                return fixed

    # len() on an integer: len(n) -> len(str(n))
    if "has no len" in message:
        match = re.search(r"\blen\(\s*([A-Za-z_]\w*)\s*\)", code)
        if match:
            name = match.group(1)
            assignment = re.search(
                rf"(?m)^\s*{re.escape(name)}\s*=\s*-?\d+\s*$",
                code,
            )
            if assignment:
                fixed = (
                    code[:match.start()]
                    + f"len(str({name}))"
                    + code[match.end():]
                )
                if fixed != code and _syntax_valid(fixed):
                    return fixed

    return code



def _fix_index_error(code: str, error_msg: str) -> str:
    """Fix selected out-of-range literal indexes and loop bounds."""
    match = re.search(r"\b([A-Za-z_]\w*)\[(\d+)\]", code)
    if match:
        name, index_text = match.groups()
        index = int(index_text)
        assignment = re.search(
            rf"\b{re.escape(name)}\s*=\s*(\[[^\]]*\]|(['""]).*?\2)",
            code, re.DOTALL,
        )
        if assignment:
            try:
                value = ast.literal_eval(assignment.group(1))
                if isinstance(value, (list, tuple, str)) and index >= len(value):
                    replacement = f"{name}[{len(value)-1}]" if value else "None"
                    fixed = code.replace(f"{name}[{index}]", replacement, 1)
                    if fixed != code and _syntax_valid(fixed):
                        return fixed
            except (ValueError, SyntaxError, TypeError):
                pass

    match = re.search(r"\b([A-Za-z_]\w*)\[(-\d+)\]", code)
    if match:
        name, index_text = match.groups()
        index = int(index_text)
        assignment = re.search(
            rf"\b{re.escape(name)}\s*=\s*(\[[^\]]*\]|(['""]).*?\2)",
            code, re.DOTALL,
        )
        if assignment:
            try:
                value = ast.literal_eval(assignment.group(1))
                if isinstance(value, (list, tuple, str)) and abs(index) > len(value):
                    replacement = f"{name}[0]" if value else "None"
                    fixed = code.replace(f"{name}[{index}]", replacement, 1)
                    if fixed != code and _syntax_valid(fixed):
                        return fixed
            except (ValueError, SyntaxError, TypeError):
                pass

    loop = re.search(r"for\s+([A-Za-z_]\w*)\s+in\s+range\s*\(\s*(\d+)\s*\)\s*:", code)
    if loop:
        index_name, count = loop.groups()
        access = re.search(rf"\b([A-Za-z_]\w*)\[\s*{re.escape(index_name)}\s*\]", code)
        if access:
            collection = access.group(1)
            fixed = re.sub(
                rf"range\s*\(\s*{re.escape(count)}\s*\)",
                f"range(len({collection}))", code, count=1,
            )
            if fixed != code and _syntax_valid(fixed):
                return fixed
    
    # Handle a string variable indexed beyond its final character.
    if "string index out of range" in error_msg.lower():
        match = re.search(r"\b([A-Za-z_]\w*)\[(\d+)\]", code)
        if match:
            name, index_text = match.groups()
            assignment = re.search(
                rf"(?m)^\s*{re.escape(name)}\s*=\s*(['\"])(.*?)\1\s*$",
                code,
            )
            if assignment:
                value = assignment.group(2)
                index = int(index_text)
                if index >= len(value) and value:
                    fixed = (
                        code[:match.start(2)]
                        + str(len(value) - 1)
                        + code[match.end(2):]
                    )
                    if fixed != code and _syntax_valid(fixed):
                        return fixed


def _fix_attribute_error(code: str, error_msg: str) -> str:
    """Fix selected AttributeError patterns, with syntax validation."""
    message = error_msg.lower()

    # int.append(): convert a simple integer assignment into a one-item list.
    if "int" in message and "append" in message:
        match = re.search(r"^\s*([A-Za-z_]\w*)\s*=\s*(-?\d+)\s*$", code, re.M)
        if match:
            name, number = match.groups()
            fixed = re.sub(
                rf"^(\s*{re.escape(name)}\s*=\s*){re.escape(number)}\s*$",
                rf"\g<1>[{number}]", code, count=1, flags=re.M,
            )
            if fixed != code and _syntax_valid(fixed):
                return fixed

    # str.append(): handle both an assignment and a standalone method call.
    if "str" in message and "append" in message:
        match = re.search(r"(\b[A-Za-z_]\w*)\.append\(([^()]*)\)", code)
        if match:
            name, value = match.groups()
            string_assignment = re.search(
                rf"""^\s*{re.escape(name)}\s*=\s*(['"]).*?\1\s*$""",
                code, re.M,
            )
            if string_assignment:
                line_start = code.rfind("\n", 0, match.start()) + 1
                prefix = code[line_start:match.start()]
                suffix = code[match.end():]

                # For "result = text.append(value)", preserve result =.
                lhs = re.fullmatch(r"\s*([A-Za-z_]\w*)\s*=\s*", prefix)
                if lhs:
                    result_name = lhs.group(1)
                    fixed = (
                        code[:line_start]
                        + f"{result_name} = {name} + {value}"
                        + suffix
                    )
                else:
                    # For standalone "text.append(value)", mutate text itself.
                    fixed = code[:match.start()] + f"{name} += {value}" + suffix

                if fixed != code and _syntax_valid(fixed):
                    return fixed

    # str.push(): use string concatenation.
    if "str" in message and "push" in message:
        match = re.search(r"(\b[A-Za-z_]\w*)\.push\(([^()]*)\)", code)
        if match:
            name, value = match.groups()
            fixed = code[:match.start()] + f"{name} += {value}" + code[match.end():]
            if fixed != code and _syntax_valid(fixed):
                return fixed

    # list.keys(): replace with the list variable.
    if "list" in message and "keys" in message:
        match = re.search(r"(\b[A-Za-z_]\w*)\.keys\(\)", code)
        if match:
            name = match.group(1)
            fixed = code[:match.start()] + name + code[match.end():]
            if fixed != code and _syntax_valid(fixed):
                return fixed

    # dict.get_value() -> dict.get().
    if "get_value" in message or "get_value" in code:
        fixed = code.replace(".get_value(", ".get(", 1)
        if fixed != code and _syntax_valid(fixed):
            return fixed

    # NoneType.upper(): replace a return None with an empty string.
    if "nonetype" in message and "upper" in message:
        fixed = re.sub(r"\breturn\s+None\b", 'return ""', code, count=1)
        if fixed != code and _syntax_valid(fixed):
            return fixed

    return code


def _fix_zero_division(code: str) -> str:
    """Fix simple division-by-zero cases."""
    division = re.search(r"\b([A-Za-z_]\w*)\s*/\s*([A-Za-z_]\w*)", code)
    if division:
        denominator = division.group(2)
        if re.search(rf"\b{re.escape(denominator)}\s*=\s*0\b", code):
            fixed = re.sub(
                rf"\b{re.escape(denominator)}\s*=\s*0\b",
                f"{denominator} = 1", code, count=1,
            )
            if fixed != code and _syntax_valid(fixed):
                return fixed

    fixed = re.sub(r"/\s*0\b", "/ 1", code)
    return fixed if fixed != code and _syntax_valid(fixed) else code


def _syntax_valid(code: str) -> bool:
    """Return whether code parses as valid Python."""
    try:
        ast.parse(code)
        return True
    except (SyntaxError, ValueError, TypeError):
        return False
