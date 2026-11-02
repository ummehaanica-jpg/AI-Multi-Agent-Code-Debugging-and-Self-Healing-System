"""
AI Multi-Agent Code Debugging and Self-Healing System
Main Streamlit application — orchestrates all six agents.
"""
import time
import streamlit as st

from core.orchestrator import run_pipeline

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
    Paste buggy Python code below. A multi-agent pipeline will detect, analyze, classify, repair, test, validate, explain, and evaluate your code.
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

    with st.spinner("Running Multi-Agent Pipeline..."):
        state = run_pipeline(
            code=user_code,
            max_retries=max_retries,
            timeout=5
        )
        st.divider()

    # ── Pipeline Summary ─────────────────────────────────────────────────
    st.subheader("📋 Debugging Summary")

    detection = state.detection
    classification = state.classification

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Bug Type",
        classification.get("category", "Unknown")
    )

    col2.metric(
        "Severity",
        classification.get("severity", "Unknown")
    )

    col3.metric(
        "Confidence",
        f"{classification.get('confidence', 0) * 100:.0f}%"
    )

    col4.metric(
        "Repair Attempts",
        state.total_attempts
    )

    # ── Agent 1: Error Detection ─────────────────────────────────────────
    with st.expander("🔍 Agent 1 — Error Detection", expanded=True):

        if detection.get("has_error"):
            st.error(
                f"**{detection.get('error_type', 'Unknown Error')}** detected"
            )

            st.code(
                detection.get("error_msg", ""),
                language="text"
            )

            if detection.get("line_no"):
                st.write(
                    f"📍 Line number: **{detection['line_no']}**"
                )

            st.write(
                f"**Phase:** {detection.get('phase', 'unknown')}"
            )

        else:
            st.success("No errors detected in the original code. ✅")

    # ── Agent 2: Code Analysis ───────────────────────────────────────────
    with st.expander("🧠 Agent 2 — Code Analysis"):

        analysis = state.analysis

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Functions",
            len(analysis.get("functions", []))
        )

        col2.metric(
            "Classes",
            len(analysis.get("classes", []))
        )

        col3.metric(
            "Imports",
            len(analysis.get("imports", []))
        )

        col4.metric(
            "Variables",
            len(analysis.get("variables", []))
        )

        st.json(analysis)

    # ── Agent 3: Bug Classification ──────────────────────────────────────
    with st.expander("🏷️ Agent 3 — Bug Classification"):

        st.write(
            f"**Category:** {classification.get('category', 'Unknown')}"
        )

        st.write(
            f"**Severity:** {classification.get('severity', 'Unknown')}"
        )

        st.write(
            f"**Confidence:** "
            f"{classification.get('confidence', 0) * 100:.1f}%"
        )

        st.write(
            f"**Reason:** "
            f"{classification.get('reason', 'Not available')}"
        )

        st.write(
            f"**Fixable:** "
            f"{classification.get('is_fixable', False)}"
        )

    # ── Agent 4: Knowledge Base ──────────────────────────────────────────
    with st.expander("🧠 Agent 4 — Knowledge Base"):

        if state.kb_matches:
            st.write(
                f"Found **{len(state.kb_matches)}** previous validated repairs."
            )

            for i, match in enumerate(state.kb_matches, 1):
                st.write(
                    f"**Match {i}:** "
                    f"{match.get('repair_strategy', 'Unknown strategy')}"
                )
        else:
            st.info("No previous validated repair found in knowledge base.")

    # ── Agent 5: Fix Agent ───────────────────────────────────────────────
    with st.expander("🔧 Agent 5 — Fix Agent", expanded=True):

        if state.repair_attempts:

            for attempt in state.repair_attempts:

                status = "✅ Passed" if attempt.passed else "❌ Failed"

                st.write(
                    f"**Attempt {attempt.attempt_number}** — "
                    f"{status}"
                )

                st.write(
                    f"Strategy: `{attempt.strategy}`"
                )

                st.write(
                    f"Confidence: "
                    f"{attempt.confidence * 100:.1f}%"
                )

                if attempt.description:
                    st.write(attempt.description)

                st.divider()

        else:
            st.info("No repair attempt was required.")

    # ── Agent 6: Test Generator ──────────────────────────────────────────
    with st.expander("🧪 Agent 6 — Test Generator"):

        tests = state.generated_tests

        if tests:
            st.write(
                tests.get(
                    "summary",
                    "Tests generated by the Test Generator."
                )
            )

            if tests.get("test_code"):
                st.code(
                    tests["test_code"],
                    language="python"
                )
        else:
            st.info("No tests were generated.")

    # ── Agent 7: Validator ───────────────────────────────────────────────
    with st.expander("✅ Agent 7 — Validator", expanded=True):

        validation = state.validation

        if validation.get("valid"):
            st.success("Final repaired code passed validation. ✅")
        else:
            st.error("Final code did not pass validation. ❌")

        if validation.get("validation_summary"):
            st.write(
                validation["validation_summary"]
            )

        if validation.get("stdout"):
            st.subheader("Program Output")
            st.code(
                validation["stdout"],
                language="text"
            )

        if validation.get("stderr"):
            st.subheader("Error Output")
            st.code(
                validation["stderr"],
                language="text"
            )

    # ── Final Repaired Code ───────────────────────────────────────────────
    st.subheader("✨ Final Code")

    
    if state.validation.get("valid"):
     if state.repair_succeeded:
        st.success("Self-healing successful! 🎉")
     else:
        st.success("Code is valid! No repair was required. ✅")
    else:
        st.warning(
        "The system could not produce a validated repair."
    )


    st.code(
        state.final_code,
        language="python"
    )

    # ── Agent 8: Explanation ─────────────────────────────────────────────
    with st.expander("💬 Agent 8 — Explanation"):

        if state.explanation:

            st.markdown(
                state.explanation.get(
                    "explanation",
                    "Explanation not available."
                )
            )

            if state.explanation.get("source"):
                st.caption(
                    f"Source: {state.explanation['source']}"
                )

        else:
            st.info("Explanation not available.")

    # ── Agent 9: Code Quality / Architecture ─────────────────────────────
    with st.expander("📊 Agent 9 — Code Quality Report"):

        if state.quality_report:
            st.json(state.quality_report)
        else:
            st.info("Quality report not available.")

    # ── Pipeline Logs ────────────────────────────────────────────────────
    with st.expander("📜 Multi-Agent Pipeline Logs"):

        for log in state.pipeline_log:
            st.text(log)

    # ── Performance ──────────────────────────────────────────────────────
    with st.expander("⏱️ Agent Performance"):

        st.json(state.agent_timings)

        st.write(
            f"**Total Pipeline Time:** "
            f"{state.total_time:.3f} seconds"
        )

elif run_btn:
    st.warning("Please enter some Python code first.")