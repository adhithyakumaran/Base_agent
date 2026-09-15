"""P10.3 — deterministic failure / edge terminal states (dry-run)."""

from __future__ import annotations

from pathlib import Path

import pytest

from qa_orchestrator.agent_resume import AgentResumeError, AgentResumeService
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


def test_invalid_run_id_resume_raises():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    svc = AgentResumeService(orch)
    with pytest.raises(AgentResumeError, match="run"):
        svc.resume("agent-does-not-exist-000000")


def test_unapproved_login_waits_for_approval():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run_agent(RunRequest(goal="Check login", run_type="adhoc"))
    assert result.state.status == "WAITING_FOR_APPROVAL"
    assert result.state.plan is not None
    assert result.state.plan.execution_allowed is False


def test_search_flow_routes_without_hanging():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run_agent(
        RunRequest(goal="Search SKU ABC123", run_type="adhoc", skip_execution=True)
    )
    assert result.state.status in {
        "WAITING_FOR_APPROVAL",
        "NEEDS_REVIEW",
        "BLOCKED",
        "COMPLETED",
        "FAILED",
    }
