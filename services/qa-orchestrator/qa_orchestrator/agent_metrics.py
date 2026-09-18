"""P6.1 — explicit agent evaluation metrics."""

from __future__ import annotations

from typing import Any

from qa_orchestrator.agent_models import AgentMetrics, AgentRunResult


def _reached_executing(result: AgentRunResult) -> bool:
    decisions = [entry.decision for entry in result.state.decision_journal]
    return "RUN_EXISTING_TEST" in decisions or result.state.status in {"EXECUTING", "OBSERVING", "VERIFYING", "COMPLETED", "FAILED"}


def _execution_ok(result: AgentRunResult) -> bool:
    return bool(result.state.execution and result.state.execution.ok)


def _verification_pass(result: AgentRunResult) -> bool:
    return result.state.validation is not None and result.state.validation.conclusion == "PASS"


def _recovery_verified(result: AgentRunResult) -> bool:
    for record in result.state.recovery_history:
        if record.recovery_attempted and "HEALED" in record.recovery_outcome:
            return _verification_pass(result) or result.state.validation is None
    return False


def enrich_eval_row(result: AgentRunResult, scenario_row: dict[str, Any]) -> dict[str, Any]:
    state = result.state
    reached = _reached_executing(result)
    row = dict(scenario_row)
    row.update(
        {
            "terminal_status": state.status,
            "reached_executing": reached,
            "execution_ok": _execution_ok(result) if reached else False,
            "verification_pass": _verification_pass(result),
            "recovery_attempted": state.recovery_count > 0,
            "recovery_count": state.recovery_count,
            "recovery_verified": _recovery_verified(result),
            "terminal_accurate": row.get("passed", False),
            "plan_ok": state.plan is not None,
            "approval_routed_correctly": row.get("passed", False)
            or (state.status == "WAITING_FOR_APPROVAL" and row.get("expected_outcome") == "WAITING_FOR_APPROVAL"),
        }
    )
    return row


def aggregate_eval_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows) or 1
    executing = [r for r in rows if r.get("reached_executing")]
    failed_runs = [r for r in rows if r.get("recovery_attempted")]
    recovery_success = [r for r in rows if r.get("recovery_verified")]
    false_recovery = [
        r
        for r in rows
        if r.get("recovery_attempted") and not r.get("recovery_verified") and r.get("terminal_status") != "WAITING_FOR_APPROVAL"
    ]
    return {
        "runs": total,
        "planning_success_rate": round(sum(1 for r in rows if r.get("plan_ok")) / total, 4),
        "terminal_state_accuracy": round(sum(1 for r in rows if r.get("terminal_accurate")) / total, 4),
        "execution_attempt_rate": round(len(executing) / total, 4),
        "execution_attempt_success_rate": round(
            sum(1 for r in executing if r.get("execution_ok")) / len(executing),
            4,
        )
        if executing
        else 0.0,
        "verification_success_rate": round(
            sum(1 for r in rows if r.get("verification_pass")) / total,
            4,
        ),
        "approval_routing_accuracy": round(
            sum(1 for r in rows if r.get("approval_routed_correctly")) / total,
            4,
        ),
        "recovery_attempt_rate": round(len(failed_runs) / total, 4),
        "recovery_success_rate": round(len(recovery_success) / len(failed_runs), 4) if failed_runs else 0.0,
        "recovery_failure_rate": round(
            (len(failed_runs) - len(recovery_success)) / len(failed_runs),
            4,
        )
        if failed_runs
        else 0.0,
        "false_recovery_rate": round(len(false_recovery) / total, 4),
        "average_recoveries_per_failed_run": round(
            sum(r.get("recovery_count", 0) for r in rows if r.get("recovery_attempted")) / len(failed_runs),
            4,
        )
        if failed_runs
        else 0.0,
        "waiting_for_approval_rate": round(
            sum(1 for r in rows if r.get("terminal_status") == "WAITING_FOR_APPROVAL") / total,
            4,
        ),
        "blocked_rate": round(sum(1 for r in rows if r.get("terminal_status") == "BLOCKED") / total, 4),
        "needs_review_rate": round(
            sum(1 for r in rows if r.get("actual_outcome") == "NEEDS_REVIEW" or r.get("terminal_status") == "NEEDS_REVIEW")
            / total,
            4,
        ),
        "decision_trace_completeness": round(
            sum(1 for r in rows if r.get("journal_entries", 0) > 0) / total,
            4,
        ),
    }


def metrics_from_single_run(result: AgentRunResult) -> AgentMetrics:
    row = enrich_eval_row(result, {"passed": True, "journal_entries": len(result.state.decision_journal)})
    agg = aggregate_eval_metrics([row])
    return AgentMetrics(
        planning_success_rate=agg["planning_success_rate"],
        terminal_state_accuracy=agg["terminal_state_accuracy"],
        execution_attempt_rate=agg["execution_attempt_rate"],
        execution_attempt_success_rate=agg["execution_attempt_success_rate"],
        verification_success_rate=agg["verification_success_rate"],
        approval_routing_accuracy=agg["approval_routing_accuracy"],
        recovery_attempt_rate=agg["recovery_attempt_rate"],
        recovery_success_rate=agg["recovery_success_rate"],
        recovery_failure_rate=agg["recovery_failure_rate"],
        false_recovery_rate=agg["false_recovery_rate"],
        average_recoveries_per_failed_run=agg["average_recoveries_per_failed_run"],
        waiting_for_approval_rate=agg["waiting_for_approval_rate"],
        blocked_rate=agg["blocked_rate"],
        needs_review_rate=agg["needs_review_rate"],
        decision_trace_completeness=agg["decision_trace_completeness"],
        average_iterations=float(result.state.iteration),
        average_recoveries=float(result.state.recovery_count),
        evidence_completeness=min(1.0, len(result.state.evidence_paths) / 3.0) if result.state.execution else 0.0,
    )
