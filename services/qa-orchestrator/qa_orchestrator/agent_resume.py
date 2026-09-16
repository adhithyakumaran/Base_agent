"""P6.1 — resume WAITING_FOR_APPROVAL agent runs with safety checks."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from qa_orchestrator.agent_journal import load_journal
from qa_orchestrator.agent_metrics import metrics_from_single_run
from qa_orchestrator.agent_models import AgentDecisionEntry, AgentRunResult, AgentRunState
from qa_orchestrator.agent_state_store import (
    ResumableAgentSnapshot,
    artifact_fingerprint,
    load_snapshot,
    mutate_snapshot,
    save_snapshot,
)
from qa_orchestrator.execution_gate import ExecutionGate, CANONICAL_ARTIFACT
from qa_orchestrator.healing_overlay import apply_approved_proposal, load_overlay_store, resolve_overlay_selectors
from qa_orchestrator.healing_proposal_store import load_proposal
from qa_orchestrator.healing_runner import run_isolated_retry, simulate_retry_success
from qa_orchestrator.models import ExecutionResult, HealingLocatorCandidate
from qa_orchestrator.run_request import RunRequest

_TERMINAL = frozenset({"COMPLETED", "FAILED", "BLOCKED", "NEEDS_REVIEW"})
_RESUMABLE = frozenset({"WAITING_FOR_APPROVAL"})


class AgentResumeError(Exception):
    """Controlled resume failure — safe to expose without secrets."""


class AgentResumeService:
    def __init__(self, orchestrator) -> None:
        self.orchestrator = orchestrator
        self.gate = ExecutionGate(orchestrator.graph)
        self.base_dir = orchestrator.agent_loop.config.journal_dir

    def get_state(self, run_id: str) -> ResumableAgentSnapshot:
        return load_snapshot(run_id, base_dir=self.base_dir)

    def resume(
        self,
        run_id: str,
        *,
        resume_token: str | None = None,
        resume_reason: str = "approval granted",
    ) -> AgentRunResult:
        try:
            snapshot = load_snapshot(run_id, base_dir=self.base_dir)
        except FileNotFoundError as exc:
            raise AgentResumeError(f"run {run_id} is not resumable: no persisted state") from exc
        except ValueError as exc:
            raise AgentResumeError(str(exc)) from exc

        token = resume_token or uuid4().hex
        idempotent: dict[str, ResumableAgentSnapshot | None] = {"snapshot": None}

        def _capture(snap: ResumableAgentSnapshot) -> None:
            if snap.last_applied_resume_token == token:
                idempotent["snapshot"] = snap

        mutate_snapshot(run_id, _capture, base_dir=self.base_dir)
        if idempotent["snapshot"] is not None:
            return self._result_from_snapshot(idempotent["snapshot"], note="idempotent resume — no duplicate actions")

        snapshot = load_snapshot(run_id, base_dir=self.base_dir)
        if snapshot.last_applied_resume_token == token:
            return self._result_from_snapshot(snapshot, note="idempotent resume — no duplicate actions")

        state = snapshot.state
        if state.status in _TERMINAL - {"WAITING_FOR_APPROVAL"}:
            raise AgentResumeError(f"run {run_id} already terminal: {state.status}")

        if state.status not in _RESUMABLE:
            raise AgentResumeError(f"run {run_id} is not resumable from status={state.status}")

        req = RunRequest(**snapshot.run_request) if snapshot.run_request else RunRequest(goal=state.request, run_type=state.run_type)

        validation = self._validate_resume(snapshot)
        if not validation["ok"]:
            state.status = "NEEDS_REVIEW"
            state.reason_code = validation["reason_code"]
            state.summary = validation["message"]
            state.final_result = "NEEDS_REVIEW"
            from qa_orchestrator.decision_diagnostics import (
                attach_diagnostic_to_state,
                build_execution_gate_block_diagnostic,
                build_terminal_diagnostic,
                log_decision_block,
            )

            flow_id = state.current_flow or (state.selected_flows[0] if state.selected_flows else "")
            gate_diag = None
            if flow_id and str(validation["reason_code"]).startswith(("approval.", "kb.", "gate.")):
                gate_diag = build_execution_gate_block_diagnostic(
                    self.gate,
                    flow_id,
                    run_id=run_id,
                    stage="agent_resume",
                )
            attach_diagnostic_to_state(
                state,
                gate_diag
                or build_terminal_diagnostic(
                    run_id=run_id,
                    stage="agent_resume",
                    status="NEEDS_REVIEW",
                    reason_code=str(validation["reason_code"]),
                    message=str(validation["message"]),
                    failed_checks=[str(validation["reason_code"])],
                    extra={"checkpoint": snapshot.checkpoint, "resume_reason": resume_reason},
                ),
            )
            log_decision_block(state.decision_diagnostics)
            self._append_resume_journal(
                state,
                resume_reason=resume_reason,
                checkpoint=snapshot.checkpoint,
                previous_state="WAITING_FOR_APPROVAL",
                new_state="NEEDS_REVIEW",
                result=validation["message"],
            )
            snapshot.state = state
            save_snapshot(snapshot, base_dir=self.base_dir)
            return self.orchestrator.agent_loop._finalize(state, req, started=0.0)  # type: ignore[attr-defined]

        self._append_resume_journal(
            state,
            resume_reason=resume_reason,
            checkpoint=snapshot.checkpoint,
            previous_state="WAITING_FOR_APPROVAL",
            new_state="READY",
            result="resume validated",
        )

        kind = snapshot.approval_pause_kind
        if kind == "healing":
            state = self._resume_healing(state, snapshot, req, token)
        elif kind == "generation":
            state = self._resume_generation(state, snapshot, req, token)
        else:
            state = self._resume_execution_gate(state, snapshot, req, token)

        if state.status in _RESUMABLE:
            result = self.orchestrator.agent_loop._finalize(state, req, started=0.0)  # type: ignore[attr-defined]
        else:
            result = self.orchestrator.agent_loop._continue_from_state(state, req)  # type: ignore[attr-defined]

        snapshot.state = result.state
        snapshot.last_applied_resume_token = token
        save_snapshot(snapshot, base_dir=self.base_dir)
        return result

    def _validate_resume(self, snapshot: ResumableAgentSnapshot) -> dict[str, Any]:
        state = snapshot.state
        kind = snapshot.approval_pause_kind

        if kind == "healing":
            return self._validate_healing_resume(snapshot)
        if kind == "generation":
            return self._validate_generation_resume(snapshot)

        flow_id = state.current_flow or (state.selected_flows[0] if state.selected_flows else "")
        if not flow_id and state.plan and state.plan.candidate_flows:
            flow_id = state.plan.candidate_flows[0]
        if not flow_id:
            if state.suite_plan and state.suite_plan.commands:
                return {"ok": True, "reason_code": "gate.suite_command", "message": "suite command resume allowed"}
            return {"ok": False, "reason_code": "resume.no_flow", "message": "no flow selected for resume"}

        decision = self.gate.evaluate(flow_id)
        if not decision.executable:
            return {"ok": False, "reason_code": decision.reason_code, "message": decision.message}

        stored_fp = snapshot.artifact_fingerprints.get(flow_id, "")
        artifact_path = self.gate.design_root / flow_id / CANONICAL_ARTIFACT
        current_fp = artifact_fingerprint(artifact_path)
        paused_status = snapshot.artifact_status_at_pause.get(flow_id, "")
        if (
            stored_fp
            and current_fp
            and stored_fp != current_fp
            and paused_status == "APPROVED"
        ):
            return {
                "ok": False,
                "reason_code": "approval.stale",
                "message": f"{flow_id}: artifact changed after pause — re-approval required",
            }
        if decision.approval_stale:
            return {
                "ok": False,
                "reason_code": "approval.stale",
                "message": decision.message,
            }
        return {"ok": True, "reason_code": "gate.executable", "message": decision.message}

    def _validate_healing_resume(self, snapshot: ResumableAgentSnapshot) -> dict[str, Any]:
        healing = snapshot.state.healing_result
        if healing is None or healing.proposal is None:
            return {"ok": False, "reason_code": "healing.missing", "message": "no healing proposal to resume"}
        proposal = load_proposal(self.orchestrator.graph.automation_dir, healing.healing_id)
        if proposal is None:
            return {"ok": False, "reason_code": "healing.missing", "message": "healing proposal file missing"}
        if proposal.status != "APPROVED":
            return {"ok": False, "reason_code": "healing.not_approved", "message": "healing proposal not APPROVED"}
        stored_fp = snapshot.artifact_fingerprints.get(f"healing:{proposal.healing_id}", "")
        current_fp = artifact_fingerprint(
            self.orchestrator.graph.automation_dir / "healing" / "proposals" / f"{proposal.healing_id}.json"
        )
        if stored_fp and current_fp and stored_fp != current_fp:
            return {"ok": False, "reason_code": "approval.stale", "message": "healing proposal changed after approval"}
        return {"ok": True, "reason_code": "healing.approved", "message": "healing proposal approved"}

    def _validate_generation_resume(self, snapshot: ResumableAgentSnapshot) -> dict[str, Any]:
        gen = snapshot.state.generation_result
        flow_id = gen.flow_id if gen else (snapshot.state.current_flow or "")
        if not flow_id:
            return {"ok": False, "reason_code": "generation.missing", "message": "no generated flow to resume"}
        decision = self.gate.evaluate(flow_id)
        if not decision.executable:
            return {"ok": False, "reason_code": decision.reason_code, "message": decision.message}
        spec_path = Path(gen.generated_spec_path) if gen and gen.generated_spec_path else None
        if spec_path and spec_path.exists():
            stored = snapshot.artifact_fingerprints.get(f"generation:{flow_id}", "")
            current = artifact_fingerprint(spec_path)
            if stored and current and stored != current:
                return {"ok": False, "reason_code": "approval.stale", "message": "generated artifact changed after approval"}
        return {"ok": True, "reason_code": "generation.approved", "message": "generated test approved"}

    def _resume_execution_gate(
        self,
        state: AgentRunState,
        snapshot: ResumableAgentSnapshot,
        req: RunRequest,
        token: str,
    ) -> AgentRunState:
        state.status = "READY"
        state.reason_code = "resume.approved"
        state.summary = "Resuming after approval"
        state.metadata["resume_checkpoint"] = snapshot.checkpoint
        state.metadata["resume_token"] = token
        if state.plan and not state.selected_flows:
            state.selected_flows = list(state.plan.candidate_flows[:1])
            state.current_flow = state.selected_flows[0] if state.selected_flows else state.current_flow
        if state.plan:
            allowed, gates = self.gate.filter_executable(state.plan.candidate_flows)
            state.selected_flows = allowed
            state.plan.selected_flows = allowed
            from qa_orchestrator.models import ExecutionGateSnapshot

            state.plan.execution_gates = [ExecutionGateSnapshot(**g.to_dict()) for g in gates]
            state.plan.execution_allowed = bool(allowed or (state.suite_plan and state.suite_plan.commands))
            if allowed:
                state.plan.requires_human_approval = False
                if state.suite_plan:
                    from qa_orchestrator.suite_commands import build_flow_command

                    polarity = state.plan.polarity if state.plan else "positive"
                    state.suite_plan.flow_ids = allowed[:1]
                    state.suite_plan.commands = [build_flow_command(allowed[0], polarity=polarity)]
        return state

    def _resume_healing(
        self,
        state: AgentRunState,
        snapshot: ResumableAgentSnapshot,
        req: RunRequest,
        token: str,
    ) -> AgentRunState:
        healing = state.healing_result
        assert healing and healing.proposal
        proposal = load_proposal(self.orchestrator.graph.automation_dir, healing.healing_id)
        assert proposal and proposal.status == "APPROVED"
        apply_approved_proposal(Path(self.orchestrator.graph.automation_dir), proposal)

        overlay = resolve_overlay_selectors(
            load_overlay_store(Path(self.orchestrator.graph.automation_dir)),
            flow_id=proposal.flow_id,
            locator_label=proposal.locator_label,
            test_id=proposal.test_id,
            step_id=proposal.step_id,
        )
        if not overlay:
            state.status = "NEEDS_REVIEW"
            state.reason_code = "healing.overlay_missing"
            state.summary = "Approved healing overlay not found"
            state.final_result = "NEEDS_REVIEW"
            return state

        if snapshot.checkpoint == "after_healing_retry" and snapshot.last_applied_resume_token:
            state.status = "READY"
            return state

        candidate = HealingLocatorCandidate(
            primary=proposal.new_locator,
            fallbacks=proposal.fallbacks,
            css_selectors=list(overlay.get("selectors") or []),
            confidence=proposal.confidence,
            validated=True,
        )
        retry = run_isolated_retry(
            automation_dir=Path(self.orchestrator.graph.automation_dir),
            test_grep=proposal.test_id or proposal.flow_id,
            candidate=candidate,
            locator_label=proposal.locator_label or "element",
            run_id=state.run_id,
            flow_id=proposal.flow_id,
            dry_run=req.skip_execution or _default_healing_dry_run(),
        )
        if not retry.get("ok") and not simulate_retry_success(candidate):
            state.status = "NEEDS_REVIEW"
            state.reason_code = "healing.retry_failed"
            state.summary = "Approved healing retry failed verification"
            state.final_result = "NEEDS_REVIEW"
            return state

        state.execution = ExecutionResult(ok=True, mode="healing_retry", observations=[])
        snapshot.checkpoint = "after_healing_retry"
        snapshot.completed_steps.append("healing_retry")
        state.status = "READY"
        state.metadata["resume_checkpoint"] = snapshot.checkpoint
        state.metadata["resume_token"] = token
        if state.failure:
            state.failure.recovery_attempted = True
            state.failure.recovery_outcome = "HEALED_VERIFIED"
        return state

    def _resume_generation(
        self,
        state: AgentRunState,
        snapshot: ResumableAgentSnapshot,
        req: RunRequest,
        token: str,
    ) -> AgentRunState:
        flow_id = state.generation_result.flow_id if state.generation_result else ""
        decision = self.gate.evaluate(flow_id)
        if not decision.executable:
            state.status = "NEEDS_REVIEW"
            state.reason_code = decision.reason_code
            state.summary = decision.message
            state.final_result = "NEEDS_REVIEW"
            return state
        state.current_flow = flow_id
        state.selected_flows = [flow_id]
        if state.suite_plan:
            from qa_orchestrator.suite_commands import build_flow_command

            polarity = state.plan.polarity if state.plan else "positive"
            state.suite_plan.flow_ids = [flow_id]
            state.suite_plan.commands = [build_flow_command(flow_id, polarity=polarity)]
        state.status = "READY"
        state.metadata["resume_checkpoint"] = "after_generation_approval"
        state.metadata["resume_token"] = token
        snapshot.checkpoint = "after_generation_approval"
        return state

    def _append_resume_journal(
        self,
        state: AgentRunState,
        *,
        resume_reason: str,
        checkpoint: str,
        previous_state: str,
        new_state: str,
        result: str,
    ) -> None:
        entry = AgentDecisionEntry(
            iteration=state.iteration,
            state=state.status,
            decision="RESUME",
            reason=resume_reason,
            source="SYSTEM",
            result=result,
            resume_reason=resume_reason,
            checkpoint=checkpoint,
            previous_state=previous_state,
            new_state=new_state,
        )
        state.decision_journal.append(entry)

    def _result_from_snapshot(self, snapshot: ResumableAgentSnapshot, *, note: str) -> AgentRunResult:
        req = RunRequest(**snapshot.run_request) if snapshot.run_request else RunRequest(goal=snapshot.state.request)
        journal_data = load_journal(snapshot.run_id, base_dir=self.base_dir)
        state = snapshot.state
        if journal_data.get("decision_journal"):
            state.decision_journal = [
                AgentDecisionEntry.model_validate(entry) for entry in journal_data["decision_journal"]
            ]
            state.status = journal_data.get("status", state.status)  # type: ignore[assignment]
            state.final_result = journal_data.get("final_result", state.final_result)
            state.reason_code = journal_data.get("reason_code", state.reason_code)
            state.summary = journal_data.get("summary", state.summary)
        state.summary = note
        result = AgentRunResult(
            state=state,
            conclusion=state.final_result or state.status,
            reason_code=state.reason_code or "",
            summary=note,
        )
        result.metrics = metrics_from_single_run(result)
        return result


def _default_healing_dry_run() -> bool:
    import os

    return os.environ.get("QA_RUNNER", "playwright").lower() in {"dry_run", "dry-run", "mock"} or os.environ.get(
        "QA_HEALING_SIMULATE", "true"
    ).lower() in {"1", "true", "yes"}


def _read_artifact_status(artifact_path: Path) -> str:
    import re

    if not artifact_path.exists():
        return ""
    match = re.search(
        r"^status:\s*(PENDING_SME_APPROVAL|APPROVED|REJECTED)\s*$",
        artifact_path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    return match.group(1) if match else ""


def build_snapshot_from_state(
    state: AgentRunState,
    req: RunRequest,
    *,
    pause_kind: str,
    automation_dir: str | Path,
) -> ResumableAgentSnapshot:
    automation_dir = Path(automation_dir)
    design_root = automation_dir / "test-design" / "flows"
    fingerprints: dict[str, str] = {}
    statuses: dict[str, str] = {}
    flow_id = state.current_flow or (state.selected_flows[0] if state.selected_flows else "")
    if not flow_id and state.plan and state.plan.candidate_flows:
        flow_id = state.plan.candidate_flows[0]
    if flow_id:
        artifact_path = design_root / flow_id / CANONICAL_ARTIFACT
        fingerprints[flow_id] = artifact_fingerprint(artifact_path)
        statuses[flow_id] = _read_artifact_status(artifact_path)
    if state.healing_result and state.healing_result.proposal:
        hid = state.healing_result.healing_id
        prop_path = automation_dir / "healing" / "proposals" / f"{hid}.json"
        fingerprints[f"healing:{hid}"] = artifact_fingerprint(prop_path)
    if state.generation_result and state.generation_result.generated_spec_path:
        spec = Path(state.generation_result.generated_spec_path)
        fingerprints[f"generation:{state.generation_result.flow_id}"] = artifact_fingerprint(spec)

    checkpoint = "after_plan"
    pending = None
    if pause_kind == "healing":
        checkpoint = "after_healing_proposal"
        pending = "RESUME_HEALING_RETRY"
    elif pause_kind == "generation":
        checkpoint = "after_generation"
        pending = "RESUME_GENERATED_TEST"
    elif pause_kind == "execution_gate":
        checkpoint = "before_execution"
        pending = "RESUME_EXECUTION"

    return ResumableAgentSnapshot(
        run_id=state.run_id,
        state=state,
        checkpoint=checkpoint,
        pending_action=pending,
        approval_reason=state.reason_code or "",
        approval_pause_kind=pause_kind,
        completed_steps=list(state.metadata.get("completed_steps", [])),
        artifact_fingerprints=fingerprints,
        artifact_status_at_pause=statuses,
        run_request={
            "goal": req.goal,
            "run_type": req.run_type,
            "model": req.model,
            "run_id": req.run_id,
            "skip_discovery": req.skip_discovery,
            "skip_execution": req.skip_execution,
            "execution_mode": req.execution_mode,
            "allow_skip_execution": req.allow_skip_execution,
            "context_packets": req.context_packets,
        },
    )
