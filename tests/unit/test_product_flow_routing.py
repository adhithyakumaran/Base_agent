"""Product search vs view-product routing and GT matching regressions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qa_orchestrator.gt_eval import goal_matches_gt
from qa_orchestrator.intent_classifier import IntentClassifier
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.llm_client import PlannerLlmClient
from qa_orchestrator.models import ExecutionPlan, ExecutionResult, StepObservation
from qa_orchestrator.suite_commands import build_flow_command
from qa_orchestrator.suite_selector import SuiteSelector
from qa_orchestrator.validator import Validator
from qa_orchestrator.kb_rag import KbRag

REPO = Path(__file__).resolve().parents[2]
DISCOVERY = REPO / "data" / "discovery-kb"


@pytest.fixture(scope="module")
def graph() -> FlowKnowledgeGraph:
    return FlowKnowledgeGraph(discovery_root=str(DISCOVERY))


def test_search_sku_routes_to_bf_product_003(graph: FlowKnowledgeGraph) -> None:
    goal = "Search SKU 552811DUDABA00"
    intent = IntentClassifier(graph, PlannerLlmClient(enabled=False)).classify(goal)
    plan = SuiteSelector(graph).select(intent)
    assert intent.flow_ids == ["BF-PRODUCT-003"]
    assert plan.primary_executable_flow_id == "BF-PRODUCT-003"
    assert plan.commands == [build_flow_command("BF-PRODUCT-003", polarity="positive")]


def test_view_product_sku_routes_to_bf_product_004(graph: FlowKnowledgeGraph) -> None:
    goal = "View product using SKU 552811DUDABA00"
    intent = IntentClassifier(graph, PlannerLlmClient(enabled=False)).classify(goal)
    plan = SuiteSelector(graph).select(intent)
    assert intent.flow_ids == ["BF-PRODUCT-004"]
    assert "BF-PRODUCT-003" in intent.supporting_flow_ids or "BF-PRODUCT-003" in plan.supporting_flow_ids
    assert plan.primary_executable_flow_id == "BF-PRODUCT-004"
    assert plan.commands == [build_flow_command("BF-PRODUCT-004", polarity="positive")]


def test_gt_003_does_not_match_view_product_intent() -> None:
    fact = json.loads((DISCOVERY / "gt" / "gt-bf-product-003-positive.json").read_text(encoding="utf-8"))
    goal = "View product using SKU 552811DUDABA00"
    assert not goal_matches_gt(goal, fact, primary_flow_id="BF-PRODUCT-004")
    assert not goal_matches_gt(goal, fact, primary_flow_id="BF-PRODUCT-003")


def test_gt_003_matches_search_sku_intent() -> None:
    fact = {
        "flow_id": "BF-PRODUCT-003",
        "subject": "product search",
        "tags": ["BF-PRODUCT-003", "search sku", "product-search", "sku"],
    }
    assert goal_matches_gt("Search SKU 552811DUDABA00", fact, primary_flow_id="BF-PRODUCT-003")


def test_view_product_without_approved_gt_needs_review(tmp_path: Path) -> None:
    gt_dir = tmp_path / "gt"
    gt_dir.mkdir()
    approved = {
        "id": "gt-bf-product-003-positive",
        "status": "approved",
        "flow_id": "BF-PRODUCT-003",
        "tags": ["BF-PRODUCT-003", "search sku"],
        "expectations": {"execution_ok": True, "min_passed_tests": 1},
    }
    (gt_dir / "gt-bf-product-003-positive.json").write_text(json.dumps(approved), encoding="utf-8")
    kb = KbRag(f"{DISCOVERY}/kb")
    validator = Validator(kb, gt_dir=gt_dir)
    goal = "View product using SKU 552811DUDABA00"
    execution = ExecutionResult(
        ok=True,
        mode="playwright",
        observations=[
            StepObservation(
                step_index=0,
                action="suite",
                ok=True,
                meta={"playwright_report": {"stats": {"expected": 1}}},
            )
        ],
    )
    plan = ExecutionPlan(goal=goal, steps=[])
    from qa_orchestrator.models import IntentClassification, SuiteSelectionPlan

    intent = IntentClassification(goal=goal, flow_ids=["BF-PRODUCT-004"], execution_mode="adhoc_parameterized")
    suite = SuiteSelectionPlan(
        flow_ids=["BF-PRODUCT-004"],
        commands=[build_flow_command("BF-PRODUCT-004")],
        primary_executable_flow_id="BF-PRODUCT-004",
        supporting_flow_ids=["BF-PRODUCT-003"],
    )
    v = validator.validate(goal=goal, run_type="adhoc", plan=plan, execution=execution, intent=intent, suite_plan=suite)
    assert v.conclusion == "NEEDS_REVIEW"
    assert v.phase == "A"


def test_executed_003_test_cannot_pass_view_product_with_003_gt(tmp_path: Path) -> None:
    gt_dir = tmp_path / "gt"
    gt_dir.mkdir()
    approved = {
        "id": "gt-bf-product-003-positive",
        "status": "approved",
        "flow_id": "BF-PRODUCT-003",
        "tags": ["BF-PRODUCT-003", "search sku"],
        "expectations": {"execution_ok": True, "min_passed_tests": 1},
    }
    (gt_dir / "gt-bf-product-003-positive.json").write_text(json.dumps(approved), encoding="utf-8")
    kb = KbRag(f"{DISCOVERY}/kb")
    validator = Validator(kb, gt_dir=gt_dir)
    from qa_orchestrator.agent_models import AgentRunState

    goal = "View product using SKU 552811DUDABA00"
    execution = ExecutionResult(
        ok=True,
        mode="playwright",
        observations=[StepObservation(step_index=0, action="suite", ok=True, meta={"playwright_report": {"stats": {"expected": 1}}})],
    )
    state = AgentRunState(
        run_id="r1",
        request=goal,
        metadata={"executed_test_case_ids": ["TC-BF-PRODUCT-003-P01"]},
    )
    v = validator.validate(
        goal=goal,
        run_type="adhoc",
        plan=ExecutionPlan(goal=goal, steps=[]),
        execution=execution,
        diagnostic_context={"run_id": "r1", "state": state},
    )
    assert v.conclusion != "PASS"
