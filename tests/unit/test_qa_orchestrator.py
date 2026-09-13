"""P0 unit tests — params, suite commands, evidence, GT, approval helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from qa_orchestrator.flow_kb import YamlFlowKb
from qa_orchestrator.gt_eval import evaluate_gt_expectations, goal_matches_gt
from qa_orchestrator.intent_classifier import IntentClassifier
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.llm_client import PlannerLlmClient
from qa_orchestrator.models import ExecutionPlan, ExecutionResult, PlanStep, StepObservation
from qa_orchestrator.openclaw_adapter import OpenClawAdapter
from qa_orchestrator.orchestrator import QaOrchestrator, RunRequest
from qa_orchestrator.param_validator import validate_run_params
from qa_orchestrator.playwright_runner import PlaywrightRunner, collect_evidence
from qa_orchestrator.suite_commands import (
    build_flow_command,
    build_negative_flow_commands,
    build_sanity_command,
)
from qa_orchestrator.suite_selector import SuiteSelector
from qa_orchestrator.validator import Validator


DISCOVERY_ROOT = "data/discovery-kb"
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


def test_intent_classifier_search_sku_abc123_preserves_case():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    classifier = IntentClassifier(graph, PlannerLlmClient(enabled=False))
    intent = classifier.classify("Search SKU ABC123")
    assert intent.execution_mode == "adhoc_parameterized"
    assert intent.params.get("sku") == "ABC123"


def test_intent_classifier_parameterized_sku():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    classifier = IntentClassifier(graph, PlannerLlmClient(enabled=False))
    intent = classifier.classify("SKU ABC12345 returns 404 in product search")
    assert intent.execution_mode == "adhoc_parameterized"
    assert intent.params.get("sku") == "ABC12345"


def test_param_validator_accepts_safe_sku():
    out = validate_run_params({"sku": "ABC123"})
    assert out["sku"] == "ABC123"


def test_param_validator_rejects_unsafe_sku():
    with pytest.raises(ValueError, match="invalid param SKU"):
        validate_run_params({"sku": "bad;rm -rf"})


def test_suite_commands_positive_login():
    cmd = build_flow_command("BF-LOGIN-001", polarity="positive")
    assert cmd == "npm run test:flow:positive -- BF-LOGIN-001"


def test_suite_commands_negative_login():
    cmd = build_flow_command("BF-LOGIN-001", polarity="negative")
    assert cmd == "npm run test:flow:negative -- BF-LOGIN-001"


def test_suite_commands_sanity_positive_only():
    assert build_sanity_command(positive_only=True) == "npm run test:sanity:positive"


def test_suite_selector_picks_positive_sanity():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    classifier = IntentClassifier(graph, PlannerLlmClient(enabled=False))
    intent = classifier.classify("morning sanity", run_type="sanity")
    plan = SuiteSelector(graph).select(intent)
    assert plan.commands == ["npm run test:sanity:positive"]


def test_suite_selector_positive_login_flow():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    classifier = IntentClassifier(graph, PlannerLlmClient(enabled=False))
    intent = classifier.classify("run positive login")
    plan = SuiteSelector(graph).select(intent)
    assert "BF-LOGIN-001" in plan.flow_ids
    assert plan.commands == ["npm run test:flow:positive -- BF-LOGIN-001"]


def test_suite_selector_negative_login_flow():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    classifier = IntentClassifier(graph, PlannerLlmClient(enabled=False))
    intent = classifier.classify("run negative login invalid credentials")
    plan = SuiteSelector(graph).select(intent)
    assert "BF-LOGIN-001" in plan.flow_ids
    assert plan.commands == ["npm run test:flow:negative -- BF-LOGIN-001"]


def test_suite_selector_parameterized_sku_command():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    classifier = IntentClassifier(graph, PlannerLlmClient(enabled=False))
    intent = classifier.classify("Search SKU ABC123")
    plan = SuiteSelector(graph).select(intent)
    assert plan.params["sku"] == "ABC123"
    assert plan.commands == ["npm run test:flow:positive -- BF-PRODUCT-003"]


def test_playwright_runner_rejects_invalid_params(tmp_path: Path):
    from qa_orchestrator.playwright_runner import PlaywrightRunnerConfig

    runner = PlaywrightRunner(
        config=PlaywrightRunnerConfig(automation_dir=tmp_path, dry_run=False, timeout_s=5.0)
    )
    (tmp_path / "node_modules").mkdir()
    obs = runner._run_command(
        "npm run test:sanity:positive",
        step_index=0,
        params={"sku": "../../../etc/passwd"},
        flow_ids=[],
    )
    assert obs.ok is False
    assert "invalid params" in (obs.message or "")


def test_collect_evidence_isolated_by_run_id(tmp_path: Path):
    root = tmp_path / "automation"
    run_a = root / "reports" / "evidence" / "run-a" / "TC-1" / "step"
    run_b = root / "reports" / "evidence" / "run-b" / "TC-2" / "step"
    run_a.mkdir(parents=True)
    run_b.mkdir(parents=True)
    png_a = run_a / "capture.png"
    png_b = run_b / "capture.png"
    png_a.write_bytes(b"a")
    png_b.write_bytes(b"b")
    meta_a = run_a / "capture.json"
    meta_a.write_text(json.dumps({"runId": "run-a", "testId": "TC-1", "stepId": "step"}), encoding="utf-8")

    only_a = collect_evidence(root, run_id="run-a")
    assert len(only_a) == 1
    assert "run-a" in only_a[0]["path"]
    assert "run-b" not in only_a[0]["path"]

    only_b = collect_evidence(root, run_id="run-b")
    assert len(only_b) == 1
    assert "run-b" in only_b[0]["path"]


def test_validator_needs_review_without_gt():
    from qa_orchestrator.kb_rag import KbRag

    kb = KbRag(f"{DISCOVERY_ROOT}/kb")
    validator = Validator(kb, gt_dir=f"{DISCOVERY_ROOT}/gt")
    plan = ExecutionPlan(goal="unrelated goal xyz", steps=[PlanStep(action="custom", target="suite")])
    execution = ExecutionResult(ok=True, mode="playwright_dry_run", observations=[])
    v = validator.validate(goal="unrelated goal xyz", run_type="adhoc", plan=plan, execution=execution)
    assert v.phase == "A"
    assert v.conclusion == "NEEDS_REVIEW"


def test_validator_pass_with_approved_gt():
    from qa_orchestrator.kb_rag import KbRag

    kb = KbRag(f"{DISCOVERY_ROOT}/kb")
    validator = Validator(kb, gt_dir=f"{DISCOVERY_ROOT}/gt")
    plan = ExecutionPlan(goal="verify login works", steps=[PlanStep(action="custom", target="suite")])
    execution = ExecutionResult(
        ok=True,
        mode="playwright",
        observations=[
            StepObservation(
                step_index=0,
                action="playwright_suite",
                ok=True,
                meta={"playwright_report": {"stats": {"expected": 1}}},
            )
        ],
    )
    v = validator.validate(goal="verify positive login", run_type="adhoc", plan=plan, execution=execution)
    assert v.phase == "B"
    assert v.conclusion == "PASS"


def test_gt_eval_expectations_fail_on_bad_execution():
    fact = {"expectations": {"execution_ok": True, "min_passed_tests": 1}}
    passed, failures = evaluate_gt_expectations(fact, execution_ok=False, observation_meta=[])
    assert passed is False
    assert failures


def test_goal_matches_gt_login():
    fact = {"subject": "login", "tags": ["BF-LOGIN-001"]}
    assert goal_matches_gt("verify positive login", fact)


def test_orchestrator_sanity_run_dry_run():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    payload = orch.to_agent_payload(
        orch.run(RunRequest(goal="morning sanity check endless aisle", run_type="sanity", model="disabled"))
    )
    assert payload["conclusion"] in {"NEEDS_REVIEW", "FAIL", "PASS"}
    assert payload["local"]["execution_mode"] == "morning_sanity"
    assert payload["local"]["suite_plan"]["commands"] == ["npm run test:sanity:positive"]


def test_orchestrator_passes_run_id_metadata():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run(
        RunRequest(goal="morning sanity", run_type="sanity", model="disabled", run_id="run-test-123")
    )
    assert result.metadata.get("run_id") == "run-test-123"
