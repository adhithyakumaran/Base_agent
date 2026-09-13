"""P6.1 — agent resume, state persistence, metrics, and legacy guard tests."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from qa_orchestrator.agent_eval import (
    P61_RESUME_SCENARIOS,
    evaluate_scenario,
    run_agent_evaluation,
    run_p61_resume_evaluation,
)
from qa_orchestrator.agent_metrics import aggregate_eval_metrics
from qa_orchestrator.agent_models import AgentDecisionEntry, AgentRunState
from qa_orchestrator.agent_resume import AgentResumeError, AgentResumeService, build_snapshot_from_state
from qa_orchestrator.agent_state_store import STATE_SCHEMA_VERSION, load_snapshot, save_snapshot, state_path
from qa_orchestrator.healing_proposal_store import load_proposal, save_proposal, update_proposal_status
from qa_orchestrator.legacy_guard import assert_canonical_agent_path, legacy_runtime_requested
from qa_orchestrator.models import HealingProposal, HealingResult
from qa_orchestrator.orchestrator import QaOrchestrator
from qa_orchestrator.run_request import RunRequest

DISCOVERY_ROOT = "data/discovery-kb"


@pytest.fixture(autouse=True)
def agent_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("QA_RUNNER", "dry_run")
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("QA_QDRANT_ENABLED", "false")
    monkeypatch.setenv("QA_EMBEDDING_PROVIDER", "deterministic")
    monkeypatch.setenv("QA_AGENT_JOURNAL_DIR", str(tmp_path / "agent-journals"))
    monkeypatch.setenv("QA_USE_LEGACY_AGENT_RUNTIME", "false")
    _reset_login_artifact()


def _reset_login_artifact() -> None:
    artifact = Path("apps/automation/test-design/flows/BF-LOGIN-001/test-cases.yaml")
    if artifact.exists():
        text = artifact.read_text(encoding="utf-8")
        text = re.sub(r"^status:\s*APPROVED\s*$", "status: PENDING_SME_APPROVAL", text, flags=re.MULTILINE)
        text = re.sub(r"^status:\s*REJECTED\s*$", "status: PENDING_SME_APPROVAL", text, flags=re.MULTILINE)
        artifact.write_text(text, encoding="utf-8")
    approval_log = Path("apps/automation/approval/approval-log.json")
    if approval_log.exists():
        approval_log.unlink()


def _approve_flow(orch: QaOrchestrator, flow_id: str) -> None:
    automation = Path(orch.graph.automation_dir)
    artifact = automation / "test-design" / "flows" / flow_id / "test-cases.yaml"
    text = artifact.read_text(encoding="utf-8")
    text = re.sub(r"^status:\s*PENDING_SME_APPROVAL\s*$", "status: APPROVED", text, flags=re.MULTILINE)
    artifact.write_text(text, encoding="utf-8")
    log_dir = automation / "approval"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "approval-log.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "flowId": flow_id,
                        "artifact": "test-cases.yaml",
                        "status": "APPROVED",
                        "approver": "sme@test.com",
                        "decidedAt": datetime.now(timezone.utc).isoformat(),
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _approve_healing(orch: QaOrchestrator, healing_id: str) -> None:
    update_proposal_status(Path(orch.graph.automation_dir), healing_id, "APPROVED")


def test_waiting_run_persists_state_json():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run_agent(RunRequest(goal="Check login", model="disabled"))
    assert result.state.status == "WAITING_FOR_APPROVAL"
    path = state_path(orch.agent_loop.config.journal_dir, result.state.run_id)
    assert path.exists()
    snapshot = load_snapshot(result.state.run_id, base_dir=orch.agent_loop.config.journal_dir)
    assert snapshot.schema_version == STATE_SCHEMA_VERSION
    assert snapshot.approval_pause_kind == "execution_gate"


def test_resume_rejects_missing_state():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    with pytest.raises(AgentResumeError, match="not resumable"):
        orch.resume_agent("missing-run-id")


def test_resume_rejects_corrupt_state(tmp_path: Path):
    run_id = "agent-corrupt"
    bad = tmp_path / "agent-journals" / run_id / "state.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{not json", encoding="utf-8")
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    with pytest.raises(AgentResumeError, match="corrupt"):
        orch.resume_agent(run_id)


def test_resume_rejects_incompatible_schema(tmp_path: Path):
    run_id = "agent-schema"
    path = tmp_path / "agent-journals" / run_id / "state.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"schema_version": "p0-v1", "run_id": run_id, "state": {"run_id": run_id, "request": "x"}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="incompatible"):
        load_snapshot(run_id, base_dir=tmp_path / "agent-journals")


def test_resume_idempotent_token():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    paused = orch.run_agent(RunRequest(goal="Check login", model="disabled", run_id="agent-resume-idem"))
    _approve_flow(orch, "BF-LOGIN-001")
    token = "fixed-token"
    first = orch.resume_agent(paused.state.run_id, resume_token=token)
    second = orch.resume_agent(paused.state.run_id, resume_token=token)
    assert first.conclusion == second.conclusion
    resume_entries = [e for e in second.state.decision_journal if e.decision == "RESUME"]
    assert len(resume_entries) == 1


def test_resume_after_terminal_fails():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run_agent(
        RunRequest(goal="morning sanity check endless aisle", run_type="sanity", model="disabled")
    )
    assert result.state.status in {"FAILED", "COMPLETED", "NEEDS_REVIEW"}
    with pytest.raises(AgentResumeError, match="not resumable"):
        orch.resume_agent(result.state.run_id)


def test_stale_artifact_on_resume_needs_review():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    paused = orch.run_agent(RunRequest(goal="Check login", model="disabled", run_id="agent-stale"))
    _approve_flow(orch, "BF-LOGIN-001")
    snapshot = load_snapshot(paused.state.run_id, base_dir=orch.agent_loop.config.journal_dir)
    snapshot.artifact_status_at_pause["BF-LOGIN-001"] = "APPROVED"
    snapshot.artifact_fingerprints["BF-LOGIN-001"] = "deadbeefdeadbeef"
    save_snapshot(snapshot, base_dir=orch.agent_loop.config.journal_dir)
    resumed = orch.resume_agent(paused.state.run_id)
    assert resumed.conclusion == "NEEDS_REVIEW"
    assert any(entry.decision == "RESUME" for entry in resumed.state.decision_journal)


def test_journal_continuity_on_resume():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    paused = orch.run_agent(RunRequest(goal="Check login", model="disabled"))
    before = len(paused.state.decision_journal)
    _approve_flow(orch, "BF-LOGIN-001")
    resumed = orch.resume_agent(paused.state.run_id, resume_token="once")
    assert len(resumed.state.decision_journal) >= before + 1
    assert resumed.state.run_id == paused.state.run_id
    resume_entry = next(e for e in resumed.state.decision_journal if e.decision == "RESUME")
    assert resume_entry.checkpoint
    assert resume_entry.previous_state == "WAITING_FOR_APPROVAL"


def test_approval_pause_then_resume_executes():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    paused = orch.run_agent(RunRequest(goal="Check login", model="disabled", run_id="agent-exec-resume"))
    assert paused.state.status == "WAITING_FOR_APPROVAL"
    _approve_flow(orch, "BF-LOGIN-001")
    resumed = orch.resume_agent(paused.state.run_id)
    assert "RUN_EXISTING_TEST" in [e.decision for e in resumed.state.decision_journal]
    assert resumed.state.run_id == paused.state.run_id


def test_healing_approval_resume_uses_overlay(tmp_path: Path):
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    base = orch.run_agent(
        RunRequest(goal="morning sanity check endless aisle", run_type="sanity", model="disabled", run_id="agent-heal")
    )
    healing_id = "heal-resume-test"
    proposal = HealingProposal(
        healing_id=healing_id,
        flow_id="BF-LOGIN-001",
        test_id="TC-BF-LOGIN-001-P01",
        locator_label="login button",
        old_locator="page.getByTestId('login')",
        new_locator="page.getByRole('button', { name: 'Login' })",
        fallbacks=['button[name="login"]'],
        confidence=0.9,
        status="PENDING_SME_APPROVAL",
    )
    save_proposal(Path(orch.graph.automation_dir), proposal)
    base.state.healing_result = HealingResult(
        healing_id=healing_id,
        status="HEALED_PENDING_APPROVAL",
        proposal=proposal,
        message="Healing proposal pending SME approval",
    )
    base.state.status = "WAITING_FOR_APPROVAL"
    base.state.final_result = "WAITING_FOR_APPROVAL"
    base.state.reason_code = "healing.pending_approval"
    base.state.metadata["approval_pause_kind"] = "healing"
    req = RunRequest(goal=base.state.request, run_type=base.state.run_type)
    snapshot = build_snapshot_from_state(base.state, req, pause_kind="healing", automation_dir=orch.graph.automation_dir)
    save_snapshot(snapshot, base_dir=orch.agent_loop.config.journal_dir)
    orch.agent_loop._finalize(base.state, req, started=0.0)  # type: ignore[attr-defined]
    update_proposal_status(Path(orch.graph.automation_dir), healing_id, "APPROVED")
    from qa_orchestrator.healing_overlay import apply_approved_proposal

    approved = load_proposal(Path(orch.graph.automation_dir), healing_id)
    assert approved is not None
    apply_approved_proposal(Path(orch.graph.automation_dir), approved)
    resumed = orch.resume_agent("agent-heal")
    assert resumed.state.run_id == "agent-heal"
    assert any(e.decision == "RESUME" for e in resumed.state.decision_journal)


def test_generated_test_resume_after_approval():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    paused = orch.run_agent(
        RunRequest(
            goal="Discover the product page and create automated coverage",
            model="disabled",
            skip_execution=True,
            run_id="agent-gen-resume",
        )
    )
    assert paused.state.status == "WAITING_FOR_APPROVAL"
    assert paused.state.generation_result is not None
    flow_id = paused.state.generation_result.flow_id
    _approve_flow(orch, flow_id)
    snapshot = load_snapshot("agent-gen-resume", base_dir=orch.agent_loop.config.journal_dir)
    snapshot.approval_pause_kind = "generation"
    save_snapshot(snapshot, base_dir=orch.agent_loop.config.journal_dir)
    resumed = orch.resume_agent("agent-gen-resume")
    assert resumed.state.run_id == "agent-gen-resume"
    assert any(e.decision == "RESUME" for e in resumed.state.decision_journal)


def test_evidence_stays_in_same_run_directory(tmp_path: Path):
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    paused = orch.run_agent(RunRequest(goal="Check login", model="disabled", run_id="agent-evidence"))
    run_dir = Path(orch.agent_loop.config.journal_dir) / "agent-evidence"
    assert run_dir.exists()
    _approve_flow(orch, "BF-LOGIN-001")
    resumed = orch.resume_agent("agent-evidence")
    assert Path(orch.agent_loop.config.journal_dir) / resumed.state.run_id == run_dir
    assert (run_dir / "state.json").exists()
    assert (run_dir / "journal.json").exists()


def test_resume_when_gate_blocked_needs_review():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    paused = orch.run_agent(RunRequest(goal="Check login", model="disabled", run_id="agent-gate-block"))
    artifact = Path(orch.graph.automation_dir) / "test-design" / "flows" / "BF-LOGIN-001" / "test-cases.yaml"
    artifact.write_text("flow_id: BF-LOGIN-001\nstatus: REJECTED\n", encoding="utf-8")
    resumed = orch.resume_agent("agent-gate-block")
    assert resumed.conclusion == "NEEDS_REVIEW"


def test_metrics_distinguish_waiting_from_execution_success():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    waiting = orch.run_agent(RunRequest(goal="Check login", model="disabled"))
    sanity = orch.run_agent(
        RunRequest(goal="morning sanity check endless aisle", run_type="sanity", model="disabled")
    )
    from qa_orchestrator.agent_eval import AgentEvalScenario

    rows = [
        evaluate_scenario(
            waiting,
            AgentEvalScenario(
                id="w",
                goal="Check login",
                expected_outcome="WAITING_FOR_APPROVAL",
                expected_terminal_states=("WAITING_FOR_APPROVAL",),
                expected_approval=True,
            ),
        ),
        evaluate_scenario(
            sanity,
            AgentEvalScenario(
                id="s",
                goal="morning sanity check endless aisle",
                expected_outcome="FAIL",
                expected_terminal_states=("FAILED", "COMPLETED", "NEEDS_REVIEW"),
            ),
        ),
    ]
    metrics = aggregate_eval_metrics(rows)
    assert metrics["waiting_for_approval_rate"] == 0.5
    assert metrics["execution_attempt_rate"] == 0.5
    assert metrics["execution_attempt_success_rate"] <= 1.0


def test_legacy_runtime_blocked_on_canonical_cli(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_USE_LEGACY_AGENT_RUNTIME", "true")
    with pytest.raises(RuntimeError, match="ControlledAgentLoop"):
        assert_canonical_agent_path("agent_cli")


def test_canonical_cli_does_not_import_legacy_runtime():
    import qa_orchestrator.agent_cli as cli
    import qa_orchestrator.orchestrator as orch_mod

    assert "ControlledAgentLoop" in str(orch_mod.ControlledAgentLoop)
    assert not legacy_runtime_requested()
    assert hasattr(cli, "cmd_run")


def test_agent_cli_subcommand_not_legacy_runtime():
    proc = subprocess.run(
        ["python3", "-m", "qa_orchestrator.agent_cli", "--json", "run", "Check login"],
        cwd="/workspace",
        env={
            **dict(__import__("os").environ),
            "PYTHONPATH": "services/qa-orchestrator",
            "QA_RUNNER": "dry_run",
            "LLM_ENABLED": "false",
            "QA_QDRANT_ENABLED": "false",
            "QA_EMBEDDING_PROVIDER": "deterministic",
            "QA_USE_LEGACY_AGENT_RUNTIME": "false",
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["agent"]["canonical"]["orchestrator_path"].endswith("ControlledAgentLoop")
    assert payload["agent"]["canonical"]["legacy_runtime_canonical"] == "false"


def test_morning_patrol_uses_legacy_not_canonical_agent_cli():
    source = Path("/workspace/scripts/morning_patrol.py").read_text(encoding="utf-8")
    assert "base_agent" in source
    assert "agent_cli" not in source
    assert "ControlledAgentLoop" not in source


def test_get_agent_state_via_orchestrator():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run_agent(RunRequest(goal="Check login", model="disabled"))
    snapshot = orch.get_agent_state(result.state.run_id)
    assert snapshot.state.status == "WAITING_FOR_APPROVAL"


def test_build_snapshot_includes_run_request():
    state = AgentRunState(run_id="x", request="goal", status="WAITING_FOR_APPROVAL")
    req = RunRequest(goal="goal", run_type="adhoc")
    snap = build_snapshot_from_state(state, req, pause_kind="execution_gate", automation_dir="apps/automation")
    assert snap.run_request["goal"] == "goal"


def test_p61_resume_eval_scenario_count():
    assert len(P61_RESUME_SCENARIOS) == 13


def test_p61_resume_evaluation_runner():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    report = run_p61_resume_evaluation(orch)
    assert report["total"] == 13
    assert report["passed"] >= 10
    assert "planning_success_rate" in report["metrics"]
    assert "execution_attempt_rate" in report["metrics"]
    assert "waiting_for_approval_rate" in report["metrics"]
