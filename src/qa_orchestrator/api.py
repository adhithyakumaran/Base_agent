from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_orchestrator.orchestrator import QaOrchestrator, RunRequest


def main() -> None:
    parser = argparse.ArgumentParser(description="QA Orchestrator CLI (LLM + OpenClaw)")
    parser.add_argument("goal", help="Natural language goal")
    parser.add_argument("--kb-dir", default="discovery/uat_ea/kb")
    parser.add_argument("--type", default="adhoc", choices=["adhoc", "sanity", "scheduled", "flow"])
    parser.add_argument("--model", default=None, help="Model id (groq/*, claude-*, or disabled)")
    args = parser.parse_args()

    orch = QaOrchestrator(kb_dir=args.kb_dir, model=args.model)
    result = orch.run(RunRequest(goal=args.goal, run_type=args.type, model=args.model))
    print(json.dumps(orch.to_agent_payload(result), indent=2))


if __name__ == "__main__":
    main()
