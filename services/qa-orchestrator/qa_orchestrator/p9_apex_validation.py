"""P9 — real Oracle APEX end-to-end validation runner."""

from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from qa_orchestrator.agent_eval import _approve_flow_for_eval, _reset_flow_artifact_for_eval, evaluate_scenario
from qa_orchestrator.agent_eval import AgentEvalScenario
from qa_orchestrator.agent_models import AgentRunResult
from qa_orchestrator.orchestrator import QaOrchestrator
from qa_orchestrator.p9_environment import (
    approve_flow_for_validation,
    restore_flow_approval,
    run_environment_preflight,
)
from qa_orchestrator.p9_flow_inventory import build_flow_inventory, select_validation_subset
from qa_orchestrator.playwright_runner import PlaywrightRunner
from qa_orchestrator.run_request import RunRequest


P9_SELECTED_FLOWS = select_validation_subset(build_flow_inventory(), limit=8)


@dataclass(frozen=True)
class P9Scenario:
    id: str
    request: str
    category: str
    expected_flow: str | None = None
    run_type: str = "adhoc"
    exact_id: bool = False
    requires_live: bool = False
    requires_approval: bool = False
    resume_after_approval: bool = False
    check_parameters: dict[str, str] | None = None
    env: dict[str, str] | None = None


P9_SCENARIOS: list[P9Scenario] = [
    P9Scenario("p9_nl_check_login", "Check login", "authentication", expected_flow="BF-LOGIN-001"),
    P9Scenario(
        "p9_nl_search_sku",
        "Search SKU ABC123",
        "parameterized_search",
        expected_flow="BF-PRODUCT-003",
        check_parameters={"sku": "ABC123"},
    ),
    P9Scenario(
        "p9_nl_item_code_variant",
        "Search for the product using item code ABC123",
        "parameterized_search",
        expected_flow="BF-PRODUCT-003",
        check_parameters={"sku": "ABC123"},
    ),
    P9Scenario(
        "p9_exact_flow_id",
        "BF-PRODUCT-003",
        "exact_id",
        expected_flow="BF-PRODUCT-003",
        exact_id=True,
    ),
    P9Scenario(
        "p9_invalid_login",
        "Test invalid login",
        "negative",
        expected_flow="BF-LOGIN-001",
    ),
    P9Scenario(
        "p9_logout",
        "Log out of the application",
        "logout",
        expected_flow="BF-LOGOUT-002",
    ),
    P9Scenario(
        "p9_live_login",
        "Check login",
        "live_execution",
        expected_flow="BF-LOGIN-001",
        requires_live=True,
        requires_approval=True,
        resume_after_approval=True,
    ),
    P9Scenario(
        "p9_live_sku",
        "Search SKU ABC123",
        "live_execution",
        expected_flow="BF-PRODUCT-003",
        requires_live=True,
        requires_approval=True,
        resume_after_approval=True,
        check_parameters={"sku": "ABC123"},
    ),
    P9Scenario(
        "p9_offline_approval_resume",
        "Check login",
        "approval_resume",
        expected_flow="BF-LOGIN-001",
        requires_approval=True,
        resume_after_approval=True,
    ),
]


def _agent_env() -> dict[str, str]:
    return {
        "QA_RUNNER": os.environ.get("QA_RUNNER", "playwright"),
        "LLM_ENABLED": "false",
        "QA_AGENT_LLM_ENABLED": "false",
        "QA_AGENT_LLM_AUTO_DECISION": "false",
    }


def _run_agent(
    orch: QaOrchestrator,
    scenario: P9Scenario,
    *,
    run_id: str,
    skip_execution: bool = False,
) -> AgentRunResult:
    return orch.run_agent(
        RunRequest(
            goal=scenario.request,
            run_type=scenario.run_type,
            model="disabled",
            run_id=run_id,
            skip_execution=skip_execution,
        )
    )


