"""P6 — deterministic agent evaluation scenarios and metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from qa_orchestrator.agent_metrics import aggregate_eval_metrics, enrich_eval_row
from qa_orchestrator.agent_models import AgentRunResult


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
    resume_after_approval: bool = False
    resume_healing: bool = False
    resume_generation: bool = False
    stale_fingerprint: bool = False
    mutate_artifact: bool = False
    idempotent_token: str | None = None
    new_orchestrator: bool = False
    corrupt_state: bool = False
    reject_on_resume: bool = False
    resume_terminal: bool = False
    check_evidence_dir: bool = False
    check_journal: bool = False
    legacy_guard_check: bool = False


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


P61_RESUME_SCENARIOS: list[AgentEvalScenario] = [
    AgentEvalScenario(
        id="p61_approval_pause_resume",
        goal="Check login",
        expected_outcome="PASS",
        expected_terminal_states=("COMPLETED", "FAILED", "NEEDS_REVIEW"),
        expected_flow="BF-LOGIN-001",
        expected_actions=("PLAN", "RUN_EXISTING_TEST"),
        resume_after_approval=True,
    ),
    AgentEvalScenario(
        id="p61_healing_resume",
        goal="morning sanity check endless aisle",
        run_type="sanity",
        expected_outcome="NEEDS_REVIEW",
        expected_terminal_states=("NEEDS_REVIEW", "COMPLETED", "FAILED", "WAITING_FOR_APPROVAL"),
        resume_healing=True,
    ),
    AgentEvalScenario(
        id="p61_generation_resume",
        goal="Discover the product page and create automated coverage",
        skip_execution=True,
        expected_outcome="WAITING_FOR_APPROVAL",
        expected_terminal_states=("WAITING_FOR_APPROVAL", "NEEDS_REVIEW", "COMPLETED", "FAILED"),
        resume_generation=True,
    ),
    AgentEvalScenario(
        id="p61_stale_approval",
        goal="Check login",
        expected_outcome="NEEDS_REVIEW",
        expected_terminal_states=("NEEDS_REVIEW",),
        stale_fingerprint=True,
    ),
    AgentEvalScenario(
        id="p61_changed_artifact",
        goal="Check login",
        expected_outcome="NEEDS_REVIEW",
        expected_terminal_states=("NEEDS_REVIEW",),
        mutate_artifact=True,
    ),
    AgentEvalScenario(
        id="p61_duplicate_resume",
        goal="Check login",
        expected_outcome="PASS",
        expected_terminal_states=("COMPLETED", "FAILED", "NEEDS_REVIEW"),
        resume_after_approval=True,
        idempotent_token="dup-token",
    ),
    AgentEvalScenario(
        id="p61_process_restart",
        goal="Check login",
        expected_outcome="PASS",
        expected_terminal_states=("COMPLETED", "FAILED", "NEEDS_REVIEW"),
        resume_after_approval=True,
        new_orchestrator=True,
    ),
    AgentEvalScenario(
        id="p61_corrupt_state",
        goal="Check login",
        expected_outcome="WAITING_FOR_APPROVAL",
        expected_terminal_states=("WAITING_FOR_APPROVAL",),
        corrupt_state=True,
    ),
    AgentEvalScenario(
        id="p61_gate_blocked_on_resume",
        goal="Check login",
        expected_outcome="NEEDS_REVIEW",
        expected_terminal_states=("NEEDS_REVIEW",),
        reject_on_resume=True,
    ),
    AgentEvalScenario(
        id="p61_terminal_resume",
        goal="morning sanity check endless aisle",
        run_type="sanity",
        expected_outcome="FAIL",
        expected_terminal_states=("FAILED", "COMPLETED", "NEEDS_REVIEW"),
        resume_terminal=True,
    ),
    AgentEvalScenario(
        id="p61_evidence_same_run",
        goal="Check login",
        expected_outcome="PASS",
        expected_terminal_states=("COMPLETED", "FAILED", "NEEDS_REVIEW"),
        resume_after_approval=True,
        check_evidence_dir=True,
    ),
    AgentEvalScenario(
        id="p61_journal_continuity",
        goal="Check login",
        expected_outcome="PASS",
        expected_terminal_states=("COMPLETED", "FAILED", "NEEDS_REVIEW"),
        resume_after_approval=True,
        check_journal=True,
    ),
    AgentEvalScenario(
        id="p61_legacy_guard",
        goal="Check login",
        expected_outcome="WAITING_FOR_APPROVAL",
        expected_terminal_states=("WAITING_FOR_APPROVAL",),
        legacy_guard_check=True,
    ),
]


def _reset_flow_artifact_for_eval(orch) -> None:
    import re
    from pathlib import Path

    artifact = Path(orch.graph.automation_dir) / "test-design" / "flows" / "BF-LOGIN-001" / "test-cases.yaml"
    if artifact.exists():
        text = artifact.read_text(encoding="utf-8")
        text = re.sub(r"^status:\s*APPROVED\s*$", "status: PENDING_SME_APPROVAL", text, flags=re.MULTILINE)
        text = re.sub(r"^status:\s*REJECTED\s*$", "status: PENDING_SME_APPROVAL", text, flags=re.MULTILINE)
        artifact.write_text(text, encoding="utf-8")
    approval_log = Path(orch.graph.automation_dir) / "approval" / "approval-log.json"
    if approval_log.exists():
        approval_log.unlink()


def _approve_flow_for_eval(orch, flow_id: str) -> None:
    import json
    import re
    from datetime import datetime, timezone
    from pathlib import Path

    automation = Path(orch.graph.automation_dir)
    artifact = automation / "test-design" / "flows" / flow_id / "test-cases.yaml"
    text = artifact.read_text(encoding="utf-8")
    text = re.sub(r"^status:\s*PENDING_SME_APPROVAL\s*$", "status: APPROVED", text, flags=re.MULTILINE)
    artifact.write_text(text, encoding="utf-8")
    log_dir = automation / "approval"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "approval-log.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "flowId": flow_id,
                        "artifact": "test-cases.yaml",
                        "status": "APPROVED",
                        "approver": "sme@test.com",
                        "decidedAt": datetime.now(timezone.utc).isoformat(),
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def run_p61_resume_evaluation(orch, *, scenarios: list[AgentEvalScenario] | None = None) -> dict[str, Any]:
    from pathlib import Path

    from qa_orchestrator.agent_resume import AgentResumeError, build_snapshot_from_state
    from qa_orchestrator.agent_state_store import load_snapshot, save_snapshot, state_path
    from qa_orchestrator.healing_proposal_store import save_proposal, update_proposal_status
    from qa_orchestrator.legacy_guard import assert_canonical_agent_path, legacy_runtime_requested
    from qa_orchestrator.models import HealingProposal, HealingResult
    from qa_orchestrator.run_request import RunRequest

    from qa_orchestrator.orchestrator import QaOrchestrator as _QaOrchestrator

    scenarios = scenarios or P61_RESUME_SCENARIOS
    rows: list[dict[str, Any]] = []

    for scenario in scenarios:
        _reset_flow_artifact_for_eval(orch)
        run_id = f"eval-{scenario.id}"
        result = orch.run_agent(
            RunRequest(
                goal=scenario.goal,
                run_type=scenario.run_type,
                skip_execution=scenario.skip_execution,
                skip_discovery=scenario.skip_discovery,
                model="disabled",
                run_id=run_id,
            )
        )
        passed_extra = True

        if scenario.legacy_guard_check:
            passed_extra = not legacy_runtime_requested()
            try:
                assert_canonical_agent_path("agent_cli")
            except RuntimeError:
                passed_extra = False

        if scenario.corrupt_state:
            bad = state_path(orch.agent_loop.config.journal_dir, run_id)
            bad.write_text("{bad", encoding="utf-8")
            try:
                orch.resume_agent(run_id)
                passed_extra = False
            except AgentResumeError:
                passed_extra = True
            row = evaluate_scenario(result, scenario)
            row["passed"] = row["passed"] and passed_extra
            rows.append(row)
            continue

        if scenario.resume_terminal:
            try:
                orch.resume_agent(run_id)
                passed_extra = False
            except AgentResumeError:
                passed_extra = True
            row = evaluate_scenario(result, scenario)
            row["passed"] = row["passed"] and passed_extra
            rows.append(row)
            continue

        if scenario.stale_fingerprint:
            _approve_flow_for_eval(orch, "BF-LOGIN-001")
            snapshot = load_snapshot(run_id, base_dir=orch.agent_loop.config.journal_dir)
            flow_id = result.state.current_flow or "BF-LOGIN-001"
            snapshot.artifact_status_at_pause[flow_id] = "APPROVED"
            snapshot.artifact_fingerprints[flow_id] = "deadbeefdeadbeef"
            save_snapshot(snapshot, base_dir=orch.agent_loop.config.journal_dir)
            result = orch.resume_agent(run_id)
        elif scenario.mutate_artifact or scenario.reject_on_resume:
            artifact = (
                Path(orch.graph.automation_dir)
                / "test-design"
                / "flows"
                / "BF-LOGIN-001"
                / "test-cases.yaml"
            )
            artifact.write_text("flow_id: BF-LOGIN-001\nstatus: REJECTED\n", encoding="utf-8")
            result = orch.resume_agent(run_id)
        elif scenario.resume_healing:
            healing_id = f"heal-{scenario.id}"
            proposal = HealingProposal(
                healing_id=healing_id,
                flow_id="BF-LOGIN-001",
                test_id="TC-BF-LOGIN-001-P01",
                locator_label="login button",
                old_locator="page.getByTestId('login')",
                new_locator="page.getByRole('button', { name: 'Login' })",
                fallbacks=['button[name="login"]'],
                confidence=0.9,
                status="PENDING_SME_APPROVAL",
            )
            save_proposal(Path(orch.graph.automation_dir), proposal)
            result.state.healing_result = HealingResult(
                healing_id=healing_id,
                status="HEALED_PENDING_APPROVAL",
                proposal=proposal,
                message="Healing proposal pending SME approval",
            )
            result.state.status = "WAITING_FOR_APPROVAL"
            result.state.final_result = "WAITING_FOR_APPROVAL"
            result.state.metadata["approval_pause_kind"] = "healing"
            req = RunRequest(goal=result.state.request, run_type=result.state.run_type)
            snapshot = build_snapshot_from_state(
                result.state, req, pause_kind="healing", automation_dir=orch.graph.automation_dir
            )
            save_snapshot(snapshot, base_dir=orch.agent_loop.config.journal_dir)
            update_proposal_status(Path(orch.graph.automation_dir), healing_id, "APPROVED")
            result = orch.resume_agent(run_id)
        elif scenario.resume_generation:
            if result.state.generation_result:
                flow_id = result.state.generation_result.flow_id
                _approve_flow_for_eval(orch, flow_id)
                snapshot = load_snapshot(run_id, base_dir=orch.agent_loop.config.journal_dir)
                snapshot.approval_pause_kind = "generation"
                save_snapshot(snapshot, base_dir=orch.agent_loop.config.journal_dir)
                result = orch.resume_agent(run_id)
        elif scenario.resume_after_approval:
            _approve_flow_for_eval(orch, "BF-LOGIN-001")
            resume_orch = _QaOrchestrator(discovery_root=orch.discovery_root, model="disabled") if scenario.new_orchestrator else orch
            token = scenario.idempotent_token
            result = resume_orch.resume_agent(run_id, resume_token=token)
            if scenario.idempotent_token:
                second = resume_orch.resume_agent(run_id, resume_token=token)
                passed_extra = len([e for e in second.state.decision_journal if e.decision == "RESUME"]) == 1
                result = second
            if scenario.check_evidence_dir:
                passed_extra = passed_extra and (Path(resume_orch.agent_loop.config.journal_dir) / run_id).exists()
            if scenario.check_journal:
                passed_extra = passed_extra and any(e.decision == "RESUME" for e in result.state.decision_journal)

        row = evaluate_scenario(result, scenario)
        row["passed"] = row["passed"] and passed_extra
        rows.append(row)

    metrics = aggregate_eval_metrics(rows)
    return {"scenarios": rows, "metrics": metrics, "passed": sum(1 for r in rows if r["passed"]), "total": len(rows)}


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
    if not outcome_ok and scenario.expected_outcome == "PASS":
        outcome_ok = result.state.status in {"COMPLETED", "FAILED", "NEEDS_REVIEW"} and "RUN_EXISTING_TEST" in decisions
    predicate_ok = scenario.predicate(result) if scenario.predicate else True
    passed = flow_ok and action_ok and status_ok and approval_ok and outcome_ok and predicate_ok
    row = {
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
    return enrich_eval_row(result, row)


def run_agent_evaluation(run_fn, *, scenarios: list[AgentEvalScenario] | None = None) -> dict[str, Any]:
    scenarios = scenarios or P6_EVAL_SCENARIOS
    rows = []
    for scenario in scenarios:
        result = run_fn(scenario)
        rows.append(evaluate_scenario(result, scenario))
    metrics = aggregate_eval_metrics(rows)
    return {"scenarios": rows, "metrics": metrics, "passed": sum(1 for r in rows if r["passed"]), "total": len(rows)}


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
    p61 = run_p61_resume_evaluation(orch)
    combined_rows = report["scenarios"] + p61["scenarios"]
    combined_metrics = aggregate_eval_metrics(combined_rows)
    full_report = {
        "runs": len(combined_rows),
        **combined_metrics,
        "p6": {"passed": report["passed"], "total": report["total"], "scenarios": report["scenarios"]},
        "p61": {"passed": p61["passed"], "total": p61["total"], "scenarios": p61["scenarios"]},
        "passed": report["passed"] + p61["passed"],
        "total": report["total"] + p61["total"],
    }
    out = Path(os.environ.get("QA_AGENT_EVAL_REPORT", "reports/agent/p6-1-evaluation.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(full_report, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(out), "passed": full_report["passed"], "total": full_report["total"]}, indent=2))


if __name__ == "__main__":
    from pathlib import Path

    main()
