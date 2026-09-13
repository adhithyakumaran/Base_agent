"""P6 — deterministic agent evaluation scenarios and metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from qa_orchestrator.agent_models import AgentMetrics, AgentRunResult


@dataclass(frozen=True)
class AgentEvalScenario:
    id: str
    goal: str
    expected_outcome: str
    run_type: str = "adhoc"
    skip_execution: bool = False
    skip_discovery: bool = False
    expected_terminal_states: tuple[str, ...] = ()
    expected_flow: str | None = None
    expected_actions: tuple[str, ...] = ()
    expected_approval: bool = False
    env: dict[str, str] | None = None
    predicate: Callable[[AgentRunResult], bool] | None = None


P6_EVAL_SCENARIOS: list[AgentEvalScenario] = [
    AgentEvalScenario(
        id="check_login",
        goal="Check login",
        expected_outcome="WAITING_FOR_APPROVAL",
        expected_terminal_states=("WAITING_FOR_APPROVAL",),
        expected_flow="BF-LOGIN-001",
        expected_actions=("PLAN",),
        expected_approval=True,
    ),
    AgentEvalScenario(
        id="invalid_login",
        goal="Test invalid login",
        expected_outcome="WAITING_FOR_APPROVAL",
        expected_terminal_states=("WAITING_FOR_APPROVAL",),
        expected_flow="BF-LOGIN-001",
        expected_approval=True,
    ),
    AgentEvalScenario(
        id="search_sku",
        goal="Search SKU ABC123",
        expected_outcome="WAITING_FOR_APPROVAL",
        expected_terminal_states=("WAITING_FOR_APPROVAL",),
        expected_flow="BF-PRODUCT-003",
        expected_approval=True,
    ),
    AgentEvalScenario(
        id="approved_flow_execution",
        goal="morning sanity check endless aisle",
        run_type="sanity",
        expected_outcome="FAIL",
        expected_terminal_states=("FAILED", "COMPLETED", "NEEDS_REVIEW"),
        expected_actions=("PLAN", "RUN_EXISTING_TEST"),
    ),
    AgentEvalScenario(
        id="pending_approval",
        goal="run positive login",
        expected_outcome="WAITING_FOR_APPROVAL",
        expected_terminal_states=("WAITING_FOR_APPROVAL",),
        expected_flow="BF-LOGIN-001",
        expected_approval=True,
    ),
    AgentEvalScenario(
        id="blocked_flow",
        goal="run positive login",
        expected_outcome="WAITING_FOR_APPROVAL",
        expected_terminal_states=("WAITING_FOR_APPROVAL",),
        expected_flow="BF-LOGIN-001",
        expected_approval=True,
    ),
    AgentEvalScenario(
        id="exploration_required",
        goal="Discover the product page and create automated coverage",
        skip_execution=True,
        expected_outcome="WAITING_FOR_APPROVAL",
        expected_terminal_states=("WAITING_FOR_APPROVAL", "READY", "NEEDS_REVIEW"),
        expected_actions=("PLAN",),
    ),
    AgentEvalScenario(
        id="generation_requires_approval",
        goal="Discover the product page and create automated coverage",
        skip_execution=True,
        expected_outcome="WAITING_FOR_APPROVAL",
        expected_terminal_states=("WAITING_FOR_APPROVAL", "NEEDS_REVIEW"),
        expected_approval=True,
        predicate=lambda r: r.state.generation_result is not None or r.state.exploration is not None,
    ),
    AgentEvalScenario(
        id="locator_healing",
        goal="morning sanity check endless aisle",
        run_type="sanity",
        expected_outcome="FAIL",
        expected_terminal_states=("FAILED", "NEEDS_REVIEW", "COMPLETED"),
    ),
    AgentEvalScenario(
        id="application_no_healing",
        goal="morning sanity check endless aisle",
        run_type="sanity",
        expected_outcome="FAIL",
        expected_terminal_states=("FAILED", "NEEDS_REVIEW", "COMPLETED"),
    ),
    AgentEvalScenario(
        id="ambiguous_verification",
        goal="unrelated goal xyz not in ground truth",
        skip_execution=True,
        expected_outcome="WAITING_FOR_APPROVAL",
        expected_terminal_states=("WAITING_FOR_APPROVAL", "NEEDS_REVIEW"),
    ),
    AgentEvalScenario(
        id="max_recovery_limit",
        goal="morning sanity check endless aisle",
        run_type="sanity",
        expected_outcome="FAIL",
        expected_terminal_states=("FAILED", "NEEDS_REVIEW", "COMPLETED"),
        env={"QA_AGENT_MAX_RECOVERIES": "0"},
    ),
    AgentEvalScenario(
        id="max_iteration_limit",
        goal="morning sanity check endless aisle",
        run_type="sanity",
        expected_outcome="FAIL",
        expected_terminal_states=("FAILED", "NEEDS_REVIEW", "COMPLETED"),
        env={"QA_AGENT_MAX_ITERATIONS": "1"},
    ),
    AgentEvalScenario(
        id="qdrant_unavailable",
        goal="Check login",
        expected_outcome="WAITING_FOR_APPROVAL",
        expected_terminal_states=("WAITING_FOR_APPROVAL",),
        env={"QA_QDRANT_ENABLED": "false"},
    ),
    AgentEvalScenario(
        id="embedding_unavailable",
        goal="Check login",
        expected_outcome="WAITING_FOR_APPROVAL",
        expected_terminal_states=("WAITING_FOR_APPROVAL",),
        env={"QA_EMBEDDING_PROVIDER": "deterministic", "QA_QDRANT_ENABLED": "false"},
    ),
    AgentEvalScenario(
        id="exact_flow_id",
        goal="BF-PRODUCT-003",
        expected_outcome="WAITING_FOR_APPROVAL",
        expected_terminal_states=("WAITING_FOR_APPROVAL",),
        expected_flow="BF-PRODUCT-003",
    ),
    AgentEvalScenario(
        id="unknown_request",
        goal="quantum flux capacitor calibration",
        skip_execution=True,
        expected_outcome="WAITING_FOR_APPROVAL",
        expected_terminal_states=("WAITING_FOR_APPROVAL", "NEEDS_REVIEW"),
    ),
]


def evaluate_scenario(result: AgentRunResult, scenario: AgentEvalScenario) -> dict[str, Any]:
    state = result.state
    decisions = [entry.decision for entry in state.decision_journal]
    flow_ok = True
    if scenario.expected_flow:
        flows = (state.plan.candidate_flows if state.plan else []) + state.selected_flows
        flow_ok = scenario.expected_flow in flows
    action_ok = all(action in decisions for action in scenario.expected_actions) if scenario.expected_actions else True
    status_ok = (not scenario.expected_terminal_states) or state.status in scenario.expected_terminal_states
    approval_ok = (state.status == "WAITING_FOR_APPROVAL") == scenario.expected_approval or not scenario.expected_approval
    outcome_ok = result.conclusion == scenario.expected_outcome
    predicate_ok = scenario.predicate(result) if scenario.predicate else True
    passed = flow_ok and action_ok and status_ok and approval_ok and outcome_ok and predicate_ok
    return {
        "id": scenario.id,
        "passed": passed,
        "expected_terminal_states": scenario.expected_terminal_states,
        "actual_status": state.status,
        "expected_outcome": scenario.expected_outcome,
        "actual_outcome": result.conclusion,
        "decisions": decisions,
        "flow_ok": flow_ok,
        "action_ok": action_ok,
        "journal_entries": len(state.decision_journal),
    }


def aggregate_metrics(results: list[dict[str, Any]]) -> AgentMetrics:
    total = len(results) or 1
    passed = sum(1 for row in results if row["passed"])
    approvals = sum(1 for row in results if row["actual_status"] == "WAITING_FOR_APPROVAL")
    blocked = sum(1 for row in results if row["actual_status"] == "BLOCKED")
    needs_review = sum(1 for row in results if row["actual_outcome"] == "NEEDS_REVIEW")
    return AgentMetrics(
        planning_success_rate=round(passed / total, 4),
        execution_success_rate=round(sum(1 for r in results if r.get("action_ok")) / total, 4),
        approval_escalation_rate=round(approvals / total, 4),
        blocked_rate=round(blocked / total, 4),
        needs_review_rate=round(needs_review / total, 4),
        decision_trace_completeness=round(
            sum(1 for r in results if r.get("journal_entries", 0) > 0) / total,
            4,
        ),
    )


def run_agent_evaluation(run_fn, *, scenarios: list[AgentEvalScenario] | None = None) -> dict[str, Any]:
    scenarios = scenarios or P6_EVAL_SCENARIOS
    rows = []
    for scenario in scenarios:
        result = run_fn(scenario)
        rows.append(evaluate_scenario(result, scenario))
    return {"scenarios": rows, "metrics": aggregate_metrics(rows).model_dump(), "passed": sum(1 for r in rows if r["passed"]), "total": len(rows)}


def main() -> None:
    import json
    import os

    os.environ.setdefault("QA_RUNNER", "dry_run")
    os.environ.setdefault("LLM_ENABLED", "false")
    from qa_orchestrator.orchestrator import QaOrchestrator
    from qa_orchestrator.run_request import RunRequest

    orch = QaOrchestrator()

    def _run(scenario: AgentEvalScenario) -> AgentRunResult:
        if scenario.env:
            for key, value in scenario.env.items():
                os.environ[key] = value
        return orch.run_agent(
            RunRequest(
                goal=scenario.goal,
                run_type=scenario.run_type,
                skip_execution=scenario.skip_execution,
                skip_discovery=scenario.skip_discovery,
                model="disabled",
            )
        )

    report = run_agent_evaluation(_run)
    out = Path(os.environ.get("QA_AGENT_EVAL_REPORT", "reports/agent/p6-evaluation.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(out), "passed": report["passed"], "total": report["total"]}, indent=2))


if __name__ == "__main__":
    from pathlib import Path

    main()
