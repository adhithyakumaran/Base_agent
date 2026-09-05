from __future__ import annotations

import argparse
import json

from qa_orchestrator.orchestrator import QaOrchestrator, RunRequest


def main() -> None:
    parser = argparse.ArgumentParser(description="Enterprise QA Orchestrator CLI")
    parser.add_argument("goal", help="Natural language goal")
    parser.add_argument("--discovery-root", default="discovery/uat_ea")
    parser.add_argument("--type", default="adhoc", choices=["adhoc", "sanity", "scheduled", "flow"])
    parser.add_argument("--model", default=None, help="Model id (groq/*, claude-*, or disabled)")
    parser.add_argument("--skip-discovery", action="store_true")
    parser.add_argument("--skip-execution", action="store_true")
    args = parser.parse_args()

    orch = QaOrchestrator(discovery_root=args.discovery_root, model=args.model)
    result = orch.run(
        RunRequest(
            goal=args.goal,
            run_type=args.type,
            model=args.model,
            skip_discovery=args.skip_discovery,
            skip_execution=args.skip_execution,
        )
    )
    print(json.dumps(orch.to_agent_payload(result), indent=2))


if __name__ == "__main__":
    main()
