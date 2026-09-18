"""P2.1 generation hardening tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qa_orchestrator.action_model import build_action_model, locator_from_element
from qa_orchestrator.assertion_quality import classify_assertion_action, classify_actions
from qa_orchestrator.codegen_bridge import invoke_codegen_bridge, probe_codegen_bridge
from qa_orchestrator.execution_gate import ExecutionGate
from qa_orchestrator.generation_quality import code_hash, validate_parameter_trace
from qa_orchestrator.generation_service import GenerationService
from qa_orchestrator.generation_validator import (
    validate_fixture_imports,
    validate_playwright_discovery,
    validate_typescript_compile,
)
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.locator_verification import verify_action_locators, verify_locator_against_elements
from qa_orchestrator.models import (
    DiscoveredElement,
    ExplorationResult,
    GeneratedAction,
    GenerationRequest,
    LocatorCandidate,
)
from qa_orchestrator.page_object_validator import validate_page_object_actions
from qa_orchestrator.playwright_codegen import generate_spec
from qa_orchestrator.scenario_builder import build_scenario
from qa_orchestrator.test_case_builder import build_test_case
from tests.unit.conftest_generation import automation_dir  # noqa: F401
from tests.unit.test_generation import _exploration, _generation_request, graph


def test_playwright_codegen_bridge_probe_documents_unavailable(automation_dir: Path):
    probe = probe_codegen_bridge(automation_dir)
    assert probe.get("bridgeAvailable") is False
    assert "playwright" in str(probe.get("reason", "")).lower() or "codegen" in str(probe.get("reason", "")).lower()
    assert probe.get("playwrightVersion") not in {None, ""}


def test_fallback_serializer_when_bridge_unavailable(automation_dir: Path):
    scenario = build_scenario(flow_id="BF-PRODUCT-003", request=_generation_request(), exploration=_exploration())
    test_case = build_test_case(scenario)
    actions = build_action_model(test_case, exploration=_exploration())
    bridge = invoke_codegen_bridge(
        automation_dir,
        {"actions": [a.model_dump() for a in actions]},
    )
    assert bridge.get("ok") is True
    assert bridge.get("bridgeAvailable") is False
    spec, meta = generate_spec(
        scenario=scenario,
        test_case=test_case,
        actions=actions,
        automation_dir=automation_dir,
    )
    assert "test.describe" in spec
    assert meta.get("bodyLines") or "expectResultRegion" in spec or "recordStep" in spec


def test_typescript_failure_rejected(automation_dir: Path):
    bad_path = automation_dir / "generated" / "drafts" / "BF-PRODUCT-003" / "bad.spec.ts"
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text("const x: number = 'nope'; export {}", encoding="utf-8")
    result = validate_typescript_compile(bad_path, automation_dir)
    assert result.valid is False
    assert result.reason_code == "generation.typescript_invalid"


def test_import_failure_rejected(automation_dir: Path):
    content = "import { test } from '../../src/fixtures/missing-fixture'; test('x', async () => {});"
    result = validate_fixture_imports(content, automation_dir)
    assert result.valid is False
    assert result.reason_code == "generation.import_missing"


def test_missing_fixture_file_rejected(automation_dir: Path):
    (automation_dir / "src" / "fixtures" / "test-base.ts").unlink()
    content = "import { test } from '../../src/fixtures/test-base';"
    result = validate_fixture_imports(content, automation_dir)
    assert result.valid is False
    assert result.reason_code == "generation.fixture_missing"


def test_missing_page_object_method_rejected(automation_dir: Path):
    actions = [
        GeneratedAction(
            type="page_object",
            page_object="ProductSearchPage",
            page_object_method="nonExistentMethod",
        )
    ]
    result = validate_page_object_actions(actions, automation_dir)
    assert result.valid is False
    assert result.reason_code == "generation.page_object_method_missing"


def test_strong_assertion_classification():
    action = GeneratedAction(
        type="page_object",
        page_object="ProductSearchPage",
        page_object_method="expectResultRegion",
        expectation="Product result matching QA_PARAM_SKU is displayed",
        evidence_source="exploration",
    )
    quality, source, text = classify_assertion_action(action, user_goal="Search SKU ABC123")
    assert quality == "STRONG"
    assert source == "EXPLORATION"
    assert "product result" in text.lower()


def test_weak_assertion_classification():
    action = GeneratedAction(
        type="assert",
        expectation="Search button is visible",
        evidence_source="exploration",
    )
    quality, _, _ = classify_assertion_action(action, user_goal="filter")
    assert quality == "WEAK"


def test_missing_assertion_classification():
    action = GeneratedAction(type="navigate")
    quality, _, _ = classify_assertion_action(action)
    assert quality == "MISSING"


def test_assertion_traceability_required():
    scenario = build_scenario(flow_id="BF-PRODUCT-003", request=_generation_request(), exploration=_exploration())
    test_case = build_test_case(scenario)
    actions = build_action_model(test_case, exploration=_exploration())
    quality = classify_actions(actions, scenario=scenario, test_case=test_case, user_goal="filter")
    assertion_actions = [
        a
        for a in actions
        if a.type == "assert" or (a.type == "page_object" and a.page_object_method == "expectResultRegion")
    ]
    assert assertion_actions
    assert all(a.assertion_source and a.assertion_text for a in assertion_actions)
    assert quality in {"STRONG", "MODERATE", "WEAK", "MISSING"}


def test_locator_verified_from_exploration():
    exploration = _exploration()
    element = exploration.elements[0]
    loc = locator_from_element(element)
    verified, evidence = verify_locator_against_elements(loc, exploration.elements)
    assert verified is True
    assert "matched" in evidence.lower()


def test_locator_not_observed():
    loc = locator_from_element(_exploration().elements[0])
    verified, _ = verify_locator_against_elements(
        loc,
        [
            DiscoveredElement(
                element_id="other",
                role="button",
                name="Cancel",
                text="Cancel",
                tag="button",
                attributes={},
            )
        ],
    )
    assert verified is False


def test_parameter_hardcoding_rejected():
    trace = [{"step": "request", "value": "ABC123"}]
    test_case = build_test_case(
        build_scenario(
            flow_id="BF-PRODUCT-003",
            request=_generation_request(test_data_requirements={"sku": "ABC123"}),
            exploration=_exploration(),
            polarity="parameterized",
        )
    )
    bad_content = "await productSearchPage.searchItemCode('ABC123');"
    result = validate_parameter_trace(
        bad_content,
        user_goal="Search SKU ABC123",
        test_case=test_case,
        trace=trace,
    )
    assert result.valid is False
    assert "hardcoded" in result.reason_code or "parameter" in result.reason_code


def test_qa_param_sku_propagation(graph: FlowKnowledgeGraph):
    service = GenerationService(graph)
    result = service.generate(
        flow_id="BF-PRODUCT-003",
        request=_generation_request(test_data_requirements={"sku": "ABC123"}),
        exploration=_exploration(),
        polarity="parameterized",
        goal="Search SKU ABC123",
    )
    content = (graph.automation_dir / (result.generated_spec_path or "")).read_text(encoding="utf-8")
    assert "QA_PARAM_SKU" in content
    assert "ABC123" not in content
    assert any(step.get("step") == "env_var" for step in (result.journal.parameter_trace if result.journal else []))


def test_generated_test_discovery(graph: FlowKnowledgeGraph):
    service = GenerationService(graph)
    result = service.generate(
        flow_id="BF-PRODUCT-003",
        request=_generation_request(),
        exploration=_exploration(),
        goal="Test the new product-search filter added yesterday",
    )
    assert result.quality_report is not None
    assert result.quality_report.test_discovered is True


def test_generated_code_hash_in_journal(graph: FlowKnowledgeGraph):
    service = GenerationService(graph)
    result = service.generate(
        flow_id="BF-PRODUCT-003",
        request=_generation_request(),
        exploration=_exploration(),
        generation_id="gen-hash-test",
    )
    assert result.journal is not None
    assert len(result.journal.generated_code_hash) == 64
    content = (graph.automation_dir / (result.generated_spec_path or "")).read_text(encoding="utf-8")
    assert result.journal.generated_code_hash == code_hash(content)


def test_draft_remains_non_executable(graph: FlowKnowledgeGraph):
    service = GenerationService(graph)
    result = service.generate(
        flow_id="BF-PRODUCT-003",
        request=_generation_request(),
        exploration=_exploration(),
    )
    assert result.blocked_execution is True
    assert result.scenario.status == "DRAFT"
    assert "GENERATED DRAFT" in (
        graph.automation_dir / (result.generated_spec_path or "")
    ).read_text(encoding="utf-8")


def test_execution_gate_still_required(graph: FlowKnowledgeGraph):
    gate = ExecutionGate(graph)
    assert gate.evaluate("BF-PRODUCT-003").executable is False
