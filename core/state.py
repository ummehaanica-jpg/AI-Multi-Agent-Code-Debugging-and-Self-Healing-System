"""
core/state.py

Shared state object passed between all agents in the pipeline.
Each field is populated progressively as agents run.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RepairAttempt:
    """Record of one repair attempt."""
    attempt_number: int
    fixed_code: str
    strategy: str
    description: str
    confidence: float
    validation_result: dict[str, Any] = field(default_factory=dict)
    test_results: dict[str, Any] = field(default_factory=dict)
    passed: bool = False


@dataclass
class DebugState:
    """
    Central state object for the multi-agent debugging pipeline.

    Passed between agents by the orchestrator.
    Each agent reads relevant fields and writes its own output fields.
    """

    # ── Input ─────────────────────────────────────────────────────
    original_code: str = ""
    current_code: str = ""  # Updated after each successful repair attempt
    working_code: str = ""  
    # ── Agent 1: Error Detection ───────────────────────────────────
    detection: dict[str, Any] = field(default_factory=dict)

    # ── Agent 2: Code Analysis ─────────────────────────────────────
    analysis: dict[str, Any] = field(default_factory=dict)

    # ── Agent 3: Bug Classification ───────────────────────────────
    classification: dict[str, Any] = field(default_factory=dict)

    # ── Agent 4: Knowledge Base ───────────────────────────────────
    kb_matches: list[dict[str, Any]] = field(default_factory=list)

    # ── Agent 5: Fixer ────────────────────────────────────────────
    repair_attempts: list[RepairAttempt] = field(default_factory=list)
    best_repair: RepairAttempt | None = None

    # ── Agent 6: Test Generator ───────────────────────────────────
    generated_tests: dict[str, Any] = field(default_factory=dict)

    # ── Agent 7: Validator ────────────────────────────────────────
    validation: dict[str, Any] = field(default_factory=dict)

    # ── Agent 8: Explainer ────────────────────────────────────────
    explanation: dict[str, Any] = field(default_factory=dict)

    # ── Agent 9: Code Quality ─────────────────────────────────────
    quality_report: dict[str, Any] = field(default_factory=dict)

    # ── Pipeline metadata ─────────────────────────────────────────
    pipeline_start: float = field(default_factory=time.time)
    pipeline_end: float = 0.0
    max_retries: int = 3
    total_attempts: int = 0
    repair_succeeded: bool = False
    pipeline_log: list[str] = field(default_factory=list)
    agent_timings: dict[str, float] = field(default_factory=dict)
    error: str = ""  # Pipeline-level error message

    def log(self, message: str) -> None:
        """Append a log message."""
        self.pipeline_log.append(f"[{time.strftime('%H:%M:%S')}] {message}")

    @property
    def total_time(self) -> float:
        """Total elapsed time in seconds."""
        end = self.pipeline_end or time.time()
        return round(end - self.pipeline_start, 3)

    @property
    def final_code(self) -> str:
        """Return the final accepted code (fixed if repair succeeded, else original)."""
        if self.repair_succeeded and self.best_repair:
            return self.best_repair.fixed_code
        return self.original_code
