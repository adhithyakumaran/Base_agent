"""P6 — canonical agent CLI entry point."""

from __future__ import annotations

import argparse
import json
import sys

from qa_orchestrator.agent_journal import journal_path
from qa_orchestrator.agent_state_store import state_path
from qa_orchestrator.legacy_guard import assert_canonical_agent_path, canonical_path_metadata
from qa_orchestrator.orchestrator import QaOrchestrator
from qa_orchestrator.run_request import RunRequest


def _emit_payload(orch: QaOrchestrator, agent_result, *, as_json: bool) -> None:
    state = agent_result.state
    orchestrator_result = orch.agent_loop.to_orchestrator_result(agent_result)
    orchestrator_result.metadata.update(agent_result.orchestrator_metadata)
    payload = orch.to_agent_payload(orchestrator_result)
    payload["agent"]["decision_journal"] = [entry.model_dump() for entry in state.decision_journal]
    payload["agent"]["metrics"] = agent_result.metrics.model_dump()
    payload["agent"]["journal_path"] = str(journal_path(orch.agent_loop.config.journal_dir, state.run_id))
    payload["agent"]["state_path"] = str(state_path(orch.agent_loop.config.journal_dir, state.run_id))
    payload["agent"]["canonical"] = canonical_path_metadata()
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(json.dumps({"run_id": state.run_id, "result": agent_result.conclusion, "summary": agent_result.summary}, indent=2))


def cmd_run(args: argparse.Namespace) -> int:
    assert_canonical_agent_path("agent_cli")
    orch = QaOrchestrator(discovery_root=args.discovery_root, model=args.model)
    request = RunRequest(
        goal=args.goal,
        run_type=args.type,
        model=args.model,
        run_id=args.run_id,
        skip_discovery=args.skip_discovery,
        skip_execution=args.skip_execution,
    )
    print("Planning...", file=sys.stderr)
    agent_result = orch.run_agent(request)
    state = agent_result.state
    planning = state.plan
    if planning:
        flows = ", ".join(planning.selected_flows or planning.candidate_flows[:3]) or "n/a"
        print(f"Selected flow: {flows}", file=sys.stderr)
        gate = "PASS" if planning.execution_allowed or (state.suite_plan and state.suite_plan.commands) else "BLOCKED"
        print(f"Execution gate: {gate}", file=sys.stderr)
    if state.execution and state.execution.mode != "skipped":
        print("Running existing approved test...", file=sys.stderr)
    if state.validation:
        print(f"Verification: {state.validation.conclusion}", file=sys.stderr)
    print(f"Result: {agent_result.conclusion}", file=sys.stderr)
    print(f"Run ID: {state.run_id}", file=sys.stderr)
    _emit_payload(orch, agent_result, as_json=args.json)
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    assert_canonical_agent_path("agent_cli")
    orch = QaOrchestrator(discovery_root=args.discovery_root, model=args.model)
    print(f"Resuming run {args.run_id}...", file=sys.stderr)
    agent_result = orch.resume_agent(args.run_id, resume_token=args.resume_token, resume_reason=args.reason)
    print(f"Result: {agent_result.conclusion}", file=sys.stderr)
    _emit_payload(orch, agent_result, as_json=args.json)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Controlled QA agent run")
    parser.add_argument("--discovery-root", default="data/discovery-kb")
    parser.add_argument("--model", default=None)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable payload")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Start a new bounded agent run")
    run_p.add_argument("goal", help="Natural language goal")
    run_p.add_argument("--type", default="adhoc", choices=["adhoc", "sanity", "scheduled", "flow"])
    run_p.add_argument("--run-id", default=None)
    run_p.add_argument("--skip-discovery", action="store_true")
    run_p.add_argument("--skip-execution", action="store_true")
    run_p.set_defaults(func=cmd_run)

    resume_p = sub.add_parser("resume", help="Resume a WAITING_FOR_APPROVAL run")
    resume_p.add_argument("run_id", help="Existing agent run id")
    resume_p.add_argument("--resume-token", default=None, help="Idempotency token")
    resume_p.add_argument("--reason", default="approval granted")
    resume_p.set_defaults(func=cmd_resume)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