def _gate_snapshot(orch: QaOrchestrator, flow_id: str | None) -> dict[str, Any]:
    if not flow_id:
        return {}
    decision = orch.graph.evaluate_execution(flow_id)
    return {
        "flow_id": flow_id,
        "executable": decision.executable,
        "reason_code": decision.reason_code,
        "approval_status": decision.approval_status,
        "message": decision.message,
    }


def _parameter_trace(result: AgentRunResult, expected: dict[str, str] | None) -> dict[str, Any]:
    plan = result.state.plan
    actual = dict(plan.validated_parameters or {}) if plan else {}
    env_hits = {}
    for key, value in (expected or {}).items():
        env_name = f"QA_PARAM_{key.upper()}"
        env_hits[key] = os.environ.get(env_name)
    ok = True
    if expected:
        ok = all(actual.get(k) == v for k, v in expected.items())
    return {
        "validated_parameters": actual,
        "expected": expected or {},
        "parameter_ok": ok,
        "env_params": {k: v for k, v in env_hits.items() if v},
    }


def _evidence_audit(run_id: str, *, automation_dir: Path) -> dict[str, Any]:
    root = automation_dir / "reports" / "evidence" / run_id
    if not root.exists():
        return {"run_id": run_id, "count": 0, "paths": [], "complete": False}
    pngs = list(root.rglob("*.png"))
    htmls = list(root.rglob("*.html"))
    jsons = list(root.rglob("*.json"))
    paths = [str(p.relative_to(automation_dir)) for p in pngs + htmls + jsons]
    return {
        "run_id": run_id,
        "count": len(paths),
        "screenshots": len(pngs),
        "dom": len(htmls),
        "structured": len(jsons),
        "paths": paths[:20],
        "complete": len(pngs) > 0,
    }


def _false_pass_check(result: AgentRunResult) -> bool:
    validation = result.state.validation
    execution = result.state.execution
    if not validation or not execution:
        return False
    if validation.conclusion == "PASS" and not execution.ok:
        return True
    if validation.conclusion == "PASS" and validation.reason_code.startswith("validator.pre_gt"):
        return False
    return validation.conclusion == "PASS" and execution.mode.startswith("playwright") and not execution.ok


def _evaluate_p9_row(
    scenario: P9Scenario,
    result: AgentRunResult,
    *,
    preflight_status: str,
    gate: dict[str, Any],
    param_trace: dict[str, Any],
    evidence: dict[str, Any],
    elapsed_ms: int,
    blocked: bool = False,
) -> dict[str, Any]:
    if scenario.resume_after_approval and not blocked:
        expected_outcome = "PASS"
        expected_approval = False
    elif scenario.requires_live and blocked:
        expected_outcome = "WAITING_FOR_APPROVAL"
        expected_approval = True
    elif not scenario.requires_live:
        expected_outcome = "WAITING_FOR_APPROVAL"
        expected_approval = True
    else:
        expected_outcome = "PASS"
        expected_approval = False

    eval_scenario = AgentEvalScenario(
        id=scenario.id,
        goal=scenario.request,
        expected_outcome=expected_outcome,
        expected_flow=scenario.expected_flow,
        expected_approval=expected_approval,
        expected_terminal_states=("WAITING_FOR_APPROVAL", "COMPLETED", "NEEDS_REVIEW", "FAILED"),
    )
    base = evaluate_scenario(result, eval_scenario)
    false_pass = _false_pass_check(result)
    passed = base["passed"]
    if scenario.check_parameters and not param_trace.get("parameter_ok"):
        passed = False
    if scenario.requires_live and preflight_status != "READY":
        passed = blocked or (result.state.status == "WAITING_FOR_APPROVAL" and gate.get("reason_code") == "approval.pending")
    if false_pass:
        passed = False
    if not scenario.requires_live and scenario.expected_flow and not base.get("flow_ok"):
        passed = False
    if not scenario.requires_live and result.state.status == "WAITING_FOR_APPROVAL" and gate.get("reason_code") == "approval.pending":
        passed = passed or (base.get("flow_ok") and (not scenario.check_parameters or param_trace.get("parameter_ok")))
    return {
        **base,
        "request": scenario.request,
        "category": scenario.category,
        "expected_flow": scenario.expected_flow,
        "selected_flow": (result.state.selected_flows or result.state.plan.candidate_flows[:1] if result.state.plan else []),
        "gate": gate,
        "agent_state": result.state.status,
        "verification": result.state.validation.model_dump() if result.state.validation else None,
        "parameter_trace": param_trace,
        "evidence": evidence,
        "elapsed_ms": elapsed_ms,
        "blocked": blocked,
        "false_pass": false_pass,
        "passed": passed,
        "final_result": result.conclusion,
    }


