"""Unified execution gate tests — approval + sme_ready + KB safety."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from qa_orchestrator.execution_gate import ExecutionGate
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph


def _write_flow_kb(root: Path, *, sme_ready: list[str]) -> None:
    flows_dir = root / "flows"
    flows_dir.mkdir(parents=True, exist_ok=True)
    (flows_dir / "index.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "flow_kb_index_v1",
                "application": "Test App",
                "sme_ready": sme_ready,
                "flows": [
                    {
                        "id": "BF-LOGIN-001",
                        "file": "BF-LOGIN-001.yaml",
                        "name": "Login",
                        "status": "READY",
                    },
                    {
                        "id": "BF-DRAFT-001",
                        "file": "BF-DRAFT-001.yaml",
                        "name": "Draft",
                        "status": "DRAFT",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (flows_dir / "BF-LOGIN-001.yaml").write_text(
        yaml.safe_dump({"flow_id": "BF-LOGIN-001", "flow_name": "Login", "purpose": "login"}),
        encoding="utf-8",
    )
    (flows_dir / "BF-DRAFT-001.yaml").write_text(
        yaml.safe_dump({"flow_id": "BF-DRAFT-001", "flow_name": "Draft", "purpose": "draft"}),
        encoding="utf-8",
    )


def _write_automation(root: Path, flow_id: str, status: str) -> None:
    design = root / "test-design" / "flows" / flow_id
    design.mkdir(parents=True, exist_ok=True)
    (design / "test-cases.yaml").write_text(
        f"flow_id: {flow_id}\nstatus: {status}\n",
        encoding="utf-8",
    )
    catalog = root / "catalog" / "index.yaml"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text(
        yaml.safe_dump(
            {
                "schema": "automation_catalog_v1",
                "flows": [{"flow_id": flow_id, "flow_name": flow_id}],
            }
        ),
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


@pytest.fixture()
def gate_workspace(tmp_path: Path) -> tuple[Path, Path]:
    discovery = tmp_path / "discovery-kb"
    automation = tmp_path / "automation"
    _write_flow_kb(discovery, sme_ready=["BF-LOGIN-001"])
    _write_automation(automation, "BF-LOGIN-001", "PENDING_SME_APPROVAL")
    return discovery, automation


def _graph(discovery: Path, automation: Path) -> FlowKnowledgeGraph:
    return FlowKnowledgeGraph(discovery_root=discovery, automation_dir=automation)


def test_gate_pending_cannot_execute(gate_workspace: tuple[Path, Path]) -> None:
    discovery, automation = gate_workspace
    decision = _graph(discovery, automation).evaluate_execution("BF-LOGIN-001")
    assert decision.executable is False
    assert decision.reason_code == "approval.pending"
    assert decision.approval_status == "PENDING_SME_APPROVAL"


def test_gate_rejected_cannot_execute(gate_workspace: tuple[Path, Path]) -> None:
    discovery, automation = gate_workspace
    artifact = automation / "test-design" / "flows" / "BF-LOGIN-001" / "test-cases.yaml"
    artifact.write_text("flow_id: BF-LOGIN-001\nstatus: REJECTED\n", encoding="utf-8")
    decision = _graph(discovery, automation).evaluate_execution("BF-LOGIN-001")
    assert decision.executable is False
    assert decision.reason_code == "approval.rejected"


def test_gate_approved_and_ready_can_execute(gate_workspace: tuple[Path, Path]) -> None:
    discovery, automation = gate_workspace
    artifact = automation / "test-design" / "flows" / "BF-LOGIN-001" / "test-cases.yaml"
    artifact.write_text("flow_id: BF-LOGIN-001\nstatus: APPROVED\n", encoding="utf-8")
    _write_approval_log(automation, "BF-LOGIN-001")
    decision = _graph(discovery, automation).evaluate_execution("BF-LOGIN-001")
    assert decision.executable is True
    assert decision.reason_code == "gate.executable"
    assert decision.in_sme_ready is True
    assert decision.kb_ready is True


def test_gate_approved_not_sme_ready_cannot_execute(gate_workspace: tuple[Path, Path]) -> None:
    discovery, automation = gate_workspace
    index_path = discovery / "flows" / "index.yaml"
    index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    index["sme_ready"] = []
    index_path.write_text(yaml.safe_dump(index), encoding="utf-8")
    artifact = automation / "test-design" / "flows" / "BF-LOGIN-001" / "test-cases.yaml"
    artifact.write_text("flow_id: BF-LOGIN-001\nstatus: APPROVED\n", encoding="utf-8")
    _write_approval_log(automation, "BF-LOGIN-001")
    decision = _graph(discovery, automation).evaluate_execution("BF-LOGIN-001")
    assert decision.executable is False
    assert decision.reason_code == "kb.not_sme_ready"


def test_gate_stale_approval_cannot_execute(gate_workspace: tuple[Path, Path]) -> None:
    discovery, automation = gate_workspace
    artifact = automation / "test-design" / "flows" / "BF-LOGIN-001" / "test-cases.yaml"
    artifact.write_text("flow_id: BF-LOGIN-001\nstatus: APPROVED\n", encoding="utf-8")
    _write_approval_log(automation, "BF-LOGIN-001", decided_at="2020-01-01T00:00:00+00:00")
    decision = _graph(discovery, automation).evaluate_execution("BF-LOGIN-001")
    assert decision.executable is False
    assert decision.reason_code == "approval.stale"
    assert decision.approval_stale is True


def test_gate_invalid_transition_rejected() -> None:
    assert ExecutionGate.is_valid_transition("PENDING_SME_APPROVAL", "APPROVED") is True
    assert ExecutionGate.is_valid_transition("PENDING_SME_APPROVAL", "REJECTED") is True
    assert ExecutionGate.is_valid_transition("REJECTED", "PENDING_SME_APPROVAL") is True
    assert ExecutionGate.is_valid_transition("APPROVED", "REJECTED") is False
    assert ExecutionGate.is_valid_transition("APPROVED", "APPROVED") is False


def test_gate_approved_missing_log_is_stale(gate_workspace: tuple[Path, Path]) -> None:
    discovery, automation = gate_workspace
    artifact = automation / "test-design" / "flows" / "BF-LOGIN-001" / "test-cases.yaml"
    artifact.write_text("flow_id: BF-LOGIN-001\nstatus: APPROVED\n", encoding="utf-8")
    decision = _graph(discovery, automation).evaluate_execution("BF-LOGIN-001")
    assert decision.executable is False
    assert decision.reason_code == "approval.stale"


def test_suite_selector_reports_blocked_login_flow() -> None:
    from qa_orchestrator.intent_classifier import IntentClassifier
    from qa_orchestrator.llm_client import PlannerLlmClient
    from qa_orchestrator.suite_selector import SuiteSelector

    graph = FlowKnowledgeGraph(discovery_root="data/discovery-kb")
    classifier = IntentClassifier(graph, PlannerLlmClient(enabled=False))
    intent = classifier.classify("run positive login")
    plan = SuiteSelector(graph).select(intent)
    assert "BF-LOGIN-001" in plan.blocked_flows
    assert "BF-LOGIN-001" not in plan.flow_ids
    assert plan.commands == []
    assert any(g.flow_id == "BF-LOGIN-001" and g.reason_code == "approval.pending" for g in plan.execution_gates)
