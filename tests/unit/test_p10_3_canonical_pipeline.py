"""P10.3 — canonical pipeline dry-run validation (Search SKU path)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qa_orchestrator.orchestrator import QaOrchestrator
from qa_orchestrator.run_request import RunRequest

DISCOVERY_ROOT = "data/discovery-kb"


@pytest.fixture(autouse=True)
def dry_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("QA_RUNNER", "dry_run")
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("QA_QDRANT_ENABLED", "false")
    monkeypatch.setenv("QA_EMBEDDING_PROVIDER", "deterministic")
    monkeypatch.setenv("QA_AGENT_JOURNAL_DIR", str(tmp_path / "agent"))


def test_search_sku_canonical_pipeline_stages():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run_agent(
        RunRequest(goal="Search SKU ABC123 in endless aisle", run_type="adhoc", skip_execution=True)
    )
    state = result.state
    assert state.run_id
    planning = state.plan
    assert planning is not None
    assert "BF-PRODUCT-003" in planning.candidate_flows or "BF-PRODUCT-003" in (planning.selected_flows or [])
    assert state.status in {"WAITING_FOR_APPROVAL", "COMPLETED", "NEEDS_REVIEW", "FAILED", "BLOCKED"}
    meta = result.orchestrator_metadata
    assert meta.get("llm_enabled") is False or meta.get("llm_enabled") == "false"


def test_restart_resume_no_duplicate_steps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from qa_orchestrator.agent_state_store import load_snapshot, mutate_snapshot

    journal = tmp_path / "agent"
    monkeypatch.setenv("QA_AGENT_JOURNAL_DIR", str(journal))
    orch1 = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    agent_result = orch1.run_agent(RunRequest(goal="Check login", run_type="adhoc"))
    run_id = agent_result.state.run_id
    token = "resume-token-p10-3"

    def _stamp_token(snap):
        snap.last_applied_resume_token = token

    mutate_snapshot(run_id, _stamp_token, base_dir=journal)

    orch2 = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    first = orch2.resume_agent(run_id, resume_token=token, resume_reason="test")
    snap_after_first = load_snapshot(run_id, base_dir=journal)
    second = orch2.resume_agent(run_id, resume_token=token, resume_reason="test")
    assert "idempotent" in second.summary.lower()
    snap_after_second = load_snapshot(run_id, base_dir=journal)
    assert snap_after_second.last_applied_resume_token == token
    assert len(snap_after_second.state.decision_journal) == len(snap_after_first.state.decision_journal)


def test_concurrent_dry_runs_isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    journal = tmp_path / "agent"
    monkeypatch.setenv("QA_AGENT_JOURNAL_DIR", str(journal))
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    r1 = orch.run_agent(RunRequest(goal="Check login", run_type="adhoc"))
    r2 = orch.run_agent(RunRequest(goal="Search SKU ABC123", run_type="adhoc"))
    assert r1.state.run_id != r2.state.run_id
    p1 = journal / r1.state.run_id / "state.json"
    p2 = journal / r2.state.run_id / "state.json"
    assert p1.exists() and p2.exists()
    assert json.loads(p1.read_text())["run_id"] != json.loads(p2.read_text())["run_id"]