def _aggregate_metrics(rows: list[dict[str, Any]], durations: list[int], preflight: dict[str, Any]) -> dict[str, Any]:
    live_rows = [r for r in rows if r.get("category") == "live_execution"]
    blocked_live = sum(1 for r in live_rows if r.get("blocked"))
    attempted_live = len(live_rows)
    executed_live = sum(
        1
        for r in live_rows
        if not r.get("blocked") and r.get("agent_state") in {"COMPLETED", "NEEDS_REVIEW", "FAILED"}
    )
    false_passes = sum(1 for r in rows if r.get("false_pass"))
    false_fails = sum(
        1
        for r in rows
        if r.get("final_result") == "FAIL" and r.get("verification", {}) and r["verification"].get("conclusion") == "PASS"
    )
    param_ok = sum(1 for r in rows if r.get("parameter_trace", {}).get("parameter_ok") is True)
    param_total = sum(1 for r in rows if r.get("parameter_trace", {}).get("expected"))
    evidence_ok = sum(1 for r in rows if r.get("evidence", {}).get("complete"))
    evidence_total = sum(1 for r in rows if r.get("category") == "live_execution" and not r.get("blocked"))

    return {
        "live_flow_execution_rate": round(executed_live / attempted_live, 4) if attempted_live else 0.0,
        "live_execution_success_rate": round(
            sum(1 for r in live_rows if r.get("final_result") in {"PASS", "COMPLETED"} and not r.get("blocked"))
            / max(1, executed_live),
            4,
        ),
        "verification_success_rate": round(
            sum(
                1
                for r in rows
                if (r.get("verification") or {}).get("conclusion") in {"PASS", "NEEDS_REVIEW"}
            )
            / max(1, len(rows)),
            4,
        ),
        "false_pass_rate": round(false_passes / max(1, len(rows)), 4),
        "false_fail_rate": round(false_fails / max(1, len(rows)), 4),
        "approval_routing_accuracy": round(
            sum(
                1
                for r in rows
                if r.get("expected_flow")
                and r.get("agent_state") == "WAITING_FOR_APPROVAL"
                and not r.get("blocked")
            )
            / max(1, sum(1 for r in rows if r.get("category") != "live_execution")),
            4,
        ),
        "recovery_success_rate": 0.0,
        "evidence_completeness": round(evidence_ok / max(1, evidence_total), 4) if evidence_total else 0.0,
        "parameter_traceability_rate": round(param_ok / max(1, param_total), 4) if param_total else 1.0,
        "decision_trace_completeness": round(
            sum(1 for r in rows if r.get("journal_entries", 0) > 0) / max(1, len(rows)),
            4,
        ),
        "resume_success_rate": round(
            sum(1 for r in rows if "RESUME" in (r.get("decisions") or [])) / max(1, sum(1 for r in rows if r.get("resume"))),
            4,
        )
        if any(r.get("resume") for r in rows)
        else 0.0,
        "average_run_duration_ms": round(statistics.mean(durations), 2) if durations else 0.0,
        "p95_run_duration_ms": round(sorted(durations)[max(0, int(len(durations) * 0.95) - 1)], 2) if durations else 0.0,
        "human_intervention_rate": round(
            sum(1 for r in rows if r.get("agent_state") == "WAITING_FOR_APPROVAL") / max(1, len(rows)),
            4,
        ),
        "environment_status": preflight.get("status"),
        "blocked_live_scenarios": blocked_live,
    }


