"""Structured decision diagnostics for blocked / review terminal states."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from qa_orchestrator.execution_gate import ExecutionGateDecision

if TYPE_CHECKING:
    from qa_orchestrator.agent_models import AgentRunState
    from qa_orchestrator.execution_gate import ExecutionGate
    from qa_orchestrator.models import (
        ExecutionResult,
        IntentClassification,
        PlanningResult,
        SuiteSelectionPlan,
        ValidationResult,
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _selected_test_case_ids(state: "AgentRunState | None") -> list[str]:
    if not state:
        return []
    meta_ids = state.metadata.get("executed_test_case_ids")
    if isinstance(meta_ids, list) and meta_ids:
        return [str(x) for x in meta_ids]
    if state.current_test:
        return [state.current_test]
    return []


def build_validation_phase_b_diagnostic(
    *,
    run_id: str | None,
    validation: "ValidationResult",
    gt_id: str,
    state: "AgentRunState | None" = None,
    execution: "ExecutionResult | None" = None,
) -> dict[str, Any]:
    return {
        "decision": validation.conclusion,
        "run_id": run_id,
        "stage": "validation_phase_b",
        "timestamp": utc_now_iso(),
        "reason_code": validation.reason_code,
        "message": validation.summary,
        "gt_id": gt_id,
        "selected_test_case_ids": _selected_test_case_ids(state),
        "ground_truth": {
            "approved_available": True,
            "matched_for_goal": True,
            "phase": "B",
            "gt_id": gt_id,
        },
        "evidence": {
            "execution_ok": execution.ok if execution else None,
            "execution_mode": execution.mode if execution else None,
        },
    }


def _failed_checks_from_gate(decision: ExecutionGateDecision) -> list[str]:
    code = decision.reason_code
    checks: list[str] = []
    if code == "approval.missing":
        checks.append("yaml_approved")
    elif code == "approval.pending":
        checks.append("yaml_approved")
    elif code == "approval.rejected":
        checks.append("yaml_approved")
    elif code == "approval.stale":
        checks.extend(["approval_log_valid", "approval_stale"])
    elif code == "kb.not_sme_ready":
        checks.append("sme_ready")
    elif code.startswith("kb."):
        checks.append("kb_ready")
    elif not decision.catalog_automated:
        checks.append("catalog_automated")
    return checks


def build_execution_gate_block_diagnostic(
    gate: ExecutionGate,
    flow_id: str,
    *,
    decision: ExecutionGateDecision | None = None,
    run_id: str | None = None,
    stage: str = "execution_gate",
) -> dict[str, Any] | None:
    from qa_orchestrator.execution_gate import CANONICAL_ARTIFACT

    decision = decision or gate.evaluate(flow_id)
    if decision.executable:
        return None

    status = decision.approval_status
    yaml_approved = status == "APPROVED"
    approval_stale = bool(decision.approval_stale or decision.reason_code == "approval.stale")
    approval_log_valid = yaml_approved and not approval_stale and decision.reason_code != "approval.missing"

    artifact_path = gate.design_root / flow_id / CANONICAL_ARTIFACT
    test_case_ready = artifact_path.exists() and status is not None

    checks = {
        "yaml_approved": yaml_approved,
        "approval_log_valid": approval_log_valid,
        "approval_stale": approval_stale,
        "sme_ready": decision.in_sme_ready,
        "catalog_automated": decision.catalog_automated,
        "kb_ready": decision.kb_ready,
        "test_case_ready": test_case_ready,
        "parameter_valid": True,
        "other": decision.reason_code.startswith("kb.") and decision.kb_ready is False,
    }
    failed = _failed_checks_from_gate(decision)
    if not failed and not decision.executable:
        failed = [k for k, ok in checks.items() if k != "parameter_valid" and not ok]

    return {
        "decision": "BLOCK",
        "run_id": run_id,
        "stage": stage,
        "timestamp": utc_now_iso(),
        "flow_id": flow_id,
        "reason_code": decision.reason_code,
        "message": decision.message,
        "checks": checks,
        "failed_checks": failed,
        "source": "ExecutionGate.evaluate",
    }


def build_validation_phase_a_diagnostic(
    *,
    run_id: str | None,
    validation: ValidationResult,
    goal: str,
    execution: ExecutionResult,
    intent: IntentClassification | None = None,
    suite_plan: SuiteSelectionPlan | None = None,
    planning: PlanningResult | None = None,
    state: AgentRunState | None = None,
    gate: ExecutionGate | None = None,
    approved_gt_available: bool = False,
    matched_for_goal: bool | None = None,
    skip_execution: bool | None = None,
) -> dict[str, Any]:
    selected_flows = list(state.selected_flows if state else planning.selected_flows if planning else [])
    if suite_plan and suite_plan.flow_ids:
        selected_flows = list(dict.fromkeys([*selected_flows, *suite_plan.flow_ids]))

    gate_rows: list[dict[str, Any]] = []
    if planning:
        for snap in planning.execution_gates:
            row = {
                "flow_id": snap.flow_id,
                "executable": snap.executable,
                "reason_code": snap.reason_code,
            }
            if gate and not snap.executable:
                block = build_execution_gate_block_diagnostic(gate, snap.flow_id, run_id=run_id)
                if block:
                    row["block_diagnostic"] = block
            gate_rows.append(row)

    param_ok = True
    param_detail: dict[str, Any] = {}
    if planning and planning.validated_parameters is not None:
        param_detail = dict(planning.validated_parameters)
    if intent and intent.params:
        param_detail = {**param_detail, **intent.params}

    failed_condition = "unknown"
    failed_checks: list[str] = []
    for finding in validation.findings:
        msg = finding.message.lower()
        if finding.code in {"param.invalid", "parameter.invalid"} or "invalid param" in msg:
            param_ok = False
            failed_condition = "invalid_parameter"
            failed_checks.append("parameter_valid")
            break

    if validation.conclusion == "NEEDS_REVIEW" and validation.reason_code == "validator.pre_gt_honest":
        failed_condition = "no_approved_ground_truth"
        failed_checks.append("ground_truth")
        if not approved_gt_available:
            failed_checks.append("ground_truth_available")
    elif validation.conclusion == "FAIL" and validation.reason_code == "validator.technical_failure":
        if failed_condition == "unknown":
            failed_condition = "technical_validation_failure"
        failed_checks.extend([f.code for f in validation.findings if f.severity == "error"])
    if execution.mode == "skipped":
        failed_checks.append("playwright_not_executed")
    elif execution.mode.startswith("playwright_dry_run"):
        failed_checks.append("playwright_dry_run_only")
    if skip_execution:
        failed_checks.append("skip_execution_flag")

    evidence_count = len(state.evidence_paths) if state else 0
    for obs in execution.observations:
        if obs.screenshot_path:
            evidence_count += 1

    current_action = None
    if state and state.current_action:
        current_action = state.current_action.type
    elif state and state.decision_journal:
        current_action = state.decision_journal[-1].decision

    return {
        "decision": validation.conclusion,
        "run_id": run_id,
        "stage": "validation_phase_a",
        "timestamp": utc_now_iso(),
        "reason_code": validation.reason_code,
        "message": validation.summary,
        "failed_condition": failed_condition,
        "failed_checks": list(dict.fromkeys(failed_checks)),
        "run_status": state.status if state else None,
        "selected_flow_ids": selected_flows,
        "primary_executable_flow_id": (
            suite_plan.primary_executable_flow_id if suite_plan else (selected_flows[0] if selected_flows else None)
        ),
        "supporting_flow_ids": list(suite_plan.supporting_flow_ids) if suite_plan else [],
        "selected_test_case_ids": _selected_test_case_ids(state),
        "current_action": current_action,
        "gate_decisions": gate_rows,
        "approval_state": {
            "requires_human_approval": planning.requires_human_approval if planning else None,
            "execution_allowed": planning.execution_allowed if planning else None,
            "blocked_flows": list(planning.blocked_flows) if planning else [],
        },
        "parameter_validation": {
            "ok": param_ok,
            "validated_parameters": param_detail,
        },
        "checks": {
            "parameter_valid": param_ok,
            "ground_truth": "ground_truth" not in failed_checks,
        },
        "ground_truth": {
            "approved_available": approved_gt_available,
            "matched_for_goal": approved_gt_available if matched_for_goal is None else matched_for_goal,
            "phase": validation.phase,
        },
        "evidence": {
            "paths_count": evidence_count,
            "execution_mode": execution.mode,
            "execution_ok": execution.ok,
        },
        "resume": {
            "applicable": state.status == "WAITING_FOR_APPROVAL" if state else False,
            "reason_code": state.reason_code if state else None,
        },
        "validation_findings": [f.model_dump() for f in validation.findings[:20]],
        "source": "Validator._validate_phase_a",
    }


def build_terminal_diagnostic(
    *,
    run_id: str,
    stage: str,
    status: str,
    reason_code: str,
    message: str,
    failed_checks: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "decision": status,
        "run_id": run_id,
        "stage": stage,
        "timestamp": utc_now_iso(),
        "reason_code": reason_code,
        "message": message,
        "failed_checks": failed_checks or [],
        "source": "controlled_agent_loop",
    }
    if extra:
        payload.update(extra)
    return payload


def attach_diagnostic_to_state(state: AgentRunState, diagnostic: dict[str, Any] | None) -> None:
    if not diagnostic:
        return
    state.decision_diagnostics = diagnostic
    state.metadata["decision_diagnostics"] = diagnostic


def format_decision_block_log(diagnostic: dict[str, Any]) -> str:
    run_id = diagnostic.get("run_id") or "-"
    stage = diagnostic.get("stage") or "-"
    reason_code = diagnostic.get("reason_code") or "-"
    message = str(diagnostic.get("message") or "")[:240]
    failed = diagnostic.get("failed_checks") or []
    flow_ids = diagnostic.get("selected_flow_ids") or diagnostic.get("flow_id") or []
    if isinstance(flow_ids, str):
        flow_ids = [flow_ids]
    action = diagnostic.get("current_action") or diagnostic.get("decision") or "-"
    return (
        f"[DECISION_BLOCK]\n"
        f"run_id={run_id}\n"
        f"stage={stage}\n"
        f"reason_code={reason_code}\n"
        f"message={message}\n"
        f"failed_checks={','.join(failed) if failed else '-'}\n"
        f"flow_ids={','.join(flow_ids) if flow_ids else '-'}\n"
        f"action={action}\n"
    )


def log_decision_block(diagnostic: dict[str, Any], *, stream: Any | None = None) -> None:
    target = stream if stream is not None else sys.stderr
    target.write(format_decision_block_log(diagnostic))
    if not str(getattr(target, "name", "")).endswith(("stderr", "stdout")):
        try:
            target.flush()
        except Exception:
            pass
