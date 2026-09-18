"""P12 — Flow resolver and discovery selection tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qa_orchestrator.flow_intent import FLOW_SEARCH_PRODUCT, FLOW_VIEW_PRODUCT
from qa_orchestrator.flow_resolver import FlowResolver
from qa_orchestrator.gt_eval import goal_matches_gt
from qa_orchestrator.intent_classifier import IntentClassifier
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.llm_client import PlannerLlmClient
from qa_orchestrator.qa_planner import QaPlanner
from qa_orchestrator.suite_selector import SuiteSelector

REPO = Path(__file__).resolve().parents[2]
DISCOVERY = REPO / "data" / "discovery-kb"


@pytest.fixture(scope="module")
def graph() -> FlowKnowledgeGraph:
    return FlowKnowledgeGraph(discovery_root=str(DISCOVERY))


def test_search_sku_resolves_to_bf_product_003(graph: FlowKnowledgeGraph) -> None:
    goal = "Search SKU 552811DUDABA00"
    res = FlowResolver(graph, PlannerLlmClient(enabled=False)).resolve(goal)
    assert res.decision == "EXECUTE"
    assert res.primary_flow_id == FLOW_SEARCH_PRODUCT
    intent = IntentClassifier(graph, PlannerLlmClient(enabled=False)).classify(goal)
    plan = QaPlanner(graph, PlannerLlmClient(enabled=False)).plan(intent)
    suite = SuiteSelector(graph).select(plan.intent)
    assert plan.intent.flow_ids == [FLOW_SEARCH_PRODUCT]
    assert suite.primary_executable_flow_id == FLOW_SEARCH_PRODUCT


def test_view_product_resolves_to_bf_product_004(graph: FlowKnowledgeGraph) -> None:
    goal = "View product using SKU 552811DUDABA00"
    res = FlowResolver(graph, PlannerLlmClient(enabled=False)).resolve(goal)
    assert res.decision == "EXECUTE"
    assert res.primary_flow_id == FLOW_VIEW_PRODUCT
    assert FLOW_SEARCH_PRODUCT in res.supporting_flow_ids
    assert res.primary_flow_id != FLOW_SEARCH_PRODUCT
    intent = IntentClassifier(graph, PlannerLlmClient(enabled=False)).classify(goal)
    plan = QaPlanner(graph, PlannerLlmClient(enabled=False)).plan(intent)
    suite = SuiteSelector(graph).select(plan.intent)
    assert suite.primary_executable_flow_id == FLOW_VIEW_PRODUCT
    assert suite.primary_executable_flow_id != FLOW_SEARCH_PRODUCT


def test_product_search_gt_does_not_match_view_intent() -> None:
    fact = json.loads((DISCOVERY / "gt" / "gt-bf-product-003-positive.json").read_text(encoding="utf-8"))
    goal = "View product using SKU 552811DUDABA00"
    assert not goal_matches_gt(goal, fact, primary_flow_id=FLOW_VIEW_PRODUCT)


def test_stale_search_flow_as_primary_for_view_is_flow_mismatch(graph: FlowKnowledgeGraph) -> None:
    goal = "View product using SKU 552811DUDABA00"
    res = FlowResolver(graph, PlannerLlmClient(enabled=False)).resolve(
        goal,
        intent_flow_ids=[FLOW_SEARCH_PRODUCT],
    )
    assert res.mismatch_detected is True
    assert res.decision == "FLOW_MISMATCH"
    intent = IntentClassifier(graph, PlannerLlmClient(enabled=False)).classify(goal)
    intent = intent.model_copy(update={"flow_ids": [FLOW_SEARCH_PRODUCT]})
    plan = QaPlanner(graph, PlannerLlmClient(enabled=False)).plan(intent)
    assert plan.strategy == "BLOCK"
    assert plan.execution_allowed is False
    assert plan.flow_resolution["decision"] == "FLOW_MISMATCH"


def test_unknown_intent_discovery_required(graph: FlowKnowledgeGraph) -> None:
    goal = "Validate the orbital payroll reconciliation widget in module ZZZ-UNKNOWN"
    res = FlowResolver(graph, PlannerLlmClient(enabled=False)).resolve(goal, intent_flow_ids=[])
    assert res.decision == "DISCOVERY_REQUIRED"
    intent = IntentClassifier(graph, PlannerLlmClient(enabled=False)).classify(goal)
    intent = intent.model_copy(update={"flow_ids": []})
    plan = QaPlanner(graph, PlannerLlmClient(enabled=False)).plan(intent)
    assert plan.strategy == "EXPLORE"
    assert plan.execution_allowed is False
    assert plan.flow_resolution["decision"] == "DISCOVERY_REQUIRED"


def test_supporting_flow_not_business_verdict_primary(graph: FlowKnowledgeGraph) -> None:
    goal = "View product using SKU 552811DUDABA00"
    res = FlowResolver(graph, PlannerLlmClient(enabled=False)).resolve(goal)
    assert res.primary_flow_id == FLOW_VIEW_PRODUCT
    assert "BF-HOME-010-01" not in {res.primary_flow_id}
    assert res.primary_flow_id != FLOW_SEARCH_PRODUCT
