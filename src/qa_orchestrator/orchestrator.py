from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qa_orchestrator.discovery_service import DiscoveryService
from qa_orchestrator.flow_kb import YamlFlowKb
from qa_orchestrator.intent_classifier import IntentClassifier
from qa_orchestrator.kb_rag import KbRag
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.llm_client import PlannerLlmClient
from qa_orchestrator.models import DiscoveryResult, ExecutionPlan, OrchestratorResult
from qa_orchestrator.openclaw_adapter import OpenClawAdapter
from qa_orchestrator.planner import intent_to_execution_plan
from qa_orchestrator.playwright_runner import PlaywrightRunner
from qa_orchestrator.reporter import build_markdown_report
from qa_orchestrator.suite_selector import SuiteSelector
from qa_orchestrator.validator import Validator


@dataclass
class RunRequest:
    goal: str
    run_type: str = "adhoc"
    model: str | None = None
    context_packets: list[dict[str, Any]] = field(default_factory=list)
    skip_discovery: bool = False
    skip_execution: bool = False


class QaOrchestrator:
    """Enterprise orchestrator: classify → select suites → execute → analyze → report."""

    def __init__(
        self,
        *,
        discovery_root: str | Path | None = None,
        kb_dir: str | Path | None = None,
        gt_dir: str | Path | None = None,
        model: str | None = None,
    ) -> None:
        root = Path(discovery_root or os.environ.get("QA_DISCOVERY_ROOT", "discovery/uat_ea"))
        self.discovery_root = root
        self.kb_dir = Path(kb_dir or root / "kb")
        self.graph = FlowKnowledgeGraph(discovery_root=root)
        self.flow_kb: YamlFlowKb = self.graph.flow_kb
        self.legacy_kb = KbRag(self.kb_dir) if self.kb_dir.exists() else None
        self.llm = PlannerLlmClient.from_env(model_id=model)
        self.classifier = IntentClassifier(self.graph, self.llm)
        self.selector = SuiteSelector(self.graph)
        self.discovery = DiscoveryService(self.graph, dry_run=_default_crawl_dry_run())
        self.executor = _build_executor()
        gt_path = Path(gt_dir) if gt_dir else root / "gt"
        validator_kb = self.legacy_kb or _KbShim(self.flow_kb)
        self.validator = Validator(validator_kb, gt_dir=gt_path if gt_path.exists() else None)

    def run(self, request: RunRequest | str) -> OrchestratorResult:
        req = request if isinstance(request, RunRequest) else RunRequest(goal=request)
        if req.model:
            self.llm = PlannerLlmClient.from_env(model_id=req.model)
            self.classifier = IntentClassifier(self.graph, self.llm)

        intent = self.classifier.classify(
            req.goal,
            run_type=req.run_type,
            context_packets=req.context_packets,
        )
        suite_plan = self.selector.select(intent)
        plan = intent_to_execution_plan(intent)

        discovery: DiscoveryResult | None = None
        if not req.skip_discovery and intent.execution_mode in {"new_feature", "discover"}:
            discovery = self.discovery.discover(intent, suite_plan)

        if req.skip_execution:
            from qa_orchestrator.models import ExecutionResult

            execution = ExecutionResult(ok=True, mode="skipped", observations=[])
        elif hasattr(self.executor, "run_selection"):
            execution = self.executor.run_selection(suite_plan)  # type: ignore[attr-defined]
        else:
            execution = self.executor.run_plan(plan)

        llm_summary = ""
        if self.llm.enabled:
            llm_summary, _ = self.llm.summarize(
                prompt=(
                    "Write a concise enterprise QA analysis (3-4 sentences). "
                    "State intent, suites run, pass/fail honestly, and any SME follow-ups. "
                    "Do not declare PASS without evidence.\n"
                    f"Goal: {req.goal}\n"
                    f"Mode: {intent.execution_mode}\n"
                    f"Flows: {', '.join(suite_plan.flow_ids) or 'n/a'}\n"
                    f"Commands: {', '.join(suite_plan.commands)}\n"
                    f"Execution ok: {execution.ok}\n"
                    f"Observations: {len(execution.observations)}\n"
                    f"Discovery: {discovery.pages_crawled if discovery else 0} pages"
                )
            )

        validation = self.validator.validate(
            goal=req.goal,
            run_type=req.run_type,
            plan=plan,
            execution=execution,
            llm_summary=llm_summary,
            intent=intent,
            suite_plan=suite_plan,
            discovery=discovery,
        )

        result = OrchestratorResult(
            conclusion=validation.conclusion,
            reason_code=validation.reason_code,
            summary=validation.summary,
            goal=req.goal,
            run_type=req.run_type,
            intent=intent,
            suite_plan=suite_plan,
            discovery=discovery,
            plan=plan,
            execution=execution,
            validation=validation,
            tool_calls=len(execution.observations),
            llm_calls=self.llm.llm_calls,
            steps=len(suite_plan.commands),
            tokens_in=self.llm.tokens_in,
            tokens_out=self.llm.tokens_out,
            kb_refs=plan.kb_refs,
            metadata={
                "classifier": intent.classifier,
                "execution_mode": intent.execution_mode,
                "executor": getattr(self.executor, "mode", type(self.executor).__name__),
                "validation_phase": validation.phase,
                "llm_enabled": self.llm.enabled,
                "llm_provider": self.llm.provider,
                "primary_flow_count": len(self.graph.ready_flow_ids()),
                "supporting_draft_count": len(self.graph.draft_flow_ids()),
            },
        )
        result.report_markdown = build_markdown_report(result=result)
        return result

    def to_agent_payload(self, result: OrchestratorResult) -> dict[str, Any]:
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
                "execution_mode": result.intent.execution_mode,
                "classifier": result.intent.classifier,
                "capability": result.intent.capability,
                "confidence": result.intent.confidence,
                "executor": result.metadata.get("executor"),
                "validation_phase": result.validation.phase,
                "report_markdown": result.report_markdown,
                "intent": result.intent.model_dump(),
                "suite_plan": result.suite_plan.model_dump(),
                "discovery": result.discovery.model_dump() if result.discovery else None,
                "plan": result.plan.model_dump(),
                "execution": result.execution.model_dump(),
                "validation": result.validation.model_dump(),
            },
        }


def _build_executor() -> PlaywrightRunner | OpenClawAdapter:
    runner_mode = os.environ.get("QA_RUNNER", "playwright").lower()
    if runner_mode in {"openclaw", "mock"}:
        return OpenClawAdapter(mode="mock" if runner_mode == "mock" else None)
    return PlaywrightRunner()


def _default_crawl_dry_run() -> bool:
    runner = os.environ.get("QA_RUNNER", "playwright").lower()
    return runner in {"dry_run", "dry-run", "mock", "playwright"} and os.environ.get(
        "QA_CRAWL_LIVE", ""
    ).lower() not in {"1", "true", "yes"}


class _KbShim:
    """Minimal KbRag interface over YamlFlowKb for Validator compatibility."""

    def __init__(self, flow_kb: YamlFlowKb) -> None:
        self.flow_kb = flow_kb

    def search(self, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
        return [{"id": h["id"], "title": h.get("name")} for h in self.flow_kb.search(query, limit=limit)]

    def app_overview(self) -> dict[str, Any]:
        return self.flow_kb.app_overview()
