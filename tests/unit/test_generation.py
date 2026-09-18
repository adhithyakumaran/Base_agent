"""P2 test generation pipeline tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qa_orchestrator.action_model import build_action_model, locator_from_element
from qa_orchestrator.generation_service import GenerationService
from qa_orchestrator.generation_validator import (
    validate_output_path,
    validate_spec_content,
    validate_syntax_typescript,
)
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.models import (
    DiscoveredElement,
    DiscoveryCandidate,
    ExplorationResult,
    GenerationRequest,
    LocatorCandidate,
    PlanningResult,
)
from qa_orchestrator.page_object_registry import resolve_page_object
from qa_orchestrator.playwright_codegen import generate_spec
from qa_orchestrator.scenario_builder import build_scenario
from qa_orchestrator.test_case_builder import build_test_case
from qa_orchestrator.generation_journal import load_journal, save_journal, new_journal_id
from qa_orchestrator.models import GeneratorJournal
from qa_orchestrator.execution_gate import ExecutionGate

from tests.unit.conftest_generation import automation_dir  # noqa: F401 — re-export fixture


DISCOVERY_ROOT = "data/discovery-kb"


@pytest.fixture(autouse=True)
def disable_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_ENABLED", "false")


@pytest.fixture
def graph(automation_dir: Path, tmp_path: Path) -> FlowKnowledgeGraph:
    discovery = tmp_path / "discovery-kb"
    (discovery / "flows").mkdir(parents=True)
    return FlowKnowledgeGraph(discovery_root=discovery, automation_dir=automation_dir)


def _exploration(flow_id: str = "BF-PRODUCT-003") -> ExplorationResult:
    element = DiscoveredElement(
        element_id="el-0",
        role="textbox",
        name="SKU",
        text="SKU",
        tag="input",
        attributes={"placeholder": "SKU", "data-testid": "sku-field"},
        locator_candidates=[
            LocatorCandidate(
                strategy="testid",
                expression='[data-testid="sku-field"]',
                rank=1,
                playwright_code="page.getByTestId('sku-field')",
            )
        ],
        interactive=True,
    )
    candidate = DiscoveryCandidate(
        candidate_id="candidate-explore-1",
        candidate_flow=flow_id,
        observed_page="product-search",
        elements=[element],
        possible_business_behavior=["Search input identified", "Search button identified"],
        confidence=0.8,
        status="DRAFT",
    )
    return ExplorationResult(
        request_id="explore-1",
        exploration_id="explore-1",
        status="COMPLETED",
        goal="Test new product-search filter",
        elements=[element],
        business_signals=["Identified control: input SKU"],
        discovery_candidates=[candidate],
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:01Z",
    )


def _generation_request(**kwargs) -> GenerationRequest:
    defaults = {
        "flow_context": ["BF-PRODUCT-003"],
        "scenario_objective": "Validate new product-search filter behavior",
        "preconditions": ["Authenticated user"],
        "actions": ["Apply filter", "Inspect results"],
        "expected_outcomes": ["Filtered product results region reflects applied filter"],
        "test_data_requirements": {},
        "approval_required": True,
    }
    defaults.update(kwargs)
    return GenerationRequest(**defaults)


def test_exploration_to_scenario():
    exploration = _exploration()
    scenario = build_scenario(
        flow_id="BF-PRODUCT-003",
        request=_generation_request(),
        exploration=exploration,
        candidate=exploration.discovery_candidates[0],
        goal="Test the new product-search filter added yesterday",
    )
    assert scenario.flow_id == "BF-PRODUCT-003"
    assert scenario.status == "DRAFT"
    assert scenario.source == "DISCOVERY"
    assert "filter" in scenario.objective.lower() or scenario.actions


def test_scenario_to_test_case():
    scenario = build_scenario(
        flow_id="BF-PRODUCT-003",
        request=_generation_request(),
        exploration=_exploration(),
        goal="filter",
    )
    test_case = build_test_case(scenario)
    assert test_case.flow_id == "BF-PRODUCT-003"
    assert test_case.status == "DRAFT"
    assert len(test_case.steps) >= 3


def test_test_case_to_action_model():
    scenario = build_scenario(flow_id="BF-PRODUCT-003", request=_generation_request(), exploration=_exploration())
    test_case = build_test_case(scenario)
    actions = build_action_model(test_case, exploration=_exploration(), candidate=_exploration().discovery_candidates[0])
    assert actions
    assert any(a.type in {"page_object", "fill", "click", "assert"} for a in actions)


def test_locator_generation_observed():
    element = _exploration().elements[0]
    loc = locator_from_element(element)
    assert loc.primary.startswith("page.getByTestId")
    assert loc.source == "OBSERVED"
    assert loc.confidence >= 0.4


def test_page_object_reuse():
    binding = resolve_page_object("BF-PRODUCT-003")
    assert binding is not None
    assert binding.class_name == "ProductSearchPage"
    assert "searchItemCode" in binding.methods


def test_code_generation_produces_spec():
    scenario = build_scenario(flow_id="BF-PRODUCT-003", request=_generation_request(), exploration=_exploration())
    test_case = build_test_case(scenario)
    actions = build_action_model(test_case, exploration=_exploration())
    spec, _meta = generate_spec(scenario=scenario, test_case=test_case, actions=actions)
    assert "test.describe" in spec
    assert test_case.test_case_id in spec
    assert "src/fixtures/test-base" in spec
    assert "@generated" in spec and "@draft" in spec


def test_generated_spec_syntax_validation():
    scenario = build_scenario(flow_id="BF-PRODUCT-003", request=_generation_request(), exploration=_exploration())
    test_case = build_test_case(scenario)
    spec, _meta = generate_spec(
        scenario=scenario,
        test_case=test_case,
        actions=build_action_model(test_case, exploration=_exploration()),
    )
    result = validate_syntax_typescript(spec)
    assert result.valid is True


def test_invalid_generated_code_rejected(automation_dir: Path):
    bad = "import evil from '../../../etc/passwd';"
    test_case = build_test_case(
        build_scenario(flow_id="BF-PRODUCT-003", request=_generation_request(), exploration=_exploration())
    )
    result = validate_spec_content(bad, test_case=test_case)
    assert result.valid is False


def test_path_traversal_protection(automation_dir: Path):
    bad_path = automation_dir / "tests" / "evil.spec.ts"
    result = validate_output_path(bad_path, automation_dir)
    assert result.valid is False
    assert "path" in result.reason_code


def test_generated_test_remains_draft(graph: FlowKnowledgeGraph):
    service = GenerationService(graph)
    result = service.generate(
        flow_id="BF-PRODUCT-003",
        request=_generation_request(),
        exploration=_exploration(),
        candidate=_exploration().discovery_candidates[0],
        goal="Test the new product-search filter added yesterday",
    )
    assert result.scenario is not None
    assert result.scenario.status == "DRAFT"
    assert result.test_case is not None
    assert result.test_case.status == "DRAFT"


def test_approval_required_for_generated(graph: FlowKnowledgeGraph):
    service = GenerationService(graph)
    result = service.generate(
        flow_id="BF-PRODUCT-003",
        request=_generation_request(),
        exploration=_exploration(),
        goal="filter",
    )
    assert result.journal is not None
    assert result.journal.review_status in {"DRAFT", "PENDING_SME_APPROVAL"}
    assert result.blocked_execution is True


def test_execution_gate_blocks_unapproved_generated(graph: FlowKnowledgeGraph):
    gate = ExecutionGate(graph)
    decision = gate.evaluate("BF-PRODUCT-003")
    assert decision.executable is False


def test_approved_flow_gate_fixture(tmp_path: Path):
    discovery = tmp_path / "discovery-kb"
    automation = tmp_path / "automation"
    from tests.unit.test_execution_gate import _write_flow_kb, _write_automation, _write_approval_log

    _write_flow_kb(discovery, sme_ready=["BF-LOGIN-001"])
    _write_automation(automation, "BF-LOGIN-001", status="APPROVED")
    _write_approval_log(automation, "BF-LOGIN-001")
    g = FlowKnowledgeGraph(discovery_root=discovery, automation_dir=automation)
    assert g.evaluate_execution("BF-LOGIN-001").executable is True


def test_parameterized_sku_reaches_generated_test(graph: FlowKnowledgeGraph):
    service = GenerationService(graph)
    request = _generation_request(test_data_requirements={"sku": "ABC123"})
    result = service.generate(
        flow_id="BF-PRODUCT-003",
        request=request,
        exploration=_exploration(),
        polarity="parameterized",
        goal="Search SKU ABC123",
    )
    assert result.test_case is not None
    assert "QA_PARAM_SKU" in json.dumps(result.test_case.model_dump())
    content = (graph.automation_dir / (result.generated_spec_path or "")).read_text(encoding="utf-8")
    assert "QA_PARAM_SKU" in content
    assert "ABC123" not in content


def test_existing_auth_fixture_reused_in_spec():
    scenario = build_scenario(
        flow_id="BF-PRODUCT-003",
        request=_generation_request(preconditions=["Authenticated user"]),
        exploration=_exploration(),
    )
    test_case = build_test_case(scenario)
    spec, _meta = generate_spec(
        scenario=scenario,
        test_case=test_case,
        actions=build_action_model(test_case, exploration=_exploration()),
    )
    assert "authenticatedPage" in spec
    assert "productSearchPage" in spec


def test_evidence_fixture_reused_in_spec():
    scenario = build_scenario(flow_id="BF-PRODUCT-003", request=_generation_request(), exploration=_exploration())
    test_case = build_test_case(scenario)
    spec, _meta = generate_spec(
        scenario=scenario,
        test_case=test_case,
        actions=build_action_model(test_case, exploration=_exploration()),
    )
    assert "recordStep" in spec


def test_generator_journal_created(graph: FlowKnowledgeGraph):
    service = GenerationService(graph)
    result = service.generate(
        flow_id="BF-PRODUCT-003",
        request=_generation_request(),
        exploration=_exploration(),
        generation_id="gen-test-001",
    )
    journal = load_journal(graph.automation_dir, "gen-test-001")
    assert journal is not None
    assert journal.test_case_id == result.test_case.test_case_id if result.test_case else True


def test_generation_failure_invalid_path(graph: FlowKnowledgeGraph, monkeypatch: pytest.MonkeyPatch):
    service = GenerationService(graph)

    def boom(*args, **kwargs):
        path = kwargs.get("out_path") if kwargs else None
        raise ValueError("fail")

    monkeypatch.setattr(Path, "write_text", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    result = service.generate(
        flow_id="BF-PRODUCT-003",
        request=_generation_request(),
        exploration=_exploration(),
    )
    assert result.status == "VALIDATION_FAILED"
    assert "write" in result.message.lower() or "disk" in result.message.lower()


def test_generation_retry_produces_new_journal(graph: FlowKnowledgeGraph):
    service = GenerationService(graph)
    first = service.generate(
        flow_id="BF-PRODUCT-003",
        request=_generation_request(),
        exploration=_exploration(),
        generation_id="gen-retry-1",
    )
    second = service.generate(
        flow_id="BF-PRODUCT-003",
        request=_generation_request(),
        exploration=_exploration(),
        generation_id="gen-retry-2",
    )
    assert first.generation_id != second.generation_id
    assert load_journal(graph.automation_dir, "gen-retry-2") is not None


def test_reuse_existing_blocks_unnecessary_generation(graph: FlowKnowledgeGraph):
    from qa_orchestrator.intent_classifier import IntentClassifier
    from qa_orchestrator.llm_client import PlannerLlmClient
    from qa_orchestrator.qa_planner import QaPlanner

    g2 = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT, automation_dir=graph.automation_dir)
    planner = QaPlanner(g2, PlannerLlmClient(enabled=False))
    intent = IntentClassifier(g2, PlannerLlmClient(enabled=False)).classify("Search SKU ABC123")
    planning = planner.plan(intent)
    service = GenerationService(g2)
    result = service.generate_from_planning(planning, exploration=None)
    assert result.status == "BLOCKED"
    assert "existing" in result.message.lower() or "approved" in result.message.lower()


def test_orchestrator_explore_and_generate_demo(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    from qa_orchestrator.orchestrator import QaOrchestrator, RunRequest

    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run(
        RunRequest(
            goal="Discover the product page and create automated coverage",
            model="disabled",
            skip_execution=True,
        )
    )
    assert result.planning is not None
    assert result.exploration is not None
    assert result.generation_result is not None
    assert result.generation_result.status in {"GENERATED", "READY_FOR_APPROVAL", "VALIDATION_FAILED"}
    assert "Test generation" in result.report_markdown