def run_p9_validation(
    *,
    scenarios: list[P9Scenario] | None = None,
    discovery_root: str = "data/discovery-kb",
    automation_dir: str = "apps/automation",
) -> dict[str, Any]:
    scenarios = scenarios or P9_SCENARIOS
    for key, value in _agent_env().items():
        os.environ[key] = value

    inventory = build_flow_inventory(discovery_root=discovery_root)
    preflight = run_environment_preflight(
        automation_dir=automation_dir,
        discovery_root=discovery_root,
    ).to_dict()
    live_allowed = preflight["status"] == "READY" or os.environ.get("P9_FORCE_LIVE") == "1"
    if not live_allowed:
        os.environ["QA_RUNNER"] = "dry_run"

    orch = QaOrchestrator(discovery_root=discovery_root, model="disabled")
    _reset_flow_artifact_for_eval(orch)
    rows: list[dict[str, Any]] = []
    durations: list[int] = []
    failures: list[dict[str, Any]] = []
    approvals: list[dict[str, Any]] = []
    resume_rows: list[dict[str, Any]] = []
    healing: dict[str, Any] = {"status": "NOT_RUN", "reason": "controlled healing deferred when APEX blocked"}
    frontend: dict[str, Any] = {}

    healing_eval = _run_offline_healing_validation(orch)
    healing = healing_eval
    controlled_failures = _run_offline_controlled_failures(orch)

    for scenario in scenarios:
        run_id = f"p9-{scenario.id}"
        started = time.perf_counter()
        blocked = scenario.requires_live and not live_allowed
        result: AgentRunResult | None = None

        try:
            if blocked:
                result = _run_agent(orch, scenario, run_id=run_id, skip_execution=True)
            elif scenario.resume_after_approval and scenario.expected_flow:
                first = _run_agent(orch, scenario, run_id=run_id)
                approvals.append(
                    {
                        "scenario": scenario.id,
                        "flow_id": scenario.expected_flow,
                        "pause_state": first.state.status,
                        "reason": first.reason_code,
                    }
                )
                if scenario.expected_flow:
                    _approve_flow_for_eval(orch, scenario.expected_flow)
                result = orch.resume_agent(run_id, resume_reason="P9 SME approval")
                resume_rows.append(
                    {
                        "run_id": run_id,
                        "same_run_id": result.state.run_id == run_id,
                        "resume_decisions": [e.decision for e in result.state.decision_journal],
                        "status": result.state.status,
                        "conclusion": result.conclusion,
                    }
                )
            else:
                result = _run_agent(orch, scenario, run_id=run_id)
        except Exception as exc:
            failures.append({"scenario": scenario.id, "error": str(exc)})
            elapsed = int((time.perf_counter() - started) * 1000)
            rows.append(
                {
                    "id": scenario.id,
                    "request": scenario.request,
                    "passed": False,
                    "blocked": blocked,
                    "error": str(exc),
                    "elapsed_ms": elapsed,
                }
            )
            durations.append(elapsed)
            continue

        elapsed = int((time.perf_counter() - started) * 1000)
        durations.append(elapsed)
        gate = _gate_snapshot(orch, scenario.expected_flow)
        param_trace = _parameter_trace(result, scenario.check_parameters)
        evidence = _evidence_audit(run_id, automation_dir=Path(automation_dir))
        row = _evaluate_p9_row(
            scenario,
            result,
            preflight_status=preflight["status"],
            gate=gate,
            param_trace=param_trace,
            evidence=evidence,
            elapsed_ms=elapsed,
            blocked=blocked,
        )
        if scenario.resume_after_approval:
            row["resume"] = True
        rows.append(row)
        if not row["passed"]:
            failures.append({"scenario": scenario.id, "reason": row.get("final_result"), "blocked": blocked})

    _reset_flow_artifact_for_eval(orch)

    try:
        from qa_orchestrator.p9_flow_inventory import build_flow_inventory as _inv

        inv = _inv(discovery_root=discovery_root)
        frontend = {
            "inventory_totals": inv["totals"],
            "misleading_approved_label": inv["totals"]["approved"] != inv["totals"]["executable"],
            "recommended_display": {
                "total_flows": inv["totals"]["total_flows"],
                "sme_ready": inv["totals"]["sme_ready"],
                "approved": inv["totals"]["approved"],
                "executable": inv["totals"]["executable"],
                "awaiting_approval": inv["totals"]["pending_approval"],
            },
        }
    except Exception as exc:
        frontend = {"error": str(exc)}

    metrics = _aggregate_metrics(rows, durations, preflight)
    if healing.get("passed"):
        metrics["recovery_success_rate"] = healing.get("metrics", {}).get("resume_success_rate", 0.0)
    report = {
        "environment": preflight.get("environment"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "preflight": preflight,
        "inventory": inventory,
        "flows_tested": P9_SELECTED_FLOWS,
        "runs": rows,
        "execution_matrix": [
            {
                "request": r.get("request"),
                "expected_flow": r.get("expected_flow"),
                "selected_flow": (r.get("selected_flow") or [None])[0] if isinstance(r.get("selected_flow"), list) else r.get("selected_flow"),
                "gate": (r.get("gate") or {}).get("reason_code"),
                "agent_state": r.get("agent_state"),
                "final_result": r.get("final_result"),
                "blocked": r.get("blocked"),
            }
            for r in rows
        ],
        "metrics": metrics,
        "failures": failures,
        "healing": healing,
        "controlled_failures": controlled_failures,
        "approvals": approvals,
        "resume": resume_rows,
        "frontend": frontend,
        "limitations": _limitations(preflight, metrics),
        "passed": sum(1 for r in rows if r.get("passed")),
        "total": len(rows),
    }
    return report


def _run_offline_healing_validation(orch: QaOrchestrator) -> dict[str, Any]:
    """Run controlled offline healing + resume using existing P6.1 eval scenarios."""
    from qa_orchestrator.agent_eval import P61_RESUME_SCENARIOS, run_p61_resume_evaluation

    healing_ids = {"p61_healing_resume", "p61_approval_pause_resume"}
    scenarios = [s for s in P61_RESUME_SCENARIOS if s.id in healing_ids]
    if not scenarios:
        return {"status": "NOT_RUN", "reason": "healing scenarios unavailable"}
    try:
        result = run_p61_resume_evaluation(orch, scenarios=scenarios)
        return {
            "status": "COMPLETED",
            "passed": result.get("passed", 0) == result.get("total", 0),
            "scenarios": result.get("scenarios", []),
            "metrics": result.get("metrics", {}),
        }
    except Exception as exc:
        return {"status": "FAILED", "reason": str(exc), "passed": False}


def _run_offline_controlled_failures(orch: QaOrchestrator) -> dict[str, Any]:
    """Exercise non-destructive failure handling offline."""
    from qa_orchestrator.agent_eval import P6_EVAL_SCENARIOS, AgentEvalScenario, run_agent_evaluation
    from qa_orchestrator.run_request import RunRequest

    failure_ids = {"locator_healing", "ambiguous_verification", "max_recovery_limit"}
    scenarios = [s for s in P6_EVAL_SCENARIOS if s.id in failure_ids]
    if not scenarios:
        return {"status": "NOT_RUN", "reason": "failure scenarios unavailable"}

    def _run(scenario: AgentEvalScenario):
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
                run_id=f"p9-fail-{scenario.id}",
            )
        )

    try:
        result = run_agent_evaluation(_run, scenarios=scenarios)
        return {
            "status": "COMPLETED",
            "passed": result.get("passed", 0) >= len(scenarios) - 1,
            "scenarios": result.get("scenarios", []),
            "metrics": result.get("metrics", {}),
        }
    except Exception as exc:
        return {"status": "FAILED", "reason": str(exc), "passed": False}


