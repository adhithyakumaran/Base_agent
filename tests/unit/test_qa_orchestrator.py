"""Tests for enterprise QA orchestrator (classify → select → execute)."""

from __future__ import annotations

import os

import pytest

from qa_orchestrator.flow_kb import YamlFlowKb
from qa_orchestrator.intent_classifier import IntentClassifier
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.llm_client import PlannerLlmClient
from qa_orchestrator.models import ExecutionPlan, PlanStep
from qa_orchestrator.openclaw_adapter import OpenClawAdapter
from qa_orchestrator.orchestrator import QaOrchestrator, RunRequest
from qa_orchestrator.planner import Planner
from qa_orchestrator.suite_selector import SuiteSelector
from qa_orchestrator.validator import Validator


DISCOVERY_ROOT = "discovery/uat_ea"
FLOWS_DIR = f"{DISCOVERY_ROOT}/flows"


@pytest.fixture(autouse=True)
def dry_run_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QA_RUNNER", "dry_run")
    monkeypatch.setenv("LLM_ENABLED", "false")


def test_yaml_flow_kb_loads_ready_flows():
    kb = YamlFlowKb(FLOWS_DIR)
    ready = kb.ready_flow_ids
    assert "BF-LOGIN-001" in ready
    assert len(ready) >= 19


def test_knowledge_graph_primary_vs_draft():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    ready = graph.ready_flow_ids()
    draft = graph.draft_flow_ids()
    assert "BF-LOGIN-001" in ready
    assert "BF-FINDPRICE-004" in draft
    assert graph._is_primary("BF-FINDPRICE-004") is False


def test_intent_classifier_morning_sanity():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    classifier = IntentClassifier(graph, PlannerLlmClient(enabled=False))
    intent = classifier.classify("morning sanity check endless aisle", run_type="sanity")
    assert intent.execution_mode == "morning_sanity"
    assert intent.classifier.startswith("deterministic")


def test_intent_classifier_parameterized_sku():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    classifier = IntentClassifier(graph, PlannerLlmClient(enabled=False))
    intent = classifier.classify("SKU ABC12345 returns 404 in product search")
    assert intent.execution_mode == "adhoc_parameterized"
    assert intent.params.get("sku") == "abc12345"


def test_suite_selector_picks_sanity():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    classifier = IntentClassifier(graph, PlannerLlmClient(enabled=False))
    intent = classifier.classify("morning sanity", run_type="sanity")
    plan = SuiteSelector(graph).select(intent)
    assert "SUITE-SANITY-MORNING" in plan.suite_ids
    assert plan.commands == ["npm run test:sanity"]
    assert len(plan.flow_ids) >= 19


def test_suite_selector_login_flow():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    classifier = IntentClassifier(graph, PlannerLlmClient(enabled=False))
    intent = classifier.classify("verify login works")
    plan = SuiteSelector(graph).select(intent)
    assert "BF-LOGIN-001" in plan.flow_ids
    assert any("BF-LOGIN-001" in c for c in plan.commands)


def test_planner_backward_compat_plan():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    planner = Planner(graph, PlannerLlmClient(enabled=False))
    plan = planner.plan("check reports module", run_type="adhoc")
    assert plan.planner.startswith("deterministic")
    assert any("BF-REPORTS" in ref for ref in plan.kb_refs)


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


def test_orchestrator_sanity_run_dry_run():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    payload = orch.to_agent_payload(
        orch.run(RunRequest(goal="morning sanity check endless aisle", run_type="sanity", model="disabled"))
    )
    assert payload["conclusion"] in {"NEEDS_REVIEW", "FAIL", "PASS"}
    assert payload["local"]["execution_mode"] == "morning_sanity"
    assert payload["llm_calls"] == 0
    assert payload["local"]["orchestrator"] == "qa_orchestrator"
    assert payload["local"]["executor"] == "playwright_dry_run"
    assert payload["local"]["suite_plan"]["suite_ids"] == ["SUITE-SANITY-MORNING"]


def test_orchestrator_new_feature_includes_discovery():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run(RunRequest(goal="new banner added on product page", model="disabled"))
    assert result.intent.execution_mode == "new_feature"
    assert result.discovery is not None
    assert result.discovery.mode == "dry_run"


def test_validator_phase_a_needs_review():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    from qa_orchestrator.kb_rag import KbRag

    kb = KbRag(f"{DISCOVERY_ROOT}/kb")
    validator = Validator(kb)
    plan = ExecutionPlan(goal="g", steps=[PlanStep(action="custom", target="suite")])
    execution = OpenClawAdapter(mode="mock").run_plan(plan)
    v = validator.validate(goal="sanity check", run_type="sanity", plan=plan, execution=execution)
    assert v.phase == "A"
    assert v.conclusion == "NEEDS_REVIEW"
