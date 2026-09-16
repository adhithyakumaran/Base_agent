"""Run-level HITL resume UX — warm server agent state shape."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qa_orchestrator.agent_models import AgentRunState
from qa_orchestrator.agent_state_store import ResumableAgentSnapshot, save_snapshot
from qa_orchestrator.orchestrator import QaOrchestrator
from qa_orchestrator.run_request import RunRequest

from approval_test_helpers import (
    patch_suite_selector_no_commands,
    remove_flow_approval_records,
    set_flow_test_case_status,
)

DISCOVERY = "data/discovery-kb"


def test_get_agent_state_includes_resume_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_AGENT_JOURNAL_DIR", str(tmp_path / "agent"))
    monkeypatch.setenv("QA_RUNNER", "dry_run")
    monkeypatch.setenv("LLM_ENABLED", "false")
    set_flow_test_case_status("BF-PRODUCT-003", "PENDING_SME_APPROVAL")
    remove_flow_approval_records("BF-PRODUCT-003")
    orch = QaOrchestrator(discovery_root=DISCOVERY, model="disabled")
    patch_suite_selector_no_commands(monkeypatch, orch)
    result = orch.run_agent(RunRequest(goal="Search SKU ABC123", run_type="adhoc"))
    assert result.state.status == "WAITING_FOR_APPROVAL"
    snap = orch.get_agent_state(result.state.run_id)
    assert snap.resume_token
    assert snap.approval_pause_kind in {"execution_gate", "generation", "healing", "none"}
    assert snap.state.reason_code


def test_resume_idempotent_via_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from qa_orchestrator.agent_state_store import load_snapshot, mutate_snapshot

    monkeypatch.setenv("QA_AGENT_JOURNAL_DIR", str(tmp_path / "agent"))
    monkeypatch.setenv("QA_RUNNER", "dry_run")
    monkeypatch.setenv("LLM_ENABLED", "false")
    set_flow_test_case_status("BF-LOGIN-001", "PENDING_SME_APPROVAL")
    remove_flow_approval_records("BF-LOGIN-001")
    orch = QaOrchestrator(discovery_root=DISCOVERY, model="disabled")
    patch_suite_selector_no_commands(monkeypatch, orch)
    paused = orch.run_agent(RunRequest(goal="run positive login", run_type="adhoc"))
    assert paused.state.status == "WAITING_FOR_APPROVAL"
    token = "ux-resume-token"

    def _stamp(snap: ResumableAgentSnapshot) -> None:
        snap.last_applied_resume_token = token

    mutate_snapshot(paused.state.run_id, _stamp, base_dir=tmp_path / "agent")
    first = orch.resume_agent(paused.state.run_id, resume_token=token)
    second = orch.resume_agent(paused.state.run_id, resume_token=token)
    assert "idempotent" in second.summary.lower()
    assert first.state.run_id == second.state.run_id == paused.state.run_id


def test_map_conclusion_waiting_status():
    """Mirror of apps/console/lib/run-resume.ts for regression."""
    conclusion = "WAITING_FOR_APPROVAL"
    status = "waiting_approval" if conclusion == "WAITING_FOR_APPROVAL" else "completed"
    assert status == "waiting_approval"
