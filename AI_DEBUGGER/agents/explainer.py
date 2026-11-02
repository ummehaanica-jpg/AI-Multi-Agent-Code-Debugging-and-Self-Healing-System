
"""
Agent 5 - Explainer
Converts technical error information into beginner-friendly English.
Uses OpenAI if available, otherwise uses local explanation templates.
"""

import os


# ============================================================
# LOCAL EXPLANATION TEMPLATES
# ============================================================

_TEMPLATES = {
    "SyntaxError": (
        "Your code has a **syntax error** — Python cannot even read it. "
        "This usually means a missing colon `:`, mismatched brackets "
        "`()[]{}`, or a typo in a keyword like `def` or `if`."
    ),
    "NameError": (
        "Python found a **name that doesn't exist**. "
        "You used a variable or function that was never defined. "
        "Check your spelling and make sure you assigned the variable "
        "before using it."
    ),
    "UnboundLocalError": (
        "You tried to use a **local variable before assigning it**. "
        "If you meant to use a global variable, consider whether "
        "you need to declare it with `global` inside the function."
    ),
    "TypeError": (
        "You mixed **incompatible data types**. "
        "For example, you cannot add a string and a number directly. "
        "Use `str()` or `int()` to convert values when appropriate."
    ),
    "IndexError": (
        "You tried to access a **list or string position that doesn't exist**. "
        "Remember: Python indices start at 0. "
        "Check the sequence length before accessing an index."
    ),
    "AttributeError": (
        "You called a **method or property that doesn't exist** on that object. "
        "Check the object's type and verify that the attribute name "
        "is correct."
    ),
    "ZeroDivisionError": (
        "Your code tried to **divide a number by zero**, which is undefined. "
        "Check that the denominator is not zero before dividing."
    ),
    "ImportError": (
        "Python could not **find or load a module or imported name**. "
        "Check the module name and whether the required package is installed."
    ),
    "ModuleNotFoundError": (
        "Python could not find the requested module. "
        "Check the spelling and install the required package if necessary."
    ),
    "KeyError": (
        "You tried to access a **dictionary key that doesn't exist**. "
        "Use `dict.get(key)` to retrieve a value safely, or check "
        "whether the key exists first."
    ),
    "ValueError": (
        "A function received an **argument of the right type but wrong value**. "
        "For example, `int('abc')` fails because 'abc' cannot be "
        "converted to an integer."
    ),
    "FileNotFoundError": (
        "Python could not find the requested file. "
        "Check the file path, filename, and current working directory."
    ),
    "IndentationError": (
        "Your code has an indentation problem. "
        "Check that statements inside functions, loops, and conditions "
        "are consistently indented."
    ),
}

_DEFAULT = (
    "An unexpected error occurred. Read the error message carefully. "
    "It often identifies the error type, location, and what went wrong."
)


# ============================================================
# LOCAL EXPLANATION
# ============================================================

def _local_explain(
    error_type: str,
    error_msg: str,
    line_no=None,
) -> str:
    """Create a beginner-friendly explanation using local templates."""

    base = _TEMPLATES.get(error_type, _DEFAULT)

    detail = (
        f"\n\n**Technical detail:** `{error_type}: {error_msg}`"
    )

    line_info = (
        f"\n**Detected at line:** {line_no}"
        if line_no is not None
        else ""
    )

    return base + detail + line_info


# ============================================================
# OPTIONAL OPENAI EXPLANATION
# ============================================================

def _openai_explain(
    error_type: str,
    error_msg: str,
    code: str,
) -> str | None:
    """Generate an explanation using OpenAI when an API key is available."""

    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        prompt = (
            "Explain this Python error to a beginner in 3-4 sentences. "
            "Be friendly, clear, and practical. Explain the likely cause "
            "and suggest a safe correction. Do not claim the code was "
            "tested unless it actually was.\n\n"
            f"Error: {error_type}: {error_msg}\n\n"
            f"Code:\n{code}"
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )

        content = response.choices[0].message.content

        if content:
            return content.strip()

    except Exception:
        # Fall back to local templates if the API is unavailable.
        return None

    return None


# ============================================================
# PUBLIC API 1 - EXISTING EXPLAINER FUNCTION
# ============================================================

def explain_error(
    error_type: str,
    error_msg: str,
    line_no=None,
    code: str = "",
) -> dict:
    """
    Explain an error using OpenAI or local templates.

    Returns:
        {
            "explanation": str,
            "source": "openai" or "template"
        }
    """

    gpt_text = _openai_explain(
        error_type=error_type,
        error_msg=error_msg,
        code=code,
    )

    if gpt_text:
        return {
            "explanation": gpt_text,
            "source": "openai",
        }

    return {
        "explanation": _local_explain(
            error_type=error_type,
            error_msg=error_msg,
            line_no=line_no,
        ),
        "source": "template",
    }


# ============================================================
# PUBLIC API 2 - ORCHESTRATOR-COMPATIBLE EXPLAINER
# ============================================================

def explain_debugging(
    original_code: str,
    final_code: str,
    detection: dict,
    analysis: dict,
    classification: dict,
    repair_attempts: list,
    validation: dict = None,
) -> dict:
    """
    Provide an explanation using the arguments supplied by the orchestrator.

    Keeps the existing explain_error() implementation and adds the
    pipeline context to the returned dictionary.
    """

    detection = detection or {}
    analysis = analysis or {}
    classification = classification or {}
    repair_attempts = repair_attempts or []

    error_type = detection.get("error_type", "UnknownError")
    error_msg = detection.get(
        "error_msg",
        detection.get("error_message", ""),
    )
    line_no = detection.get(
        "line_no",
        detection.get("error_line"),
    )

    explanation_result = explain_error(
        error_type=error_type,
        error_msg=error_msg,
        line_no=line_no,
        code=original_code or "",
    )

    successful_attempts = [
        attempt
        for attempt in repair_attempts
        if isinstance(attempt, dict)
        and attempt.get("passed", False)
    ]

    explanation_result.update({
        "original_code": original_code,
        "final_code": final_code,
        "analysis": analysis,
        "classification": classification,
        "repair_attempts": repair_attempts,
        "repair_success": bool(successful_attempts),
        "validation": validation or {},
    })

    return explanation_result

def explain_debugging(
    original_code: str,
    final_code: str,
    detection: dict,
    analysis: dict,
    classification: dict,
    repair_attempts: list,
    validation: dict = None,
) -> dict:
    """Provide an explanation compatible with the debugging orchestrator."""

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