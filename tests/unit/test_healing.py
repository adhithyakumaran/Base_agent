"""P3 controlled self-healing tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from qa_orchestrator.execution_gate import ExecutionGate
from qa_orchestrator.failure_classifier import classify_failure
from qa_orchestrator.healing_dom import parse_dom_html
from qa_orchestrator.healing_kb import apply_approved_proposal, load_overlays
from qa_orchestrator.healing_locator import generate_candidates, validate_candidate
from qa_orchestrator.healing_policy import (
    AUTO_HEAL_THRESHOLD,
    HUMAN_REVIEW_THRESHOLD,
    MAX_HEALING_ATTEMPTS,
    is_auto_heal_candidate,
    is_healing_eligible,
    requires_human_review,
)
from qa_orchestrator.healing_proposal_store import load_proposal, save_proposal, update_proposal_status
from qa_orchestrator.healing_service import HealingService
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.models import (
    ExecutionResult,
    FailureClassification,
    HealingLocatorCandidate,
    HealingProposal,
    StepObservation,
)
from tests.unit.conftest_generation import _copy_automation_tree


@pytest.fixture
def automation_dir(tmp_path: Path) -> Path:
    root = tmp_path / "automation"
    _copy_automation_tree(root)
    (root / "healing" / "proposals").mkdir(parents=True, exist_ok=True)
    (root / "healing" / "journals").mkdir(parents=True, exist_ok=True)
    (root / "healing" / "approved").mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def discovery_root(tmp_path: Path) -> Path:
    root = tmp_path / "discovery-kb"
    flows = root / "flows"
    flows.mkdir(parents=True)
    (flows / "index.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "flow_kb_index_v1",
                "sme_ready": ["BF-PRODUCT-003"],
                "flows": [{"id": "BF-PRODUCT-003", "file": "BF-PRODUCT-003.yaml", "status": "READY"}],
            }
        ),
        encoding="utf-8",
    )
    (flows / "BF-PRODUCT-003.yaml").write_text(
        yaml.safe_dump({"flow_id": "BF-PRODUCT-003", "locator_strategy": {"primary": "#btn_search"}}),
        encoding="utf-8",
    )
    return root


@pytest.fixture
def graph(automation_dir: Path, discovery_root: Path) -> FlowKnowledgeGraph:
    from datetime import datetime, timedelta, timezone

    design = automation_dir / "test-design" / "flows" / "BF-PRODUCT-003"
    design.mkdir(parents=True, exist_ok=True)
    (design / "test-cases.yaml").write_text("flow_id: BF-PRODUCT-003\nstatus: APPROVED\n", encoding="utf-8")
    catalog = automation_dir / "catalog"
    catalog.mkdir(parents=True, exist_ok=True)
    (catalog / "index.yaml").write_text(
        yaml.safe_dump({"schema": "automation_catalog_v1", "flows": [{"flow_id": "BF-PRODUCT-003"}]}),
        encoding="utf-8",
    )
    approval = automation_dir / "approval"
    approval.mkdir(parents=True, exist_ok=True)
    decided = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    (approval / "approval-log.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "flowId": "BF-PRODUCT-003",
                        "artifact": "test-cases.yaml",
                        "status": "APPROVED",
                        "decidedAt": decided,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return FlowKnowledgeGraph(discovery_root=discovery_root, automation_dir=automation_dir)


def _failed_obs(message: str, **meta) -> StepObservation:
    return StepObservation(step_index=0, action="playwright_suite", ok=False, message=message, meta=meta)


def _dom_search_products() -> str:
    return """
    <html><body>
      <button aria-label="Search Products">Search Products</button>
    </body></html>
    """


def test_locator_failure_classified_correctly():
    obs = _failed_obs("Timeout 30000ms exceeded waiting for locator('#btn_search') No locator resolved for search button")
    failure = classify_failure(observation=obs, flow_id="BF-PRODUCT-003", test_id="TC-001")
    assert failure.type == "LOCATOR"
    assert failure.healing_eligible is True


def test_timing_failure_classified_correctly():
    obs = _failed_obs("Timeout 5000ms exceeded waiting until visible")
    failure = classify_failure(observation=obs)
    assert failure.type in {"TIMING", "LOCATOR"}
    assert is_healing_eligible(failure) or failure.type == "TIMING"


def test_application_failure_not_healable():
    obs = _failed_obs("expect(received).toHaveText() Product unavailable but expected Product displayed")
    failure = classify_failure(observation=obs)
    assert failure.type == "APPLICATION"
    assert is_healing_eligible(failure) is False


def test_business_assertion_not_healable():
    obs = _failed_obs("AssertionError: Product result matching SKU expected visible but Product unavailable shown")
    failure = classify_failure(observation=obs)
    assert failure.type == "APPLICATION"
    assert is_healing_eligible(failure) is False


def test_candidate_locator_generation():
    failure = FailureClassification(
        type="LOCATOR",
        flow_id="BF-PRODUCT-003",
        locator_label="search button",
        original_locator="page.getByTestId('search-button')",
        healing_eligible=True,
    )
    elements = parse_dom_html(_dom_search_products())
    candidates = generate_candidates(failure, dom_elements=elements)
    assert candidates
    assert "Search Products" in candidates[0].primary or "button" in candidates[0].primary.lower()


def test_candidate_locator_ranking():
    failure = FailureClassification(type="LOCATOR", locator_label="search button", healing_eligible=True)
    elements = parse_dom_html(_dom_search_products())
    candidates = generate_candidates(failure, dom_elements=elements)
    assert candidates[0].confidence >= candidates[-1].confidence


def test_candidate_validation():
    elements = parse_dom_html(_dom_search_products())
    candidate = HealingLocatorCandidate(primary="page.getByRole('button', { name: 'Search Products' })", confidence=0.9)
    validated = validate_candidate(candidate, elements)
    assert validated.validated is True


def test_successful_isolated_retry_simulated(graph: FlowKnowledgeGraph, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_HEALING_SIMULATE", "true")
    service = HealingService(graph)
    execution = ExecutionResult(
        ok=False,
        mode="playwright",
        observations=[
            _failed_obs(
                "No locator resolved for search button: page.getByTestId('search-button')",
                evidence=[{"path": "reports/x.png", "dom_path": "reports/x.html"}],
            )
        ],
    )
    dom = graph.automation_dir / "reports" / "x.html"
    dom.parent.mkdir(parents=True, exist_ok=True)
    dom.write_text(_dom_search_products(), encoding="utf-8")
    result = service.attempt_healing(
        execution,
        run_id="run-heal-1",
        flow_id="BF-PRODUCT-003",
        test_id="TC-BF-PRODUCT-003-P01",
    )
    assert result.status == "HEALED_PENDING_APPROVAL"
    assert result.attempts_used >= 1


def test_failed_retry(graph: FlowKnowledgeGraph, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_HEALING_SIMULATE", "false")
    service = HealingService(graph)
    execution = ExecutionResult(
        ok=False,
        mode="playwright",
        observations=[_failed_obs("No locator resolved for search button")],
    )
    result = service.attempt_healing(execution, flow_id="BF-PRODUCT-003", test_id="TC-001")
    assert result.status in {"NO_CANDIDATE", "HEALING_FAILED", "NEEDS_REVIEW"}


def test_maximum_two_healing_attempts():
    assert MAX_HEALING_ATTEMPTS == 2


def test_healing_proposal_created(graph: FlowKnowledgeGraph, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_HEALING_SIMULATE", "true")
    service = HealingService(graph)
    dom = graph.automation_dir / "reports" / "fail.html"
    dom.parent.mkdir(parents=True, exist_ok=True)
    dom.write_text(_dom_search_products(), encoding="utf-8")
    execution = ExecutionResult(
        ok=False,
        mode="playwright",
        observations=[
            _failed_obs(
                "waiting for locator search button",
                evidence=[{"dom_path": "reports/fail.html"}],
            )
        ],
    )
    result = service.attempt_healing(execution, flow_id="BF-PRODUCT-003", test_id="TC-001", healing_id="heal-prop-1")
    assert result.proposal is not None
    saved = load_proposal(graph.automation_dir, "heal-prop-1")
    assert saved is not None
    assert saved.flow_id == "BF-PRODUCT-003"


def test_kb_not_automatically_modified(discovery_root: Path, graph: FlowKnowledgeGraph, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_HEALING_SIMULATE", "true")
    kb_file = discovery_root / "flows" / "BF-PRODUCT-003.yaml"
    before = kb_file.read_text(encoding="utf-8")
    service = HealingService(graph)
    dom = graph.automation_dir / "reports" / "fail.html"
    dom.parent.mkdir(parents=True, exist_ok=True)
    dom.write_text(_dom_search_products(), encoding="utf-8")
    execution = ExecutionResult(
        ok=False,
        mode="playwright",
        observations=[_failed_obs("No locator resolved for search button", evidence=[{"dom_path": "reports/fail.html"}])],
    )
    service.attempt_healing(execution, flow_id="BF-PRODUCT-003", test_id="TC-001")
    after = kb_file.read_text(encoding="utf-8")
    assert before == after


def test_sme_approval_required(graph: FlowKnowledgeGraph, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_HEALING_SIMULATE", "true")
    service = HealingService(graph)
    dom = graph.automation_dir / "reports" / "fail.html"
    dom.parent.mkdir(parents=True, exist_ok=True)
    dom.write_text(_dom_search_products(), encoding="utf-8")
    execution = ExecutionResult(
        ok=False,
        mode="playwright",
        observations=[_failed_obs("No locator resolved for search button", evidence=[{"dom_path": "reports/fail.html"}])],
    )
    result = service.attempt_healing(execution, flow_id="BF-PRODUCT-003", test_id="TC-001")
    assert result.proposal is not None
    assert result.proposal.status == "PENDING_SME_APPROVAL"
    assert result.execution_still_blocked is True


def test_approved_proposal_updates_locator_chain(graph: FlowKnowledgeGraph):
    proposal = HealingProposal(
        healing_id="heal-approved-1",
        flow_id="BF-PRODUCT-003",
        test_id="TC-001",
        locator_label="search button",
        old_locator="page.getByTestId('search-button')",
        new_locator="page.getByRole('button', { name: 'Search Products' })",
        fallbacks=['button[aria-label="Search"]'],
        confidence=0.95,
        status="APPROVED",
    )
    apply_approved_proposal(graph.automation_dir, proposal)
    from qa_orchestrator.healing_overlay import load_overlay_store

    store = load_overlay_store(graph.automation_dir)
    assert store["schema"] == "healing_locator_overlay_v1"
    assert store["overlay_hash"]
    assert any(e["healing_id"] == "heal-approved-1" for e in store["entries"])


def test_rejected_proposal_does_not_update_kb(graph: FlowKnowledgeGraph):
    proposal = HealingProposal(
        healing_id="heal-reject-1",
        flow_id="BF-PRODUCT-003",
        test_id="TC-001",
        locator_label="search button",
        new_locator="page.getByRole('button', { name: 'Bad' })",
        status="REJECTED",
    )
    save_proposal(graph.automation_dir, proposal)
    update_proposal_status(graph.automation_dir, "heal-reject-1", "REJECTED")
    overlays = load_overlays(graph.automation_dir)
    assert overlays == {}


def test_evidence_captured_per_attempt(graph: FlowKnowledgeGraph, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_HEALING_SIMULATE", "true")
    service = HealingService(graph)
    dom = graph.automation_dir / "reports" / "fail.html"
    dom.parent.mkdir(parents=True, exist_ok=True)
    dom.write_text(_dom_search_products(), encoding="utf-8")
    execution = ExecutionResult(
        ok=False,
        mode="playwright",
        observations=[_failed_obs("No locator resolved for search button", evidence=[{"dom_path": "reports/fail.html"}])],
    )
    result = service.attempt_healing(execution, run_id="run-ev-1", flow_id="BF-PRODUCT-003", test_id="TC-001")
    assert result.journal is not None
    assert result.journal.evidence_paths
    evidence_root = graph.automation_dir / "reports" / "evidence" / "run-ev-1"
    assert evidence_root.exists()


def test_confidence_auto_threshold():
    candidate = HealingLocatorCandidate(primary="x", confidence=AUTO_HEAL_THRESHOLD, validated=True)
    assert is_auto_heal_candidate(candidate)


def test_human_review_threshold():
    candidate = HealingLocatorCandidate(primary="x", confidence=HUMAN_REVIEW_THRESHOLD + 0.05, validated=True)
    assert requires_human_review(candidate)
    assert not is_auto_heal_candidate(candidate)


def test_healing_cannot_bypass_execution_gate(graph: FlowKnowledgeGraph, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_HEALING_SIMULATE", "true")
    gate = ExecutionGate(graph)
    assert gate.evaluate("BF-PRODUCT-003").executable is True
    service = HealingService(graph)
    dom = graph.automation_dir / "reports" / "fail.html"
    dom.parent.mkdir(parents=True, exist_ok=True)
    dom.write_text(_dom_search_products(), encoding="utf-8")
    execution = ExecutionResult(
        ok=False,
        mode="playwright",
        observations=[_failed_obs("No locator resolved for search button", evidence=[{"dom_path": "reports/fail.html"}])],
    )
    result = service.attempt_healing(execution, flow_id="BF-PRODUCT-003", test_id="TC-001")
    assert result.execution_still_blocked is True
    assert result.proposal is not None
    assert result.proposal.status == "PENDING_SME_APPROVAL"


def test_healing_journal_created(graph: FlowKnowledgeGraph, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_HEALING_SIMULATE", "true")
    service = HealingService(graph)
    dom = graph.automation_dir / "reports" / "fail.html"
    dom.parent.mkdir(parents=True, exist_ok=True)
    dom.write_text(_dom_search_products(), encoding="utf-8")
    execution = ExecutionResult(
        ok=False,
        mode="playwright",
        observations=[_failed_obs("No locator resolved for search button", evidence=[{"dom_path": "reports/fail.html"}])],
    )
    result = service.attempt_healing(execution, healing_id="heal-journal-1", flow_id="BF-PRODUCT-003", test_id="TC-001")
    journal_path = graph.automation_dir / "healing" / "journals" / "heal-journal-1.json"
    assert journal_path.exists()
    payload = json.loads(journal_path.read_text(encoding="utf-8"))
    assert payload["healing_id"] == "heal-journal-1"
    assert result.journal is not None


def test_data_failure_not_locator_healed():
    obs = _failed_obs("QA_PARAM_SKU not set — invalid SKU causes no result")
    failure = classify_failure(observation=obs)
    assert failure.type == "DATA"
    assert is_healing_eligible(failure) is False