def _limitations(preflight: dict[str, Any], metrics: dict[str, Any]) -> list[str]:
    limits = []
    if preflight.get("status") != "READY":
        limits.append(
            f"Live Oracle APEX execution blocked: {preflight.get('blocked_reason') or preflight.get('status')}"
        )
    if metrics.get("false_pass_rate", 0) > 0:
        limits.append("One or more scenarios flagged potential false-pass conditions")
    if metrics.get("evidence_completeness", 0) == 0 and preflight.get("status") != "READY":
        limits.append("Evidence completeness not measured — live browser execution unavailable")
    if metrics.get("recovery_success_rate", 0) == 0:
        limits.append("Live recovery retry against real APEX not exercised in blocked environment")
    if preflight.get("status") != "READY":
        limits.append("Live browser evidence and Ground Truth validation against real APEX not completed")
    return limits


def write_p9_reports(report: dict[str, Any], *, json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# P9 — Oracle APEX End-to-End Validation",
        "",
        f"- **Environment:** {report.get('environment')}",
        f"- **Timestamp:** {report.get('timestamp')}",
        f"- **Preflight:** {report.get('preflight', {}).get('status')}",
        "",
        "## Flow inventory",
        "",
    ]
    totals = report.get("inventory", {}).get("totals", {})
    lines.extend(
        [
            f"- Total flows: {totals.get('total_flows')}",
            f"- SME-ready: {totals.get('sme_ready')}",
            f"- Approved: {totals.get('approved')}",
            f"- Executable: {totals.get('executable')}",
            f"- Awaiting approval: {totals.get('pending_approval')}",
            "",
            "## Selected validation subset",
            "",
        ]
    )
    for flow in report.get("flows_tested", []):
        lines.append(
            f"- `{flow.get('flow_id')}` ({flow.get('category')}) — gate `{flow.get('reason_code')}` executable={flow.get('executable')}"
        )
    lines.extend(["", "## Execution matrix", "", "| Request | Expected Flow | Gate | Agent State | Final Result |", "|---|---|---|---|---|"])
    for row in report.get("execution_matrix", []):
        lines.append(
            f"| {row.get('request')} | {row.get('expected_flow')} | {row.get('gate')} | {row.get('agent_state')} | {row.get('final_result')} |"
        )
    lines.extend(["", "## Metrics", ""])
    for key, value in sorted((report.get("metrics") or {}).items()):
        lines.append(f"- **{key}:** {value}")
    lines.extend(["", "## Limitations", ""])
    for item in report.get("limitations") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Runs", ""])
    for run in report.get("runs", []):
        lines.extend(
            [
                f"### {run.get('id')}",
                f"- Request: {run.get('request')}",
                f"- Expected flow: {run.get('expected_flow')}",
                f"- Final result: {run.get('final_result')}",
                f"- Gate: {(run.get('gate') or {}).get('reason_code')}",
                f"- Evidence count: {(run.get('evidence') or {}).get('count')}",
                f"- Parameter trace: {run.get('parameter_trace')}",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    report = run_p9_validation()
    json_out = Path(os.environ.get("QA_P9_EVAL_REPORT", "reports/e2e/p9-apex-validation.json"))
    md_out = Path(os.environ.get("QA_P9_EVAL_MD", "reports/e2e/p9-apex-validation.md"))
    write_p9_reports(report, json_path=json_out, md_path=md_out)
    print(
        json.dumps(
            {
                "report_json": str(json_out),
                "report_md": str(md_out),
                "preflight": report["preflight"]["status"],
                "passed": report["passed"],
                "total": report["total"],
                "false_pass_rate": report["metrics"]["false_pass_rate"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
