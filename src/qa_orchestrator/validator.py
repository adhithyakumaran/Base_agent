from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from qa_orchestrator.kb_rag import KbRag
from qa_orchestrator.models import ExecutionPlan, ExecutionResult, ValidationFinding, ValidationResult


class Validator:
    """Phase A: technical rules + honest NEEDS_REVIEW pre-GT. Phase B: GT compare when approved."""

    def __init__(self, kb: KbRag, *, gt_dir: str | Path | None = None) -> None:
        self.kb = kb
        self.gt_dir = Path(gt_dir) if gt_dir else None
        self._approved_gt = self._load_approved_gt()

    def validate(
        self,
        *,
        goal: str,
        run_type: str,
        plan: ExecutionPlan,
        execution: ExecutionResult,
        llm_summary: str = "",
    ) -> ValidationResult:
        if self._approved_gt and self._has_gt_coverage(goal):
            return self._validate_phase_b(goal, plan, execution, llm_summary)
        return self._validate_phase_a(goal, run_type, plan, execution, llm_summary)

    def _validate_phase_a(
        self,
        goal: str,
        run_type: str,
        plan: ExecutionPlan,
        execution: ExecutionResult,
        llm_summary: str,
    ) -> ValidationResult:
        findings: list[ValidationFinding] = []

        if not execution.ok:
            findings.append(
                ValidationFinding(
                    code="execution.failed",
                    severity="error",
                    message=execution.error or "OpenClaw execution failed",
                )
            )
        failed_steps = [o for o in execution.observations if not o.ok]
        for obs in failed_steps:
            findings.append(
                ValidationFinding(
                    code="step.failed",
                    severity="error",
                    message=f"Step {obs.step_index} ({obs.action}): {obs.message}",
                )
            )

        if execution.mode == "mock":
            findings.append(
                ValidationFinding(
                    code="execution.mock",
                    severity="warn",
                    message="OpenClaw mock mode — set OPENCLAW_MODE=http when OpenClaw is running",
                )
            )

        if not plan.steps:
            findings.append(
                ValidationFinding(code="plan.empty", severity="error", message="Planner produced no steps")
            )

        errors = [f for f in findings if f.severity == "error"]
        if errors:
            return ValidationResult(
                phase="A",
                conclusion="FAIL",
                reason_code="validator.technical_failure",
                summary="Technical execution failure before business validation",
                findings=findings,
            )

        if run_type == "sanity" and len(execution.observations) < 3:
            findings.append(
                ValidationFinding(
                    code="sanity.shallow",
                    severity="warn",
                    message="Sanity run completed fewer steps than expected",
                )
            )

        narrative = llm_summary or plan.summary
        summary = f"Phase A (pre-GT): {narrative}. Business outcome requires SME Ground Truth."
        return ValidationResult(
            phase="A",
            conclusion="NEEDS_REVIEW",
            reason_code="validator.pre_gt_honest",
            summary=summary,
            findings=findings,
        )

    def _validate_phase_b(
        self,
        goal: str,
        plan: ExecutionPlan,
        execution: ExecutionResult,
        llm_summary: str,
    ) -> ValidationResult:
        findings: list[ValidationFinding] = []
        if not execution.ok:
            return ValidationResult(
                phase="B",
                conclusion="FAIL",
                reason_code="validator.gt_execution_failed",
                summary="Execution failed — GT comparison skipped",
                findings=findings,
                gt_refs=list(self._approved_gt.keys())[:5],
            )

        matched = [gid for gid, fact in self._approved_gt.items() if _goal_matches_gt(goal, fact)]
        if matched:
            return ValidationResult(
                phase="B",
                conclusion="PASS",
                reason_code="validator.gt_match",
                summary=llm_summary or "Approved GT matched observed behaviour",
                findings=findings,
                gt_refs=matched,
            )

        return ValidationResult(
            phase="B",
            conclusion="NEEDS_REVIEW",
            reason_code="validator.gt_partial",
            summary="GT loaded but no matching approved fact for this goal yet",
            findings=findings,
            gt_refs=[],
        )

    def _load_approved_gt(self) -> dict[str, dict[str, Any]]:
        if not self.gt_dir or not self.gt_dir.exists():
            return {}
        approved: dict[str, dict[str, Any]] = {}
        for path in self.gt_dir.glob("*.json"):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if doc.get("status") == "approved":
                approved[path.stem] = doc
        return approved

    def _has_gt_coverage(self, goal: str) -> bool:
        return any(_goal_matches_gt(goal, fact) for fact in self._approved_gt.values())


def _goal_matches_gt(goal: str, fact: dict[str, Any]) -> bool:
    subjects = [
        str(fact.get("subject", "")),
        str(fact.get("id", "")),
        " ".join(str(t) for t in fact.get("tags", [])),
    ]
    g = goal.lower()
    return any(s and s.lower() in g for s in subjects)
