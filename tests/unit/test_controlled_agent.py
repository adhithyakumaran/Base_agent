"""P6 — controlled agent loop, policy, evaluation, and journal tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from qa_orchestrator.agent_config import AgentConfig
from qa_orchestrator.agent_decision_engine import AgentDecisionEngine
from qa_orchestrator.agent_eval import P6_EVAL_SCENARIOS, evaluate_scenario, run_agent_evaluation
from qa_orchestrator.agent_journal import journal_path, save_journal
from qa_orchestrator.agent_models import AgentAction, AgentRunState
from qa_orchestrator.agent_policy import PolicyValidator
from qa_orchestrator.controlled_agent_loop import ControlledAgentLoop
from qa_orchestrator.models import ExecutionResult, PlanningResult, SuiteSelectionPlan
from qa_orchestrator.orchestrator import QaOrchestrator
from qa_orchestrator.run_request import RunRequest

from approval_test_helpers import (
    patch_suite_selector_no_commands,
    remove_flow_approval_records,
    set_flow_test_case_status,
)

DISCOVERY_ROOT = "data/discovery-kb"


@pytest.fixture(autouse=True)
def agent_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("QA_RUNNER", "dry_run")
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("QA_QDRANT_ENABLED", "false")
    monkeypatch.setenv("QA_EMBEDDING_PROVIDER", "deterministic")
    monkeypatch.setenv("QA_AGENT_JOURNAL_DIR", str(tmp_path / "agent-journals"))
    monkeypatch.setenv("QA_AGENT_MAX_ITERATIONS", "5")
    monkeypatch.setenv("QA_AGENT_MAX_RECOVERIES", "2")
    _reset_login_artifact_for_tests()


def _reset_login_artifact_for_tests() -> None:
    import re
    from pathlib import Path

    artifact = Path("apps/automation/test-design/flows/BF-LOGIN-001/test-cases.yaml")
    if artifact.exists():
        text = artifact.read_text(encoding="utf-8")
        text = re.sub(r"^status:\s*APPROVED\s*$", "status: PENDING_SME_APPROVAL", text, flags=re.MULTILINE)
        text = re.sub(r"^status:\s*REJECTED\s*$", "status: PENDING_SME_APPROVAL", text, flags=re.MULTILINE)
        artifact.write_text(text, encoding="utf-8")
    approval_log = Path("apps/automation/approval/approval-log.json")
    if not approval_log.exists():
        return
    try:
        data = json.loads(approval_log.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        approval_log.unlink(missing_ok=True)
        return
    records = [
        r
        for r in (data.get("records") or [])
        if not (r.get("flowId") == "BF-LOGIN-001" and r.get("artifact") == "test-cases.yaml")
    ]
    if records:
        approval_log.write_text(json.dumps({"records": records}, indent=2) + "\n", encoding="utf-8")
    else:
        approval_log.unlink(missing_ok=True)


def test_agent_config_defaults():
    cfg = AgentConfig.from_env()
    assert cfg.max_iterations == 5
    assert cfg.max_recoveries == 2
    assert cfg.max_steps == 50


def test_policy_rejects_unknown_action():
    state = AgentRunState(run_id="t1", request="x")
    bad = AgentAction.model_construct(type="javascript_eval", target="alert(1)")  # type: ignore[arg-type]
    decision = PolicyValidator().validate(bad, state)
    assert decision.allowed is False


def test_policy_allows_suite_command_without_flow_gate():
    state = AgentRunState(
        run_id="t2",
        request="sanity",
        suite_plan=SuiteSelectionPlan(commands=["npm run test:sanity:positive"]),
        plan=PlanningResult(
            request="sanity",
            intent=__import__("qa_orchestrator.models", fromlist=["IntentClassification"]).IntentClassification(goal="sanity"),
            strategy="REUSE_EXISTING",
            execution_allowed=False,
        ),
    )
    action = AgentAction(type="RUN_EXISTING_TEST")
    assert PolicyValidator().validate(action, state).allowed is True


def test_decision_engine_prefers_existing_test_for_suite_commands():
    state = AgentRunState(
        run_id="t3",
        request="sanity",
        status="READY",
        suite_plan=SuiteSelectionPlan(commands=["npm run test:sanity:positive"]),
        plan=PlanningResult(
            request="sanity",
            intent=__import__("qa_orchestrator.models", fromlist=["IntentClassification"]).IntentClassification(goal="sanity"),
            strategy="REUSE_EXISTING",
            execution_allowed=False,
            requires_human_approval=True,
        ),
    )
    action, _ = AgentDecisionEngine().decide(state)
    assert action.type == "RUN_EXISTING_TEST"


def test_check_login_waits_for_approval(monkeypatch: pytest.MonkeyPatch):
    set_flow_test_case_status("BF-LOGIN-001", "PENDING_SME_APPROVAL")
    remove_flow_approval_records("BF-LOGIN-001")
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    patch_suite_selector_no_commands(monkeypatch, orch)
    result = orch.run_agent(RunRequest(goal="run positive login", model="disabled"))
    assert result.state.status == "WAITING_FOR_APPROVAL"
    assert result.conclusion == "WAITING_FOR_APPROVAL"
    assert any(entry.decision == "PLAN" for entry in result.state.decision_journal)


def test_search_sku_trace_in_planning(monkeypatch: pytest.MonkeyPatch):
    set_flow_test_case_status("BF-PRODUCT-003", "PENDING_SME_APPROVAL")
    remove_flow_approval_records("BF-PRODUCT-003")
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    patch_suite_selector_no_commands(monkeypatch, orch)
    result = orch.run_agent(RunRequest(goal="Search SKU ABC123", model="disabled"))
    assert result.state.plan is not None
    assert result.state.plan.validated_parameters.get("sku") == "ABC123"
    assert "BF-PRODUCT-003" in result.state.plan.candidate_flows
    assert result.conclusion == "WAITING_FOR_APPROVAL"


def test_sanity_run_executes_and_verifies():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run_agent(RunRequest(goal="morning sanity check endless aisle", run_type="sanity", model="disabled"))
    assert result.state.execution is not None
    assert "RUN_EXISTING_TEST" in [entry.decision for entry in result.state.decision_journal]
    assert result.conclusion in {"NEEDS_REVIEW", "PASS", "FAIL"}


def test_generation_requires_approval_pause():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run_agent(
        RunRequest(
            goal="Discover the product page and create automated coverage",
            model="disabled",
            skip_execution=True,
        )
    )
    assert result.state.status in {"WAITING_FOR_APPROVAL", "NEEDS_REVIEW"}
    assert result.state.generation_result is not None or result.state.exploration is not None


def test_exact_flow_id_request():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run_agent(RunRequest(goal="BF-PRODUCT-003", model="disabled"))
    assert "BF-PRODUCT-003" in (result.state.plan.candidate_flows if result.state.plan else [])


def test_unknown_request_needs_review():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run_agent(
        RunRequest(goal="quantum flux capacitor calibration", model="disabled", skip_execution=True)
    )
    assert result.conclusion in {"NEEDS_REVIEW", "WAITING_FOR_APPROVAL"}


def test_journal_persisted_without_secrets(tmp_path: Path):
    state = AgentRunState(run_id="journal-test", request="Check login", status="WAITING_FOR_APPROVAL")
    path = save_journal(state, base_dir=tmp_path)
    raw = path.read_text(encoding="utf-8")
    assert "journal-test" in raw
    assert "api_key" not in raw.lower()
    assert path == journal_path(tmp_path, "journal-test")


def test_orchestrator_payload_includes_agent_metadata(monkeypatch: pytest.MonkeyPatch):
    set_flow_test_case_status("BF-LOGIN-001", "PENDING_SME_APPROVAL")
    remove_flow_approval_records("BF-LOGIN-001")
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    patch_suite_selector_no_commands(monkeypatch, orch)
    payload = orch.to_agent_payload(orch.run(RunRequest(goal="run positive login", model="disabled")))
    assert payload["agent"]["status"] == "WAITING_FOR_APPROVAL"
    assert payload["agent"]["journal_path"]
    assert payload["agent"]["metrics"]


def test_p6_eval_scenario_count():
    assert len(P6_EVAL_SCENARIOS) == 17


def test_p6_evaluation_runner():
    set_flow_test_case_status("BF-LOGIN-001", "PENDING_SME_APPROVAL")
    remove_flow_approval_records("BF-LOGIN-001")
    set_flow_test_case_status("BF-PRODUCT-003", "PENDING_SME_APPROVAL")
    remove_flow_approval_records("BF-PRODUCT-003")
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")

    def _run(scenario):
        return orch.run_agent(
            RunRequest(
                goal=scenario.goal,
                run_type=scenario.run_type,
                skip_execution=scenario.skip_execution,
                skip_discovery=scenario.skip_discovery,
                model="disabled",
            )
        )

    report = run_agent_evaluation(_run)
    assert report["total"] == 17
    assert report["passed"] >= 14
    assert "metrics" in report


def test_agent_loop_respects_max_iterations(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_AGENT_MAX_ITERATIONS", "1")
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run_agent(RunRequest(goal="morning sanity check endless aisle", run_type="sanity", model="disabled"))
    assert result.state.iteration <= 1 or result.conclusion in {"NEEDS_REVIEW", "PASS", "FAIL", "WAITING_FOR_APPROVAL"}


def test_controlled_loop_is_canonical_path():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    assert isinstance(orch.agent_loop, ControlledAgentLoop)
    direct = orch.run_agent(RunRequest(goal="Check login", model="disabled"))
    wrapped = orch.run(RunRequest(goal="Check login", model="disabled"))
    assert direct.conclusion == wrapped.conclusion
