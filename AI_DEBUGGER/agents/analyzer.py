"""
Agent 2 - Code Analyzer
Walks the AST to extract structural information about the code.
"""
import ast


def analyze_code(code: str) -> dict:
    """
    Returns:
        {
            "functions": [str],
            "classes": [str],
            "imports": [str],
            "variables": [str],
            "total_lines": int,
            "parse_ok": bool
        }
    """
    result = {
        "functions": [],
        "classes": [],
        "imports": [],
        "variables": [],
        "total_lines": len(code.splitlines()),
        "parse_ok": False,
    }

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return result  # Can't walk a broken tree

    result["parse_ok"] = True

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            result["functions"].append(node.name)
        elif isinstance(node, ast.ClassDef):
            result["classes"].append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                result["imports"].append(f"{module}.{alias.name}")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    result["variables"].append(target.id)

    # Deduplicate while preserving order
    for key in ("functions", "classes", "imports", "variables"):
        result[key] = list(dict.fromkeys(result[key]))

    return result
