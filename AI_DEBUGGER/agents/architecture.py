"""
Agent 6 - Architecture Reporter
Generates a human-readable architecture report and a matplotlib complexity chart.
"""
import ast
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — required for Streamlit
import matplotlib.pyplot as plt
import io


def _count_complexity(code: str) -> dict[str, int]:
    """Count branches (if/for/while/try) per function as a proxy for cyclomatic complexity."""
    complexity: dict[str, int] = {}
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return complexity

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            count = sum(
                1 for child in ast.walk(node)
                if isinstance(child, ast.If | ast.For | ast.While | ast.ExceptHandler)
            )
            complexity[node.name] = count + 1  # +1 for the function entry point
    return complexity


def generate_report(analysis: dict, code: str) -> dict:
    """
    Parameters:
        analysis: output from analyzer.analyze_code()
        code: original source string

    Returns:
        {
            "report_text": str,
            "chart_bytes": bytes | None   # PNG bytes of complexity bar chart
        }
    """
    lines = [
        "## Code Architecture Report",
        f"- **Total lines:** {analysis['total_lines']}",
        f"- **Functions defined:** {len(analysis['functions'])}  →  {', '.join(analysis['functions']) or 'none'}",
        f"- **Classes defined:** {len(analysis['classes'])}  →  {', '.join(analysis['classes']) or 'none'}",
        f"- **Imports used:** {len(analysis['imports'])}  →  {', '.join(analysis['imports']) or 'none'}",
        f"- **Module-level variables:** {len(analysis['variables'])}  →  {', '.join(analysis['variables']) or 'none'}",
    ]

    complexity = _count_complexity(code)
    if complexity:
        lines.append("\n### Cyclomatic Complexity (per function)")
        for fn, score in complexity.items():
            rating = "🟢 Low" if score <= 3 else ("🟡 Medium" if score <= 7 else "🔴 High")
            lines.append(f"- `{fn}`: {score}  {rating}")

    report_text = "\n".join(lines)

    # ── Bar chart ────────────────────────────────────────────────────────────
    chart_bytes = None
    if complexity:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.bar(complexity.keys(), complexity.values(), color="#4C72B0")
        ax.set_xlabel("Function")
        ax.set_ylabel("Complexity Score")
        ax.set_title("Cyclomatic Complexity per Function")
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100)
        plt.close(fig)
        chart_bytes = buf.getvalue()

    return {"report_text": report_text, "chart_bytes": chart_bytes}
