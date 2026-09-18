"""Structured decision diagnostics — gate blocks, Phase A review, resume."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from qa_orchestrator.agent_models import AgentRunState
from qa_orchestrator.decision_diagnostics import (
    build_execution_gate_block_diagnostic,
    build_terminal_diagnostic,
    build_validation_phase_a_diagnostic,
    format_decision_block_log,
)
from qa_orchestrator.execution_gate import ExecutionGate
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.models import (
    ExecutionResult,
    IntentClassification,
    PlanningResult,
    SuiteSelectionPlan,
    ValidationFinding,
    ValidationResult,
)


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
                ],
            }
        ),
        encoding="utf-8",
    )
    (flows_dir / "BF-LOGIN-001.yaml").write_text(
        yaml.safe_dump({"flow_id": "BF-LOGIN-001", "flow_name": "Login", "purpose": "login"}),
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


@pytest.fixture
def gate_workspace(tmp_path: Path) -> tuple[Path, Path]:
    discovery = tmp_path / "discovery"
    automation = tmp_path / "automation"
    _write_flow_kb(discovery, sme_ready=["BF-LOGIN-001"])
    _write_automation(automation, "BF-LOGIN-001", "PENDING_SME_APPROVAL")
    return discovery, automation


def test_gate_block_diagnostic_approval_stale(gate_workspace: tuple[Path, Path]) -> None:
    discovery, automation = gate_workspace
    _write_automation(automation, "BF-LOGIN-001", "APPROVED")
    _write_approval_log(automation, "BF-LOGIN-001", decided_at="2020-01-01T00:00:00+00:00")
    graph = FlowKnowledgeGraph(discovery_root=str(discovery), automation_dir=str(automation))
    gate = ExecutionGate(graph)
    diag = build_execution_gate_block_diagnostic(gate, "BF-LOGIN-001", run_id="run_test")
    assert diag is not None
    assert diag["decision"] == "BLOCK"
    assert diag["reason_code"] == "approval.stale"
    assert "approval_log_valid" in diag["failed_checks"] or "approval_stale" in diag["failed_checks"]
    assert diag["source"] == "ExecutionGate.evaluate"
    assert "run_id=run_test" in format_decision_block_log(diag)


def test_phase_a_diagnostic_missing_ground_truth() -> None:
    validation = ValidationResult(
        phase="A",
        conclusion="NEEDS_REVIEW",
        reason_code="validator.pre_gt_honest",
        summary="Phase A: needs SME GT",
        findings=[],
    )
    execution = ExecutionResult(ok=True, mode="playwright_dry_run", observations=[])
    diag = build_validation_phase_a_diagnostic(
        run_id="run_gt",
        validation=validation,
        goal="Search SKU 552811DUDABA00",
        execution=execution,
        approved_gt_available=False,
    )
    assert diag["stage"] == "validation_phase_a"
    assert diag["reason_code"] == "validator.pre_gt_honest"
    assert diag["failed_condition"] == "no_approved_ground_truth"
    assert "ground_truth" in diag["failed_checks"]
    assert diag["checks"]["ground_truth"] is False


def test_phase_a_diagnostic_invalid_parameter() -> None:
    validation = ValidationResult(
        phase="A",
        conclusion="FAIL",
        reason_code="validator.technical_failure",
        summary="Technical failure",
        findings=[
            ValidationFinding(
                code="execution.failed",
                severity="error",
                message="invalid params: SKU format",
            )
        ],
    )
    diag = build_validation_phase_a_diagnostic(
        run_id="run_param",
        validation=validation,
        goal="Search SKU bad",
        execution=ExecutionResult(ok=False, mode="playwright", observations=[]),
        approved_gt_available=False,
    )
    assert diag["failed_condition"] == "invalid_parameter"
    assert "parameter_valid" in diag["failed_checks"]
    assert diag["parameter_validation"]["ok"] is False


def test_gate_block_none_when_executable(gate_workspace: tuple[Path, Path]) -> None:
    discovery, automation = gate_workspace
    artifact = automation / "test-design" / "flows" / "BF-LOGIN-001" / "test-cases.yaml"
    artifact.write_text("flow_id: BF-LOGIN-001\nstatus: APPROVED\n", encoding="utf-8")
    _write_approval_log(automation, "BF-LOGIN-001")
    graph = FlowKnowledgeGraph(discovery_root=str(discovery), automation_dir=str(automation))
    gate = ExecutionGate(graph)
    assert graph.evaluate_execution("BF-LOGIN-001").executable is True
    assert build_execution_gate_block_diagnostic(gate, "BF-LOGIN-001") is None


def test_terminal_diagnostic_waiting_for_approval() -> None:
    diag = build_terminal_diagnostic(
        run_id="run_wait",
        stage="agent_terminal",
        status="WAITING_FOR_APPROVAL",
        reason_code="approval.pending",
        message="Human approval required",
        failed_checks=["approval.pending"],
        extra={"selected_flow_ids": ["BF-LOGIN-001"]},
    )
    assert diag["reason_code"] == "approval.pending"
    assert diag["stage"] == "agent_terminal"
    assert diag["run_id"] == "run_wait"
    log = format_decision_block_log(diag)
    assert "[DECISION_BLOCK]" in log
    assert "reason_code=approval.pending" in log


def test_resume_needs_review_terminal_diagnostic() -> None:
    diag = build_terminal_diagnostic(
        run_id="run_resume",
        stage="agent_resume",
        status="NEEDS_REVIEW",
        reason_code="approval.stale",
        message="artifact changed after pause",
        failed_checks=["approval.stale"],
        extra={"checkpoint": "before_execution"},
    )
    assert diag["stage"] == "agent_resume"
    assert diag["reason_code"] == "approval.stale"


def test_search_sku_reproduction_diagnostic_like_run_mj4qy16gpz6s() -> None:
    """Mirrors Search SKU / BF-PRODUCT-003 Phase A NEEDS_REVIEW without policy change."""
    goal = "Search SKU 552811DUDABA00"
    state = AgentRunState(
        run_id="run_mj4qy16gpz6s",
        request=goal,
        status="NEEDS_REVIEW",
        selected_flows=["BF-PRODUCT-003", "BF-HOME-010-01"],
    )
    intent = IntentClassification(
        goal=goal,
        execution_mode="adhoc_parameterized",
        capability="search",
        confidence=0.9,
        classifier="rules",
        reasoning="parameterized SKU search",
        params={"sku": "552811DUDABA00"},
    )
    planning = PlanningResult(
        request=state.request,
        intent=intent,
        strategy="REUSE_EXISTING",
        selected_flows=["BF-PRODUCT-003", "BF-HOME-010-01"],
        execution_allowed=True,
        requires_human_approval=False,
    )
    suite = SuiteSelectionPlan(
        flow_ids=["BF-PRODUCT-003"],
        commands=["npm run test:flow:positive -- BF-PRODUCT-003"],
    )
    validation = ValidationResult(
        phase="A",
        conclusion="NEEDS_REVIEW",
        reason_code="validator.pre_gt_honest",
        summary=(
            "Phase A (adhoc_parameterized): plan summary. "
            "Business outcome requires SME Ground Truth approval for PASS."
        ),
        findings=[],
    )
    execution = ExecutionResult(ok=True, mode="skipped", observations=[])
    diag = build_validation_phase_a_diagnostic(
        run_id=state.run_id,
        validation=validation,
        goal=state.request,
        execution=execution,
        intent=None,
        suite_plan=suite,
        planning=planning,
        state=state,
        approved_gt_available=False,
        skip_execution=True,
    )
    assert diag["reason_code"] == "validator.pre_gt_honest"
    assert diag["failed_condition"] == "no_approved_ground_truth"
    assert "ground_truth" in diag["failed_checks"]
    assert "playwright_not_executed" in diag["failed_checks"]
    assert "skip_execution_flag" in diag["failed_checks"]
    assert "BF-PRODUCT-003" in diag["selected_flow_ids"]
    assert diag["evidence"]["execution_mode"] == "skipped"
    log = format_decision_block_log(diag)
    assert "validator.pre_gt_honest" in log
    assert "ground_truth" in log
