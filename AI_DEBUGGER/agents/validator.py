"""
Agent 4 - Validator
Writes fixed code to a temp file and runs it in a subprocess with a timeout.
"""
import subprocess
import sys
import tempfile
import os


def validate_code(code: str, timeout: int = 10) -> dict:
    """
    Returns:
        {
            "success": bool,
            "stdout": str,
            "stderr": str,
            "returncode": int,
            "timed_out": bool
        }
    """
    # Write to a real temp file so subprocess can import it cleanly
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        proc = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "success": proc.returncode == 0,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "returncode": proc.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Execution timed out after {timeout}s",
            "returncode": -1,
            "timed_out": True,
        }
    finally:
        os.unlink(tmp_path)  # Always clean up
