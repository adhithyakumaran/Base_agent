"""Controlled self-healing pipeline for approved Playwright test failures."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from qa_orchestrator.execution_gate import ExecutionGate
from qa_orchestrator.failure_classifier import classify_failure
from qa_orchestrator.healing_dom import load_dom_from_path
from qa_orchestrator.healing_evidence import capture_stage, healing_evidence_root
from qa_orchestrator.healing_journal import save_journal
from qa_orchestrator.healing_locator import generate_candidates, validate_candidate
from qa_orchestrator.healing_policy import (
    MAX_HEALING_ATTEMPTS,
    TIMING_RETRY_MS,
    is_auto_heal_candidate,
    is_healing_eligible,
    policy_reason,
    reject_candidate,
    requires_human_review,
)
from qa_orchestrator.healing_proposal_store import new_healing_id, save_proposal
from qa_orchestrator.healing_runner import run_isolated_retry, simulate_retry_success
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.models import (
    ExecutionResult,
    FailureClassification,
    HealingAttemptRecord,
    HealingJournal,
    HealingLocatorCandidate,
    HealingProposal,
    HealingResult,
    StepObservation,
)


class HealingService:
    HEALER_VERSION = "p3.0"

    def __init__(self, graph: FlowKnowledgeGraph) -> None:
        self.graph = graph
        self.automation_dir = Path(graph.automation_dir)
        self.gate = ExecutionGate(graph)

    def attempt_healing(
        self,
        execution: ExecutionResult,
        *,
        run_id: str = "",
        flow_id: str = "",
        test_id: str = "",
        healing_id: str | None = None,
        simulate_retry: bool | None = None,
    ) -> HealingResult:
        hid = healing_id or new_healing_id()
        failed_obs = _first_failed_observation(execution)
        if failed_obs is None:
            return HealingResult(
                healing_id=hid,
                status="NOT_HEALABLE",
                message="No failed observation to analyze",
                execution_still_blocked=True,
            )

        failure = classify_failure(
            observation=failed_obs,
            flow_id=flow_id,
            test_id=test_id,
            step_id=str(failed_obs.step_index),
        )
        if not is_healing_eligible(failure):
            return self._not_healable(hid, failure, run_id)

        evidence_root = healing_evidence_root(
            self.automation_dir,
            run_id or "healing-run",
            test_id or failure.test_id or "unknown-test",
        )
        original = capture_stage(
            evidence_root,
            "failure-original",
            screenshot_src=_abs_path(self.automation_dir, failure.screenshot_path),
            dom_src=_abs_path(self.automation_dir, failure.dom_evidence_path),
            meta={"failure_type": failure.type, "error": failure.error_message[:500]},
        )

        if failure.type == "TIMING":
            return self._heal_timing(hid, failure, run_id, test_id, evidence_root, original, simulate_retry)

        dom_path = _abs_path(self.automation_dir, failure.dom_evidence_path)
        elements = load_dom_from_path(dom_path) if dom_path else []
        candidates = generate_candidates(failure, dom_elements=elements, dom_path=dom_path)
        if not candidates:
            return HealingResult(
                healing_id=hid,
                status="NO_CANDIDATE",
                failure=failure,
                message="No locator candidates generated from DOM evidence",
                execution_still_blocked=True,
            )

        best = candidates[0]
        best = validate_candidate(best, elements)
        proposal = self._build_proposal(hid, failure, best, [original.get("dir", "")])

        if reject_candidate(best):
            proposal.status = "DRAFT"
            save_proposal(self.automation_dir, proposal)
            journal = self._journal(hid, run_id, flow_id, test_id, failure, [], proposal, "NO_CANDIDATE", [original.get("dir", "")])
            save_journal(self.automation_dir, journal)
            return HealingResult(
                healing_id=hid,
                status="NO_CANDIDATE",
                failure=failure,
                proposal=proposal,
                journal=journal,
                message=f"Candidate confidence {best.confidence} below healing threshold",
                execution_still_blocked=True,
            )

        if requires_human_review(best):
            proposal.status = "PENDING_SME_APPROVAL"
            save_proposal(self.automation_dir, proposal)
            journal = self._journal(hid, run_id, flow_id, test_id, failure, [], proposal, "NEEDS_REVIEW", [original.get("dir", "")])
            save_journal(self.automation_dir, journal)
            return HealingResult(
                healing_id=hid,
                status="NEEDS_REVIEW",
                failure=failure,
                proposal=proposal,
                journal=journal,
                message="Candidate requires SME review before locator update",
                execution_still_blocked=True,
            )

        attempts: list[HealingAttemptRecord] = []
        evidence_paths = [original.get("dir", "")]
        simulate = simulate_retry if simulate_retry is not None else _default_simulate()
        outcome = "HEALING_FAILED"

        for attempt_num in range(1, MAX_HEALING_ATTEMPTS + 1):
            candidate = candidates[min(attempt_num - 1, len(candidates) - 1)]
            candidate = validate_candidate(candidate, elements)
            if not is_auto_heal_candidate(candidate):
                break
            candidate_dir = capture_stage(
                evidence_root,
                f"candidate-{attempt_num}",
                meta={"candidate": candidate.model_dump(), "attempt": attempt_num},
            )
            evidence_paths.append(candidate_dir.get("dir", ""))

            retry = (
                {"ok": simulate_retry_success(candidate), "simulated": True}
                if simulate
                else run_isolated_retry(
                    automation_dir=self.automation_dir,
                    test_grep=test_id or flow_id or "BF-",
                    candidate=candidate,
                    locator_label=failure.locator_label or "search button",
                    run_id=run_id,
                    flow_id=flow_id,
                )
            )
            retry_dir = capture_stage(
                evidence_root,
                f"retry-{attempt_num}",
                meta={"retry_ok": retry.get("ok"), "attempt": attempt_num},
            )
            evidence_paths.append(retry_dir.get("dir", ""))
            attempts.append(
                HealingAttemptRecord(
                    attempt=attempt_num,
                    candidate=candidate,
                    applied=True,
                    retry_ok=bool(retry.get("ok")),
                    evidence_dir=retry_dir.get("dir", ""),
                    message=str(retry.get("message") or retry.get("stderr_tail") or "")[:500],
                )
            )
            if retry.get("ok"):
                outcome = "HEALED_PENDING_APPROVAL"
                proposal.status = "PENDING_SME_APPROVAL"
                proposal.result = "isolated retry succeeded — pending SME approval"
                proposal.validation = {"attempts": attempt_num, "confidence": candidate.confidence}
                break

        if outcome != "HEALED_PENDING_APPROVAL":
            proposal.status = "DRAFT"
            proposal.result = "healing attempts exhausted"

        save_proposal(self.automation_dir, proposal)
        journal = self._journal(hid, run_id, flow_id, test_id, failure, attempts, proposal, outcome, evidence_paths)
        save_journal(self.automation_dir, journal)

        return HealingResult(
            healing_id=hid,
            status=outcome,  # type: ignore[arg-type]
            failure=failure,
            proposal=proposal,
            journal=journal,
            attempts_used=len(attempts),
            message=proposal.result or outcome,
            execution_still_blocked=True,
        )

    def _heal_timing(
        self,
        hid: str,
        failure: FailureClassification,
        run_id: str,
        test_id: str,
        evidence_root: Path,
        original: dict,
        simulate_retry: bool | None,
    ) -> HealingResult:
        simulate = simulate_retry if simulate_retry is not None else _default_simulate()
        candidate = HealingLocatorCandidate(
            primary="timing-wait",
            confidence=0.75,
            evidence="Bounded wait extension",
            reason="Deterministic timing retry",
            validated=True,
        )
        retry = (
            {"ok": True, "simulated": True}
            if simulate
            else run_isolated_retry(
                automation_dir=self.automation_dir,
                test_grep=test_id or "BF-",
                candidate=candidate,
                locator_label="timing",
                run_id=run_id,
                timing_wait_ms=TIMING_RETRY_MS,
            )
        )
        attempt = HealingAttemptRecord(
            attempt=1,
            candidate=candidate,
            applied=True,
            retry_ok=bool(retry.get("ok")),
            message="timing retry",
        )
        proposal = self._build_proposal(hid, failure, candidate, [original.get("dir", "")])
        proposal.status = "PENDING_SME_APPROVAL" if retry.get("ok") else "DRAFT"
        proposal.result = "timing retry succeeded" if retry.get("ok") else "timing retry failed"
        save_proposal(self.automation_dir, proposal)
        journal = self._journal(
            hid,
            run_id,
            failure.flow_id,
            test_id,
            failure,
            [attempt],
            proposal,
            "NEEDS_REVIEW" if retry.get("ok") else "HEALING_FAILED",
            [original.get("dir", ""), evidence_root.as_posix()],
        )
        save_journal(self.automation_dir, journal)
        return HealingResult(
            healing_id=hid,
            status=journal.outcome,  # type: ignore[arg-type]
            failure=failure,
            proposal=proposal,
            journal=journal,
            attempts_used=1,
            message=proposal.result,
            execution_still_blocked=True,
        )

    def _not_healable(self, hid: str, failure: FailureClassification, run_id: str) -> HealingResult:
        journal = HealingJournal(
            healing_id=hid,
            run_id=run_id,
            flow_id=failure.flow_id,
            test_id=failure.test_id,
            failure=failure,
            outcome="NOT_HEALABLE",
            timestamp=datetime.now(timezone.utc).isoformat(),
            healer_version=self.HEALER_VERSION,
        )
        save_journal(self.automation_dir, journal)
        return HealingResult(
            healing_id=hid,
            status="NOT_HEALABLE",
            failure=failure,
            journal=journal,
            message=policy_reason(failure),
            execution_still_blocked=True,
        )

    def _build_proposal(
        self,
        hid: str,
        failure: FailureClassification,
        candidate: HealingLocatorCandidate,
        evidence: list[str],
    ) -> HealingProposal:
        return HealingProposal(
            healing_id=hid,
            flow_id=failure.flow_id,
            test_id=failure.test_id,
            step_id=failure.step_id,
            locator_label=failure.locator_label or "",
            old_locator=failure.original_locator or "",
            new_locator=candidate.primary,
            fallbacks=candidate.fallbacks,
            reason=candidate.reason,
            evidence=[e for e in evidence if e],
            confidence=candidate.confidence,
            validation={"validated": candidate.validated, "evidence": candidate.evidence},
            result="",
            status="DRAFT",
            failure_type=failure.type,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _journal(
        self,
        hid: str,
        run_id: str,
        flow_id: str,
        test_id: str,
        failure: FailureClassification,
        attempts: list[HealingAttemptRecord],
        proposal: HealingProposal,
        outcome: str,
        evidence_paths: list[str],
    ) -> HealingJournal:
        return HealingJournal(
            healing_id=hid,
            run_id=run_id,
            flow_id=flow_id or failure.flow_id,
            test_id=test_id or failure.test_id,
            failure=failure,
            attempts=attempts,
            proposal=proposal,
            outcome=outcome,  # type: ignore[arg-type]
            evidence_paths=[p for p in evidence_paths if p],
            timestamp=datetime.now(timezone.utc).isoformat(),
            healer_version=self.HEALER_VERSION,
        )


def _first_failed_observation(execution: ExecutionResult) -> StepObservation | None:
    for obs in execution.observations:
        if not obs.ok:
            return obs
    return None


def _abs_path(automation_dir: Path, rel: str | None) -> Path | None:
    if not rel:
        return None
    path = Path(rel)
    if path.is_absolute():
        return path if path.exists() else None
    candidate = automation_dir / rel
    return candidate if candidate.exists() else None


def _default_simulate() -> bool:
    import os

    return os.environ.get("QA_HEALING_SIMULATE", "true").lower() in {"1", "true", "yes"}
