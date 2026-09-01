"""Tests for simplified QA orchestrator."""

from __future__ import annotations

from qa_orchestrator.kb_rag import KbRag
from qa_orchestrator.openclaw_adapter import OpenClawAdapter
from qa_orchestrator.orchestrator import QaOrchestrator, RunRequest
from qa_orchestrator.planner import Planner
from qa_orchestrator.llm_client import PlannerLlmClient
from qa_orchestrator.models import ExecutionPlan, PlanStep
from qa_orchestrator.validator import Validator


KB_DIR = "discovery/uat_ea/kb"


def test_kb_rag_finds_login_flow():
    kb = KbRag(KB_DIR)
    hits = kb.search("login home endless aisle")
    ids = [h["id"] for h in hits]
    assert any("login" in i for i in ids)


def test_deterministic_sanity_plan():
    kb = KbRag(KB_DIR)
    llm = PlannerLlmClient(enabled=False)
    planner = Planner(kb, llm)
    plan = planner.plan("sanity check endless aisle", run_type="sanity")
    assert plan.planner.startswith("deterministic")
    assert len(plan.steps) >= 5
    assert plan.steps[0].action == "navigate"


def test_openclaw_mock_execution():
    adapter = OpenClawAdapter(mode="mock")
    plan = ExecutionPlan(
        goal="test",
        steps=[
            PlanStep(action="navigate", target="https://example.com"),
            PlanStep(action="screenshot", target="page"),
        ],
    )
    result = adapter.run_plan(plan)
    assert result.mode == "mock"
    assert len(result.observations) == 2
    assert result.ok is True


def test_orchestrator_sanity_run():
    orch = QaOrchestrator(kb_dir=KB_DIR, model="disabled")
    payload = orch.to_agent_payload(
        orch.run(RunRequest(goal="sanity check endless aisle", run_type="sanity", model="disabled"))
    )
    assert payload["conclusion"] in {"NEEDS_REVIEW", "FAIL", "PASS"}
    assert payload["steps"] >= 5
    assert payload["llm_calls"] == 0
    assert payload["local"]["orchestrator"] == "qa_orchestrator"
    assert payload["local"]["openclaw_mode"] == "mock"


def test_validator_phase_a_needs_review():
    kb = KbRag(KB_DIR)
    validator = Validator(kb)
    plan = ExecutionPlan(goal="g", steps=[PlanStep(action="navigate", target="x")])
    from qa_orchestrator.openclaw_adapter import OpenClawAdapter

    execution = OpenClawAdapter(mode="mock").run_plan(plan)
    v = validator.validate(goal="sanity check", run_type="sanity", plan=plan, execution=execution)
    assert v.phase == "A"
    assert v.conclusion == "NEEDS_REVIEW"
