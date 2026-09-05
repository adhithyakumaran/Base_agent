from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qa_orchestrator.kb_rag import KbRag
from qa_orchestrator.llm_client import PlannerLlmClient
from qa_orchestrator.models import OrchestratorResult
from qa_orchestrator.openclaw_adapter import OpenClawAdapter
from qa_orchestrator.playwright_runner import PlaywrightRunner
from qa_orchestrator.planner import Planner
from qa_orchestrator.reporter import build_markdown_report
from qa_orchestrator.validator import Validator


@dataclass
class RunRequest:
    goal: str
    run_type: str = "adhoc"
    model: str | None = None
    context_packets: list[dict[str, Any]] = field(default_factory=list)


class QaOrchestrator:
    """Thin product orchestrator: plan → execute → validate → report."""

    def __init__(
        self,
        *,
        kb_dir: str | Path,
        gt_dir: str | Path | None = None,
        model: str | None = None,
    ) -> None:
        self.kb_dir = Path(kb_dir)
        self.kb = KbRag(self.kb_dir)
        self.llm = PlannerLlmClient.from_env(model_id=model)
        self.planner = Planner(self.kb, self.llm)
        runner_mode = os.environ.get("QA_RUNNER", "mock").lower()
        if runner_mode == "playwright":
            self.executor = PlaywrightRunner()
        else:
            self.executor = OpenClawAdapter()
        gt_path = Path(gt_dir) if gt_dir else self.kb_dir.parent / "gt"
        self.validator = Validator(self.kb, gt_dir=gt_path if gt_path.exists() else None)

    def run(self, request: RunRequest | str) -> OrchestratorResult:
        req = request if isinstance(request, RunRequest) else RunRequest(goal=request)
        if req.model:
            self.llm = PlannerLlmClient.from_env(model_id=req.model)

        plan = self.planner.plan(
            req.goal,
            run_type=req.run_type,
            context_packets=req.context_packets,
        )
        execution = self.executor.run_plan(plan)

        llm_summary = ""
        if self.llm.enabled and execution.ok:
            llm_summary, _ = self.llm.summarize(
                prompt=(
                    f"Summarize QA run for report (2 sentences, honest, no fake PASS).\n"
                    f"Goal: {req.goal}\nPlan: {plan.summary}\n"
                    f"Steps ok: {sum(1 for o in execution.observations if o.ok)}/{len(execution.observations)}"
                )
            )

        validation = self.validator.validate(
            goal=req.goal,
            run_type=req.run_type,
            plan=plan,
            execution=execution,
            llm_summary=llm_summary,
        )

        result = OrchestratorResult(
            conclusion=validation.conclusion,
            reason_code=validation.reason_code,
            summary=validation.summary,
            goal=req.goal,
            run_type=req.run_type,
            plan=plan,
            execution=execution,
            validation=validation,
            tool_calls=len(execution.observations),
            llm_calls=self.llm.llm_calls,
            steps=len(plan.steps),
            tokens_in=self.llm.tokens_in,
            tokens_out=self.llm.tokens_out,
            kb_refs=plan.kb_refs,
            metadata={
                "planner": plan.planner,
                "openclaw_mode": execution.mode,
                "validation_phase": validation.phase,
                "llm_enabled": self.llm.enabled,
                "llm_provider": self.llm.provider,
            },
        )
        result.report_markdown = build_markdown_report(result=result)
        return result

    def to_agent_payload(self, result: OrchestratorResult) -> dict[str, Any]:
        """Console-compatible payload (mirrors legacy AgentResult fields)."""
        return {
            "conclusion": result.conclusion,
            "reason_code": result.reason_code,
            "summary": result.summary,
            "goal": result.goal,
            "tool_calls": result.tool_calls,
            "llm_calls": result.llm_calls,
            "steps": result.steps,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "kb_refs": result.kb_refs,
            "metadata": result.metadata,
            "local": {
                "orchestrator": "qa_orchestrator",
                "run_type": result.run_type,
                "planner": result.plan.planner,
                "openclaw_mode": result.execution.mode,
                "validation_phase": result.validation.phase,
                "report_markdown": result.report_markdown,
                "plan": result.plan.model_dump(),
                "execution": result.execution.model_dump(),
                "validation": result.validation.model_dump(),
            },
        }
