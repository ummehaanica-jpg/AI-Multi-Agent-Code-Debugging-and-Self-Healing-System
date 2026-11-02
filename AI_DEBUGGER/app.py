"""
AI Multi-Agent Code Debugging and Self-Healing System
Main Streamlit application — orchestrates all six agents.
"""
import time
import streamlit as st

from agents.error_detector import detect_errors
from agents.analyzer import analyze_code
from agents.fixer import fix_code
from agents.validator import validate_code
from agents.explainer import explain_error
from agents.architecture import generate_report

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Code Debugger",
    page_icon="🤖",
    layout="wide",
)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🤖 AI Multi-Agent Code Debugging & Self-Healing System")
st.markdown(
    """
    **VTU B.E. AI&ML — Major Project Phase II**  
    Paste buggy Python code below. Six AI agents will detect, analyze, fix, validate, explain, and report.
    """
)
st.divider()

# ── Sidebar: optional OpenAI key ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("OpenAI API Key (optional)", type="password")
    if api_key:
        import os
        os.environ["OPENAI_API_KEY"] = api_key
        st.success("API key set ✅")
    else:
        st.info("Running in rule-based mode (no API key)")

    st.markdown("---")
    st.markdown("**Max retry attempts**")
    max_retries = st.slider("Retries if validation fails", 1, 3, 2)

# ── Code input ────────────────────────────────────────────────────────────────
st.subheader("📝 Input: Buggy Python Code")
default_code = '''\
# Example buggy code — try editing this!
def greet(name)
    print("Hello, " + name)

greet("Alice")
'''
user_code = st.text_area("Paste your Python code here:", value=default_code, height=220)

run_btn = st.button("🚀 Debug My Code", type="primary", use_container_width=True)

# ── Pipeline ──────────────────────────────────────────────────────────────────
if run_btn and user_code.strip():
    st.divider()

    # ── Agent 1: Error Detection ──────────────────────────────────────────────
    with st.expander("🔍 Agent 1 — Error Detection", expanded=True):
        t0 = time.perf_counter()
        detection = detect_errors(user_code)
        t1 = time.perf_counter()

        if detection["has_error"]:
            st.error(f"**{detection['error_type']}** detected")
            st.code(detection["error_msg"], language="text")
            if detection["line_no"]:
                st.write(f"📍 Line number: **{detection['line_no']}**")
        else:
            st.success("No errors detected in the original code.")
        st.caption(f"⏱ Detection time: {(t1 - t0)*1000:.1f} ms")

    # ── Agent 2: Code Analysis ────────────────────────────────────────────────
    with st.expander("🧠 Agent 2 — Code Analysis", expanded=True):
        analysis = analyze_code(user_code)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Functions", len(analysis["functions"]))
        col2.metric("Classes", len(analysis["classes"]))
        col3.metric("Imports", len(analysis["imports"]))
        col4.metric("Variables", len(analysis["variables"]))
        st.json(analysis)

    # ── Agent 3: Fix ──────────────────────────────────────────────────────────
    with st.expander("🔧 Agent 3 — Fix Agent", expanded=True):
        current_code = user_code
        fix_result = {"fixed_code": user_code, "method": "unchanged", "applied_rule": "none"}

        if detection["has_error"]:
            for attempt in range(1, max_retries + 1):
                fix_result = fix_code(
                    current_code,
                    detection["error_type"],
                    detection["error_msg"],
                )
                current_code = fix_result["fixed_code"]
                st.write(f"**Attempt {attempt}** — method: `{fix_result['method']}`")

                # Re-detect after fix to decide if we should retry
                re_detect = detect_errors(current_code)
                if not re_detect["has_error"]:
                    st.success("Error resolved after fix ✅")
                    break
                else:
                    detection = re_detect  # Update for next retry
        else:
            st.info("No fix needed.")

        st.subheader("Fixed Code")
        st.code(fix_result["fixed_code"], language="python")

    # ── Agent 4: Validation ───────────────────────────────────────────────────
    with st.expander("✅ Agent 4 — Validation", expanded=True):
        t0 = time.perf_counter()
        validation = validate_code(fix_result["fixed_code"])
        t1 = time.perf_counter()

        if validation["success"]:
            st.success("Code executed successfully ✅")
        elif validation["timed_out"]:
            st.warning("⏰ Execution timed out")
        else:
            st.error("Code still has errors after fix ❌")

        if validation["stdout"]:
            st.subheader("Program Output")
            st.code(validation["stdout"], language="text")
        if validation["stderr"]:
            st.subheader("Error Output")
            st.code(validation["stderr"], language="text")
        st.caption(f"⏱ Execution time: {(t1 - t0)*1000:.1f} ms")

    # ── Agent 5: Explanation ──────────────────────────────────────────────────
    with st.expander("💬 Agent 5 — Plain-English Explanation", expanded=True):
        if detection["has_error"]:
            explanation = explain_error(
                detection["error_type"],
                detection["error_msg"],
                detection["line_no"],
                user_code,
            )
            st.markdown(explanation["explanation"])
            st.caption(f"Source: {explanation['source']}")
        else:
            st.info("No error to explain.")

    # ── Agent 6: Architecture Report ──────────────────────────────────────────
    with st.expander("📊 Agent 6 — Architecture Report", expanded=True):
        report = generate_report(analysis, fix_result["fixed_code"])
        st.markdown(report["report_text"])
        if report["chart_bytes"]:
            st.image(report["chart_bytes"], caption="Cyclomatic Complexity Chart")

elif run_btn:
    st.warning("Please enter some Python code first.")
