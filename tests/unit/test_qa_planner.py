"""QA Planning Layer tests — strategy, gate integration, and policy guards."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from qa_orchestrator.intent_classifier import IntentClassifier
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.llm_client import PlannerLlmClient
from qa_orchestrator.models import IntentClassification
from qa_orchestrator.qa_planner import QaPlanner

DISCOVERY_ROOT = "data/discovery-kb"


@pytest.fixture(scope="module", autouse=True)
def _ensure_execution_baseline_for_planner_tests() -> None:
    import os

    from qa_orchestrator.bootstrap_approval import bootstrap_approve_sme_ready_flows

    os.environ["QA_BOOTSTRAP_APPROVALS"] = "true"
    bootstrap_approve_sme_ready_flows(enabled=True)


@pytest.fixture(autouse=True)
def disable_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_ENABLED", "false")


def _planner() -> QaPlanner:
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    return QaPlanner(graph, PlannerLlmClient(enabled=False))


def _plan(goal: str, *, run_type: str = "adhoc") -> tuple:
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    intent = IntentClassifier(graph, PlannerLlmClient(enabled=False)).classify(goal, run_type=run_type)
    planning = QaPlanner(graph, PlannerLlmClient(enabled=False)).plan(intent)
    return intent, planning


def _write_flow_kb(root: Path, *, sme_ready: list[str], flows: list[dict] | None = None) -> None:
    flows_dir = root / "flows"
    flows_dir.mkdir(parents=True, exist_ok=True)
    flow_entries = flows or [
        {"id": "BF-LOGIN-001", "file": "BF-LOGIN-001.yaml", "name": "Login", "status": "READY"},
    ]
    (flows_dir / "index.yaml").write_text(
        yaml.safe_dump({"sme_ready": sme_ready, "flows": flow_entries}),
        encoding="utf-8",
    )
    for entry in flow_entries:
        fid = entry["id"]
        (flows_dir / str(entry["file"])).write_text(
            yaml.safe_dump({"flow_id": fid, "flow_name": entry.get("name", fid), "purpose": fid.lower()}),
            encoding="utf-8",
        )


def _write_automation(
    root: Path,
    flow_id: str,
    *,
    status: str = "APPROVED",
    in_catalog: bool = True,
) -> None:
    design = root / "test-design" / "flows" / flow_id
    design.mkdir(parents=True, exist_ok=True)
    (design / "test-cases.yaml").write_text(
        yaml.safe_dump(
            {
                "flow_id": flow_id,
                "status": status,
                "test_cases": [
                    {"id": "TC-P01", "type": "positive"},
                    {"id": "TC-N01", "type": "negative"},
                ],
            }
        ),
        encoding="utf-8",
    )
    if in_catalog:
        catalog = root / "catalog" / "index.yaml"
        catalog.parent.mkdir(parents=True, exist_ok=True)
        catalog.write_text(
            yaml.safe_dump({"flows": [{"flow_id": flow_id, "flow_name": flow_id}]}),
            encoding="utf-8",
        )


def _write_approval_log(root: Path, flow_id: str, *, decided_at: str | None = None) -> None:
    log_dir = root / "approval"
    log_dir.mkdir(parents=True, exist_ok=True)
    decided = decided_at or datetime.now(timezone.utc).isoformat()
    (log_dir / "approval-log.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "flowId": flow_id,
                        "artifact": "test-cases.yaml",
                        "status": "APPROVED",
                        "approver": "sme@test.com",
                        "decidedAt": decided,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _planner_for(tmp_discovery: Path, tmp_automation: Path) -> QaPlanner:
    graph = FlowKnowledgeGraph(discovery_root=tmp_discovery, automation_dir=tmp_automation)
    return QaPlanner(graph, PlannerLlmClient(enabled=False))


def _plan_intent(planner: QaPlanner, intent: IntentClassification):
    return planner.plan(intent)


# --- 17 required planner scenarios ---


def test_planner_check_login():
    _, planning = _plan("check login")
    assert planning.strategy == "REUSE_EXISTING"
    assert "BF-LOGIN-001" in planning.candidate_flows
    assert planning.polarity == "positive"
    assert planning.execution_allowed is True
    assert "BF-LOGIN-001" in planning.selected_flows


def test_planner_run_login():
    _, planning = _plan("run positive login")
    assert planning.strategy == "REUSE_EXISTING"
    assert "BF-LOGIN-001" in planning.candidate_flows
    assert planning.execution_allowed is True


def test_planner_invalid_login():
    _, planning = _plan("run negative login invalid credentials")
    assert planning.strategy == "REUSE_EXISTING"
    assert "BF-LOGIN-001" in planning.candidate_flows
    assert planning.polarity == "negative"
    assert planning.execution_allowed is True


def test_planner_search_sku_abc123():
    _, planning = _plan("Search SKU ABC123")
    assert planning.strategy == "REUSE_EXISTING"
    assert "BF-PRODUCT-003" in planning.candidate_flows
    assert planning.validated_parameters.get("sku") == "ABC123"
    assert planning.polarity == "parameterized"
    assert planning.execution_allowed is True
    assert planning.requires_human_approval is True


def test_planner_search_sku_invalid_value():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    intent = IntentClassifier(graph, PlannerLlmClient(enabled=False)).classify("Search SKU ABC123")
    intent = intent.model_copy(update={"params": {"sku": "bad;rm -rf"}})
    planning = QaPlanner(graph, PlannerLlmClient(enabled=False)).plan(intent)
    assert planning.strategy == "ASK_USER"
    assert planning.execution_allowed is False
    assert planning.validated_parameters == {}


def test_planner_full_regression():
    _, planning = _plan("run full regression", run_type="regression")
    assert planning.strategy == "REUSE_EXISTING"
    assert len(planning.candidate_flows) >= 19
    assert planning.execution_allowed is True


def test_planner_morning_sanity():
    _, planning = _plan("morning sanity check endless aisle", run_type="sanity")
    assert planning.strategy == "REUSE_EXISTING"
    assert len(planning.candidate_flows) >= 19
    assert planning.execution_allowed is True


def test_planner_unknown_flow():
    _, planning = _plan("verify the BF-DOES-NOT-EXIST-999 flow")
    assert "BF-DOES-NOT-EXIST-999" not in planning.selected_flows
    assert planning.execution_allowed is True


def test_planner_ambiguous_request():
    _, planning = _plan("test")
    assert planning.strategy == "REUSE_EXISTING"
    assert planning.requires_human_approval is True


def test_planner_new_product_feature():
    _, planning = _plan("Test the new product search filter added yesterday")
    assert planning.strategy == "EXPLORE"
    assert planning.exploration_required is True
    assert planning.exploration is not None
    assert planning.execution_allowed is False


def test_planner_discover_application():
    _, planning = _plan("discover the application and crawl pages")
    assert planning.strategy == "EXPLORE"
    assert planning.exploration is not None
    assert planning.exploration.read_only is True


def test_planner_request_requiring_new_automation():
    _, planning = _plan("Discover the product page and create automated coverage")
    assert planning.strategy == "EXPLORE"
    assert "GENERATE" in planning.secondary_strategies
    assert planning.generation_required is True
    assert planning.generation is not None
    assert planning.generation.approval_required is True


def test_planner_destructive_operation():
    _, planning = _plan("Delete all customer records")
    assert planning.strategy == "BLOCK"
    assert planning.risk_level == "BLOCKED"
    assert planning.execution_allowed is False


def test_planner_superseded_flow():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    intent = IntentClassification(
        goal="run best deal product detail",
        flow_ids=["BF-BESTDEAL-008"],
        execution_mode="adhoc_existing",
    )
    planning = QaPlanner(graph, PlannerLlmClient(enabled=False)).plan(intent)
    assert "BF-BEST-DEAL-008" in planning.candidate_flows
    assert "BF-BESTDEAL-008" not in planning.candidate_flows


def test_planner_approved_but_stale_artifact(tmp_path: Path):
    discovery = tmp_path / "discovery-kb"
    automation = tmp_path / "automation"
    _write_flow_kb(discovery, sme_ready=["BF-LOGIN-001"])
    _write_automation(automation, "BF-LOGIN-001", status="APPROVED")
    _write_approval_log(automation, "BF-LOGIN-001", decided_at="2020-01-01T00:00:00+00:00")
    planner = _planner_for(discovery, automation)
    intent = IntentClassification(goal="check login", flow_ids=["BF-LOGIN-001"])
    planning = _plan_intent(planner, intent)
    assert planning.strategy == "REUSE_EXISTING"
    assert "BF-LOGIN-001" in planning.blocked_flows
    assert planning.execution_allowed is False
    assert any(g.reason_code == "approval.stale" for g in planning.execution_gates)


def test_planner_approved_but_not_sme_ready(tmp_path: Path):
    discovery = tmp_path / "discovery-kb"
    automation = tmp_path / "automation"
    _write_flow_kb(discovery, sme_ready=[])
    _write_automation(automation, "BF-LOGIN-001", status="APPROVED")
    _write_approval_log(automation, "BF-LOGIN-001")
    planner = _planner_for(discovery, automation)
    intent = IntentClassification(goal="check login", flow_ids=["BF-LOGIN-001"])
    planning = _plan_intent(planner, intent)
    assert "BF-LOGIN-001" in planning.blocked_flows
    assert planning.execution_allowed is False
    assert any(g.reason_code == "kb.not_sme_ready" for g in planning.execution_gates)


def test_planner_flow_not_in_catalog(tmp_path: Path):
    discovery = tmp_path / "discovery-kb"
    automation = tmp_path / "automation"
    _write_flow_kb(discovery, sme_ready=["BF-LOGIN-001"])
    _write_automation(automation, "BF-LOGIN-001", status="APPROVED", in_catalog=False)
    _write_approval_log(automation, "BF-LOGIN-001")
    planner = _planner_for(discovery, automation)
    intent = IntentClassification(goal="check login", flow_ids=["BF-LOGIN-001"])
    planning = _plan_intent(planner, intent)
    assert planning.execution_allowed is False
    assert any(g.reason_code == "kb.not_in_catalog" for g in planning.execution_gates)


def test_planner_approved_executable_flow(tmp_path: Path):
    discovery = tmp_path / "discovery-kb"
    automation = tmp_path / "automation"
    _write_flow_kb(discovery, sme_ready=["BF-LOGIN-001"])
    _write_automation(automation, "BF-LOGIN-001", status="APPROVED")
    _write_approval_log(automation, "BF-LOGIN-001")
    planner = _planner_for(discovery, automation)
    intent = IntentClassification(goal="check login", flow_ids=["BF-LOGIN-001"])
    planning = _plan_intent(planner, intent)
    assert planning.strategy == "REUSE_EXISTING"
    assert planning.selected_flows == ["BF-LOGIN-001"]
    assert planning.execution_allowed is True
    assert planning.requires_human_approval is False


def test_planner_does_not_bypass_execution_gate(tmp_path: Path):
    discovery = tmp_path / "discovery-kb"
    automation = tmp_path / "automation"
    _write_flow_kb(discovery, sme_ready=["BF-LOGIN-001"])
    _write_automation(automation, "BF-LOGIN-001", status="PENDING_SME_APPROVAL")
    planner = _planner_for(discovery, automation)
    intent = IntentClassification(goal="check login", flow_ids=["BF-LOGIN-001"])
    planning = planner.plan(intent)
    assert planning.selected_flows == []
    assert "BF-LOGIN-001" in planning.blocked_flows


def test_orchestrator_includes_planning_result():
    from qa_orchestrator.orchestrator import QaOrchestrator, RunRequest

    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run(RunRequest(goal="check login", model="disabled", skip_execution=True))
    assert result.planning is not None
    assert result.planning.strategy == "REUSE_EXISTING"
    assert "QA planning" in result.report_markdown
