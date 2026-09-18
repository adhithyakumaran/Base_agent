"""Revalidate a completed run against newly approved Ground Truth (no Playwright)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from qa_orchestrator.agent_models import AgentRunState
from qa_orchestrator.kb_rag import KbRag
from qa_orchestrator.models import (
    DiscoveryResult,
    ExecutionPlan,
    ExecutionResult,
    IntentClassification,
    PlanningResult,
    SuiteSelectionPlan,
)
from qa_orchestrator.planner import intent_to_execution_plan
from qa_orchestrator.validator import Validator


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "data" / "discovery-kb").exists():
            return parent
    return here.parents[2]


def revalidate_local_snapshot(
    *,
    goal: str,
    run_type: str,
    run_id: str | None,
    local: dict[str, Any],
) -> dict[str, Any]:
    root = _repo_root()
    discovery_root = Path(local.get("discovery_root") or root / "data" / "discovery-kb")
    kb = KbRag(str(discovery_root))
    validator = Validator(kb, gt_dir=discovery_root / "gt")

    execution_raw = local.get("execution") or {"ok": False, "mode": "skipped", "observations": []}
    execution = ExecutionResult.model_validate(execution_raw)

    intent_raw = local.get("intent")
    intent = IntentClassification.model_validate(intent_raw) if intent_raw else None
    suite_raw = local.get("suite_plan")
    suite_plan = SuiteSelectionPlan.model_validate(suite_raw) if suite_raw else None
    discovery_raw = local.get("discovery")
    discovery = DiscoveryResult.model_validate(discovery_raw) if discovery_raw else None
    plan_raw = local.get("plan") or local.get("execution_plan")
    if plan_raw:
        plan = ExecutionPlan.model_validate(plan_raw)
    elif intent:
        plan = intent_to_execution_plan(intent)
    else:
        plan = ExecutionPlan(goal=goal, summary="revalidation", steps=[])

    planning_raw = local.get("planning")
    planning = PlanningResult.model_validate(planning_raw) if planning_raw else None

    diagnostic_context: dict[str, Any] = {"run_id": run_id}
    state_raw = local.get("state")
    if isinstance(state_raw, dict):
        try:
            diagnostic_context["state"] = AgentRunState.model_validate(state_raw)
        except Exception:
            diagnostic_context["state"] = None

    validation = validator.validate(
        goal=goal,
        run_type=run_type,
        plan=plan,
        execution=execution,
        llm_summary=str(local.get("llm_summary") or ""),
        intent=intent,
        suite_plan=suite_plan,
        discovery=discovery,
        diagnostic_context=diagnostic_context,
    )

    if planning:
        _ = planning

    payload = validation.model_dump()
    return {
        "ok": True,
        "conclusion": validation.conclusion,
        "reason_code": validation.reason_code,
        "decision_diagnostics": validation.decision_diagnostics,
        "validation": payload,
    }


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        print(json.dumps({"ok": False, "error": "empty_input"}))
        return 1
    body = json.loads(raw)
    goal = str(body.get("goal") or "")
    run_type = str(body.get("run_type") or "adhoc")
    run_id = body.get("run_id")
    local = body.get("local")
    if not goal or not isinstance(local, dict):
        print(json.dumps({"ok": False, "error": "invalid_payload"}))
        return 1
    result = revalidate_local_snapshot(
        goal=goal, run_type=run_type, run_id=str(run_id) if run_id else None, local=local
    )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
