"""
Agent 5 - Explainer
Converts technical error info into beginner-friendly English.
Uses OpenAI if available, otherwise uses a local template library.
"""
import os
import re


# â”€â”€ Local explanation templates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_TEMPLATES = {
    "SyntaxError": (
        "Your code has a **syntax error** â€” Python cannot even read it. "
        "This usually means a missing colon `:`, mismatched brackets `()[]{}`, "
        "or a typo in a keyword like `def` or `if`."
    ),
    "NameError": (
        "Python found a **name that doesn't exist**. "
        "You used a variable or function that was never defined. "
        "Check your spelling and make sure you assigned the variable before using it."
    ),
    "UnboundLocalError": (
        "You tried to use a **local variable before assigning it**. "
        "If you meant to use a global variable, add `global <varname>` inside the function."
    ),
    "TypeError": (
        "You mixed **incompatible data types**. "
        "For example, you cannot add a string and a number directly. "
        "Use `str()` or `int()` to convert values first."
    ),
    "IndexError": (
        "You tried to access a **list position that doesn't exist**. "
        "Remember: Python lists start at index 0. "
        "If your list has 3 items, valid indices are 0, 1, and 2."
    ),
    "AttributeError": (
        "You called a **method or property that doesn't exist** on that object. "
        "Check the object's type and verify the attribute name is spelled correctly."
    ),
    "ZeroDivisionError": (
        "Your code tried to **divide a number by zero**, which is mathematically undefined. "
        "Add a check: `if denominator != 0:` before dividing."
    ),
    "ImportError": (
        "Python could not **find or load a module**. "
        "Make sure the package is installed (`pip install <package>`) "
        "and the module name is spelled correctly."
    ),
    "KeyError": (
        "You tried to access a **dictionary key that doesn't exist**. "
        "Use `dict.get(key)` to safely retrieve values, or check with `if key in dict:`."
    ),
    "ValueError": (
        "A function received an **argument of the right type but wrong value**. "
        "For example, `int('abc')` fails because 'abc' cannot be converted to an integer."
    ),
}

_DEFAULT = (
    "An unexpected error occurred. Read the error message carefully â€” "
    "it usually tells you the file name, line number, and what went wrong."
)


def _local_explain(error_type: str, error_msg: str, line_no) -> str:
    base = _TEMPLATES.get(error_type, _DEFAULT)
    detail = f"\n\n**Technical detail:** `{error_type}: {error_msg}`"
    line_info = f"\n**Detected at line:** {line_no}" if line_no else ""
    return base + detail + line_info


def _openai_explain(error_type: str, error_msg: str, code: str) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = (
            f"Explain this Python error to a beginner in 3-4 sentences. "
            f"Be friendly and practical.\n\n"
            f"Error: {error_type}: {error_msg}\n\nCode:\n{code}"
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return resp.choices[0].message.content
    except Exception:
        return None


# â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def explain_error(error_type: str, error_msg: str, line_no, code: str = "") -> dict:
    """
    Returns:
        {
            "explanation": str (markdown),
            "source": "openai" | "template"
        }
    """
    gpt_text = _openai_explain(error_type, error_msg, code)
    if gpt_text:
        return {"explanation": gpt_text, "source": "openai"}
    return {
        "explanation": _local_explain(error_type, error_msg, line_no),
        "source": "template",
    }


def explain_debugging(
    original_code: str,
    final_code: str,
    detection: dict,
    analysis: dict,
    classification: dict,
    repair_attempts: list,
    validation: dict = None,
) -> dict:
    """Generate an explanation compatible with the debugging pipeline."""

    detection = detection or {}

    result = explain_error(
        error_type=detection.get("error_type", "UnknownError"),
        error_msg=detection.get(
            "error_msg",
            detection.get("error_message", ""),
        ),
        line_no=detection.get(
            "line_no",
            detection.get("error_line"),
        ),
        code=original_code or "",
    )

    result.update({
        "original_code": original_code,
        "final_code": final_code,
        "analysis": analysis or {},
        "classification": classification or {},
        "repair_attempts": repair_attempts or [],
        "validation": validation or {},
    })

    return result


