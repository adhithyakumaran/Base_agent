from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from qa_orchestrator.gt_eval import evaluate_gt_expectations, goal_matches_gt
from qa_orchestrator.kb_rag import KbRag
from qa_orchestrator.models import (
    DiscoveryResult,
    ExecutionPlan,
    ExecutionResult,
    IntentClassification,
    SuiteSelectionPlan,
    ValidationFinding,
    ValidationResult,
)


class Validator:
    """Phase A: technical rules + honest NEEDS_REVIEW pre-GT. Phase B: GT compare when approved."""

    def __init__(self, kb: KbRag | Any, *, gt_dir: str | Path | None = None) -> None:
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
        intent: IntentClassification | None = None,
        suite_plan: SuiteSelectionPlan | None = None,
        discovery: DiscoveryResult | None = None,
    ) -> ValidationResult:
        matched_gt = self._matching_gt(goal)
        if matched_gt:
            return self._validate_phase_b(goal, plan, execution, matched_gt)
        return self._validate_phase_a(
            goal,
            run_type,
            plan,
            execution,
            llm_summary,
            intent=intent,
            suite_plan=suite_plan,
            discovery=discovery,
        )

    def _validate_phase_a(
        self,
        goal: str,
        run_type: str,
        plan: ExecutionPlan,
        execution: ExecutionResult,
        llm_summary: str,
        *,
        intent: IntentClassification | None = None,
        suite_plan: SuiteSelectionPlan | None = None,
        discovery: DiscoveryResult | None = None,
    ) -> ValidationResult:
        findings: list[ValidationFinding] = []

        if execution.mode != "skipped" and not execution.ok:
            findings.append(
                ValidationFinding(
                    code="execution.failed",
                    severity="error",
                    message=execution.error or "Playwright suite execution failed",
                )
            )
        failed_steps = [o for o in execution.observations if not o.ok]
        for obs in failed_steps:
            findings.append(
                ValidationFinding(
                    code="step.failed",
                    severity="error",
                    message=f"Suite {obs.step_index} ({obs.action}): {obs.message}",
                )
            )

        if execution.mode == "mock":
            findings.append(
                ValidationFinding(
                    code="execution.mock",
                    severity="warn",
                    message="OpenClaw mock mode — production path uses Playwright (QA_RUNNER=playwright)",
                )
            )

        if execution.mode.startswith("playwright_dry_run"):
            findings.append(
                ValidationFinding(
                    code="execution.dry_run",
                    severity="info",
                    message="Playwright dry-run — suite commands validated without live npm execution",
                )
            )

        if suite_plan and not suite_plan.commands and execution.mode != "skipped":
            findings.append(ValidationFinding(code="suite.empty", severity="error", message="No suite commands selected"))

        if intent and intent.execution_mode == "morning_sanity" and suite_plan:
            if suite_plan.suite_ids != ["SUITE-SANITY-MORNING"] and "SUITE-SANITY-MORNING" not in suite_plan.suite_ids:
                findings.append(
                    ValidationFinding(
                        code="sanity.suite_mismatch",
                        severity="warn",
                        message="Morning sanity should target SUITE-SANITY-MORNING",
                    )
                )

        if discovery and intent and intent.execution_mode in {"new_feature", "discover"}:
            findings.append(
                ValidationFinding(
                    code="discovery.completed",
                    severity="info",
                    message=f"Discovery crawl ({discovery.mode}): {discovery.pages_crawled} pages",
                )
            )
            for suggestion in discovery.suggestions[:3]:
                findings.append(
                    ValidationFinding(code="discovery.suggestion", severity="info", message=suggestion)
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

        mode_label = intent.execution_mode if intent else run_type
        narrative = llm_summary or plan.summary
        summary = (
            f"Phase A ({mode_label}): {narrative}. "
            "Business outcome requires SME Ground Truth approval for PASS."
        )
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
        matched_gt: tuple[str, dict[str, Any]],
    ) -> ValidationResult:
        gt_id, fact = matched_gt
        findings: list[ValidationFinding] = []
        meta_list = [o.meta or {} for o in execution.observations if o.meta]

        passed, failures = evaluate_gt_expectations(fact, execution.ok, meta_list)
        if not passed:
            return ValidationResult(
                phase="B",
                conclusion="FAIL",
                reason_code="validator.gt_expectation_failed",
                summary=f"Approved GT {gt_id} expectations not met: {'; '.join(failures)}",
                findings=[
                    ValidationFinding(code="gt.expectation_failed", severity="error", message=f)
                    for f in failures
                ],
                gt_refs=[gt_id],
            )

        return ValidationResult(
            phase="B",
            conclusion="PASS",
            reason_code="validator.gt_match",
            summary="Approved GT expectations satisfied by structured execution results",
            findings=findings,
            gt_refs=[gt_id],
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

    def _matching_gt(self, goal: str) -> tuple[str, dict[str, Any]] | None:
        for gid, fact in self._approved_gt.items():
            if goal_matches_gt(goal, fact):
                return gid, fact
        return None
