"""P6 — canonical agent CLI entry point."""

from __future__ import annotations

import argparse
import json
import sys

from qa_orchestrator.agent_journal import journal_path
from qa_orchestrator.orchestrator import QaOrchestrator
from qa_orchestrator.run_request import RunRequest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Controlled QA agent run")
    parser.add_argument("goal", help="Natural language goal")
    parser.add_argument("--discovery-root", default="data/discovery-kb")
    parser.add_argument("--type", default="adhoc", choices=["adhoc", "sanity", "scheduled", "flow"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--skip-discovery", action="store_true")
    parser.add_argument("--skip-execution", action="store_true")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable payload")
    args = parser.parse_args(argv)

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
        if not planning.execution_allowed and not (state.suite_plan and state.suite_plan.commands):
            print(f"Reason: {state.reason_code or planning.reasoning_summary}", file=sys.stderr)

    if state.execution and state.execution.mode != "skipped":
        print("Running existing approved test...", file=sys.stderr)
    if state.validation:
        print(f"Verification: {state.validation.conclusion}", file=sys.stderr)

    print(f"Result: {agent_result.conclusion}", file=sys.stderr)
    print(f"Run ID: {state.run_id}", file=sys.stderr)

    orchestrator_result = orch.agent_loop.to_orchestrator_result(agent_result)
    orchestrator_result.metadata.update(agent_result.orchestrator_metadata)
    payload = orch.to_agent_payload(orchestrator_result)
    payload["agent"]["decision_journal"] = [entry.model_dump() for entry in state.decision_journal]
    payload["agent"]["metrics"] = agent_result.metrics.model_dump()
    payload["agent"]["journal_path"] = str(
        journal_path(orch.agent_loop.config.journal_dir, state.run_id)
    )
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(json.dumps({"run_id": state.run_id, "result": agent_result.conclusion, "summary": agent_result.summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
