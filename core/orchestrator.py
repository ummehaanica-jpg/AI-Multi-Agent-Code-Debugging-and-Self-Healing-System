"""
Multi-Agent Debugging Orchestrator

Pipeline:

Error Detection
      ↓
Code Analysis
      ↓
Bug Classification
      ↓
Knowledge Base
      ↓
Fixer
      ↓
Validator
      ↓
Feedback
      ↓
Fixer Retry
      ↓
Explanation
      ↓
Code Quality
      ↓
Knowledge Base Storage
"""

from __future__ import annotations

import time
from typing import Any

from core.state import DebugState, RepairAttempt


def run_pipeline(
    code: str,
    max_retries: int = 3,
    timeout: int = 5,
    use_llm: bool = False,
) -> DebugState:

    # ============================================================
    # INITIAL STATE
    # ============================================================

    state = DebugState(
        original_code=code,
        current_code=code,
        working_code=code,
        max_retries=max_retries,
    )

    state.pipeline_start = time.time()

    # ============================================================
    # 1. ERROR DETECTION
    # ============================================================

    state.log("Starting debugging pipeline.")

    try:
        from agents.error_detector import detect_errors

        detection = detect_errors(
            code=code,
            timeout=timeout,
        )

        state.detection = detection

        state.log("Error detection completed.")

    except Exception as exc:

        state.error = f"Error detector failed: {exc}"

        state.log(state.error)

        state.pipeline_end = time.time()

        return state

    # ============================================================
    # NO ERROR
    # ============================================================

    if not detection.get("has_error", False):

     state.log("No errors detected in the original code.")

     state.current_code = code
     state.working_code = code
     state.repair_succeeded = False
 
     state.validation = {
        "valid": True,
        "success": True,
        "syntax_valid": True,
        "execution_success": True,
        "tests_passed": True,
        "error_type": "",
        "error_message": "",
        "stdout": "",
        "stderr": "",
        "test_stdout": "",
        "test_stderr": "",
        "timed_out": False,
        "validation_summary": (
            "PASS: No errors detected. Original code preserved; "
            "no repair was required."
        ),
    }

     state.log(
        "Original code preserved. No repair was required."
    )

     state.pipeline_end = time.time()

     return state

    # ============================================================
    # 2. CODE ANALYSIS
    # ============================================================

    try:
        from agents.analyzer import analyze_code

        state.analysis = analyze_code(
            code=code,
            error_type=detection.get("error_type", ""),
            error_msg=detection.get("error_msg", ""),
            error_line=detection.get("line_no"),
        )

        state.log("Code analysis completed.")

    except Exception as exc:

        state.analysis = {}

        state.log(
            f"Code analysis failed: {exc}"
        )

    # ============================================================
    # 3. BUG CLASSIFICATION
    # ============================================================

    try:
        from agents.bug_classifier import classify_bug

        state.classification = classify_bug(
            error_type=detection.get("error_type", ""),
            error_msg=detection.get("error_msg", ""),
            analysis=state.analysis,
            code=code,
        )

        state.log("Bug classification completed.")

    except Exception as exc:

        state.classification = {}

        state.log(
            f"Bug classification failed: {exc}"
        )

    # ============================================================
    # 4. KNOWLEDGE BASE SEARCH
    # ============================================================

    try:
        from knowledge.knowledge_base import KnowledgeBase

        kb = KnowledgeBase()

        state.kb_matches = kb.search(
            error_type=detection.get("error_type", ""),
            error_msg=detection.get("error_msg", ""),
        )

        state.log(
            f"Knowledge base search completed. "
            f"Matches: {len(state.kb_matches)}"
        )

    except Exception as exc:

        state.kb_matches = []

        state.log(
            f"Knowledge base search skipped: {exc}"
        )

    # ============================================================
    # 5. TEST GENERATION
    # ============================================================

    try:
        from agents.test_generator import generate_tests

        state.generated_tests = generate_tests(
            code=code,
            error_type=detection.get("error_type", ""),
            error_msg=detection.get("error_msg", ""),
            analysis=state.analysis,
        )

        state.log("Test generation completed.")

    except Exception as exc:

        state.generated_tests = {}

        state.log(
            f"Test generation skipped: {exc}"
        )

    # ============================================================
    # 6. SELF-HEALING RETRY LOOP
    # ============================================================

    state.log(
        f"Starting self-healing loop. "
        f"Maximum attempts: {max_retries}"
    )

    validator_feedback: dict[str, Any] = {}

    previous_fixed_code = ""

    for attempt_number in range(
        1,
        max_retries + 1,
    ):

        state.total_attempts = attempt_number

        state.log(
            f"Starting repair attempt "
            f"{attempt_number}/{max_retries}."
        )

        # --------------------------------------------------------
        # Determine error for this attempt
        # --------------------------------------------------------

        if attempt_number == 1:

            error_type = detection.get(
                "error_type",
                "",
            )

            error_msg = detection.get(
                "error_msg",
                "",
            )

        else:

            error_type = (
                validator_feedback.get(
                    "validation_error_type",
                    "",
                )
                or detection.get(
                    "error_type",
                    "",
                )
            )

            error_msg = (
                validator_feedback.get(
                    "validation_error_message",
                    "",
                )
                or detection.get(
                    "error_msg",
                    "",
                )
            )

        state.log(
            f"Fixer error type: {error_type}"
        )

        state.log(
            f"Fixer error message: {error_msg}"
        )

        # ========================================================
        # 6A. FIXER
        # ========================================================

        try:
            from agents.fixer import fix_code

            fix_result = fix_code(
                code=state.working_code,
                error_type=error_type,
                error_msg=error_msg,
                analysis=state.analysis,
                validator_feedback=(
                    validator_feedback
                    if attempt_number > 1
                    else None
                ),
                attempt_number=attempt_number,
                kb_matches=state.kb_matches,
            )

        except Exception as exc:

            state.log(
                f"Fixer failed: {exc}"
            )

            break

        # ========================================================
        # 6B. GET FIXED CODE
        # ========================================================

        fixed_code = fix_result.get(
            "fixed_code",
            state.working_code,
        )

        strategy = fix_result.get(
            "strategy",
            "unknown",
        )

        description = fix_result.get(
            "description",
            "No description available.",
        )

        confidence = float(
            fix_result.get(
                "confidence",
                0.0,
            )
        )

        # --------------------------------------------------------
        # No repair candidate
        # --------------------------------------------------------

        if not fixed_code:

            state.log(
                f"No repair candidate generated "
                f"on attempt {attempt_number}."
            )

            break

        # --------------------------------------------------------
        # Prevent infinite identical repairs
        # --------------------------------------------------------

        if (
            attempt_number > 1
            and fixed_code == previous_fixed_code
        ):

            state.log(
                "Fixer produced the same code again. "
                "Stopping retry loop."
            )

            break

        state.working_code = fixed_code

        previous_fixed_code = fixed_code

        state.log(
            f"Repair candidate generated: {strategy}"
        )

        # ========================================================
        # 7. VALIDATION
        # ========================================================

        try:
            from agents.validator import validate_code

            test_code = ""

            if isinstance(
                state.generated_tests,
                dict,
            ):
                test_code = state.generated_tests.get(
                    "test_code",
                    "",
                )

            validation_result = validate_code(
                code=fixed_code,
                test_code=test_code,
                timeout=timeout,
            )

        except Exception as exc:

            validation_result = {
                "valid": False,
                "success": False,
                "syntax_valid": False,
                "execution_success": False,
                "tests_passed": False,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "stdout": "",
                "stderr": str(exc),
                "test_stdout": "",
                "test_stderr": "",
                "timed_out": False,
            }

        state.validation = validation_result

        # ========================================================
        # 8. CHECK VALIDATION
        # ========================================================

        passed = bool(
            validation_result.get(
                "valid",
                False,
            )
        )

        # ========================================================
        # SAVE ATTEMPT
        # ========================================================

        repair_attempt = RepairAttempt(
            attempt_number=attempt_number,
            fixed_code=fixed_code,
            strategy=strategy,
            description=description,
            confidence=confidence,
            validation_result=validation_result,
            test_results={
                "tests_passed": validation_result.get(
                    "tests_passed",
                    False,
                ),
                "test_stdout": validation_result.get(
                    "test_stdout",
                    "",
                ),
                "test_stderr": validation_result.get(
                    "test_stderr",
                    "",
                ),
            },
            passed=passed,
        )

        state.repair_attempts.append(
            repair_attempt
        )

        # ========================================================
        # SUCCESS
        # ========================================================

        if passed:

            state.repair_succeeded = True

            state.current_code = fixed_code
            state.working_code = fixed_code

            state.best_repair = repair_attempt

            state.log(
                f"Repair attempt {attempt_number} "
                f"PASSED validation."
            )

            break

        # ========================================================
        # FAILED → CREATE FEEDBACK
        # ========================================================

        state.log(
            f"Repair attempt {attempt_number} "
            f"FAILED validation."
        )

        validator_feedback = {
            "attempt_number": attempt_number,

            "previous_code": fixed_code,

            "previous_strategy": strategy,

            "validation_error_type": (
                validation_result.get(
                    "error_type",
                    "",
                )
            ),

            "validation_error_message": (
                validation_result.get(
                    "error_message",
                    "",
                )
            ),

            "stderr": (
                validation_result.get(
                    "stderr",
                    "",
                )
            ),

            "stdout": (
                validation_result.get(
                    "stdout",
                    "",
                )
            ),

            "tests_passed": (
                validation_result.get(
                    "tests_passed",
                    False,
                )
            ),

            "test_output": (
                validation_result.get(
                    "test_stdout",
                    "",
                )
            ),

            "test_error": (
                validation_result.get(
                    "test_stderr",
                    "",
                )
            ),
        }

        # IMPORTANT:
        # Keep failed repaired code as working code.
        # The next Fixer attempt will receive this code.

        state.working_code = fixed_code

        if attempt_number < max_retries:

            state.log(
                "Validator feedback sent back to Fixer."
            )

        else:

            state.log(
                "Maximum repair attempts reached."
            )

    # ============================================================
    # 9. FINAL CODE
    # ============================================================

    if state.repair_succeeded:

        if state.best_repair:

            state.current_code = (
                state.best_repair.fixed_code
            )

        state.log(
            "Self-healing completed successfully."
        )

    else:

        state.current_code = (
            state.original_code
        )

        state.log(
            "No validated repair was produced."
        )

    # ============================================================
    # 10. EXPLAINER
    # ============================================================

    try:
        from agents.explainer import explain_debugging

        state.explanation = explain_debugging(
            original_code=state.original_code,
            final_code=state.current_code,
            detection=state.detection,
            analysis=state.analysis,
            classification=state.classification,
            repair_attempts=[
                {
                    "attempt_number": attempt.attempt_number,
                    "strategy": attempt.strategy,
                    "description": attempt.description,
                    "confidence": attempt.confidence,
                    "passed": attempt.passed,
                    "validation": attempt.validation_result,
                }
                for attempt in state.repair_attempts
            ],
            validation=state.validation,
        )

    except Exception as exc:

        state.explanation = {
            "error": str(exc)
        }

        state.log(
            f"Explanation generation failed: {exc}"
        )

    # ============================================================
    # 11. CODE QUALITY
    # ============================================================

    try:
        from agents.architecture import analyze_architecture

        state.quality_report = analyze_architecture(
            code=state.current_code,
            analysis=state.analysis,
        )

    except Exception as exc:

        state.quality_report = {
            "error": str(exc)
        }

    # ============================================================
    # 12. STORE SUCCESSFUL REPAIR
    # ============================================================

    try:
        from knowledge.knowledge_base import KnowledgeBase

        kb = KnowledgeBase()

        if state.repair_succeeded and state.best_repair:

            attempt = state.best_repair

            kb.store(
                error_type=state.detection.get(
                    "error_type",
                    "",
                ),
                error_message=state.detection.get(
                    "error_msg",
                    "",
                ),
                original_code=state.original_code,
                fixed_code=attempt.fixed_code,
                repair_strategy=attempt.strategy,
                validation_ok=True,
                test_ok=attempt.test_results.get(
                    "tests_passed",
                    False,
                ),
                attempts=state.total_attempts,
                explanation=attempt.description,
                confidence=attempt.confidence,
            )

            state.log(
                "Successful repair stored in knowledge base."
            )

    except Exception as exc:

        state.log(
            f"Knowledge base storage skipped: {exc}"
        )

    # ============================================================
    # FINISH
    # ============================================================

    state.pipeline_end = time.time()

    state.log(
        f"Pipeline finished in "
        f"{state.total_time:.2f} seconds."
    )

    return state


# ================================================================
# BACKWARD COMPATIBILITY
# ================================================================


def debug_code(
    code: str,
    max_retries: int = 3,
    timeout: int = 5,
    use_llm: bool = False,
) -> DebugState:

    return run_pipeline(
        code=code,
        max_retries=max_retries,
        timeout=timeout,
        use_llm=use_llm,
    )