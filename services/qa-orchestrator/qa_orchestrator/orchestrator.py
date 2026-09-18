from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from qa_orchestrator.controlled_agent_loop import ControlledAgentLoop
from qa_orchestrator.discovery_service import DiscoveryService
from qa_orchestrator.embedding_config import EmbeddingConfig
from qa_orchestrator.embedding_provider import create_embedding_provider
from qa_orchestrator.exploration_service import ExplorationService
from qa_orchestrator.flow_kb import YamlFlowKb
from qa_orchestrator.intent_classifier import IntentClassifier
from qa_orchestrator.kb_rag import KbRag
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.knowledge_indexer import KnowledgeIndexer
from qa_orchestrator.knowledge_retriever import KnowledgeRetriever
from qa_orchestrator.llm_client import PlannerLlmClient
from qa_orchestrator.generation_service import GenerationService
from qa_orchestrator.healing_service import HealingService
from qa_orchestrator.models import OrchestratorResult
from qa_orchestrator.openclaw_adapter import OpenClawAdapter
from qa_orchestrator.playwright_runner import PlaywrightRunner
from qa_orchestrator.qa_planner import QaPlanner
from qa_orchestrator.qdrant_config import QdrantConfig
from qa_orchestrator.suite_selector import SuiteSelector
from qa_orchestrator.validator import Validator
from qa_orchestrator.vector_store import create_vector_store


from qa_orchestrator.run_request import RunRequest


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
        root = Path(discovery_root or os.environ.get("QA_DISCOVERY_ROOT", "data/discovery-kb"))
        self.discovery_root = root
        self.kb_dir = Path(kb_dir or root / "kb")
        self.graph = FlowKnowledgeGraph(discovery_root=root)
        self.flow_kb: YamlFlowKb = self.graph.flow_kb
        self.legacy_kb = KbRag(self.kb_dir) if self.kb_dir.exists() else None
        self.llm = PlannerLlmClient.from_env(model_id=model)
        self.retriever = _build_retriever(self.graph)
        self.classifier = IntentClassifier(self.graph, self.llm)
        self.qa_planner = QaPlanner(self.graph, self.llm, retriever=self.retriever)
        self.selector = SuiteSelector(self.graph)
        self.discovery = DiscoveryService(self.graph, dry_run=_default_crawl_dry_run())
        self.exploration = ExplorationService(self.graph, dry_run=_default_explore_dry_run())
        self.generation = GenerationService(self.graph)
        self.healing = HealingService(self.graph)
        self.executor = _build_executor()
        self.agent_loop = ControlledAgentLoop(self)
        gt_path = Path(gt_dir) if gt_dir else root / "gt"
        gt_path.mkdir(parents=True, exist_ok=True)
        validator_kb = self.legacy_kb or _KbShim(self.flow_kb)
        self.validator = Validator(validator_kb, gt_dir=gt_path)

    def run(self, request: RunRequest | str) -> OrchestratorResult:
        req = request if isinstance(request, RunRequest) else RunRequest(goal=request)
        agent_result = self.agent_loop.run(req)
        result = self.agent_loop.to_orchestrator_result(agent_result)
        result.metadata.update(agent_result.orchestrator_metadata)
        result.conclusion = agent_result.conclusion
        result.reason_code = agent_result.reason_code
        result.summary = agent_result.summary
        result.report_markdown = agent_result.report_markdown or result.report_markdown
        result.tool_calls = len(result.execution.observations)
        result.llm_calls = self.llm.llm_calls
        result.steps = len(result.suite_plan.commands)
        result.tokens_in = self.llm.tokens_in
        result.tokens_out = self.llm.tokens_out
        result.kb_refs = result.plan.kb_refs
        result.metadata["agent_metrics"] = agent_result.metrics.model_dump()
        result.metadata["agent_journal_path"] = str(
            __import__("qa_orchestrator.agent_journal", fromlist=["journal_path"]).journal_path(
                self.agent_loop.config.journal_dir,
                agent_result.state.run_id,
            )
        )
        if agent_result.state.decision_diagnostics:
            result.metadata["decision_diagnostics"] = agent_result.state.decision_diagnostics
        return result

    def run_agent(self, request: RunRequest | str):
        """Return full bounded agent result including decision journal."""
        req = request if isinstance(request, RunRequest) else RunRequest(goal=request)
        return self.agent_loop.run(req)

    def get_agent_state(self, run_id: str):
        from qa_orchestrator.agent_resume import AgentResumeService

        return AgentResumeService(self).get_state(run_id)

    def resume_agent(self, run_id: str, *, resume_token: str | None = None, resume_reason: str = "approval granted"):
        from qa_orchestrator.agent_resume import AgentResumeService

        return AgentResumeService(self).resume(run_id, resume_token=resume_token, resume_reason=resume_reason)

    def to_agent_payload(self, result: OrchestratorResult) -> dict[str, Any]:
        agent_state = result.metadata.get("agent_status")
        return {
            "conclusion": result.conclusion,
            "reason_code": result.reason_code,
            "summary": result.summary,
            "decision_diagnostics": result.metadata.get("decision_diagnostics"),
            "goal": result.goal,
            "tool_calls": result.tool_calls,
            "llm_calls": result.llm_calls,
            "steps": result.steps,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "kb_refs": result.kb_refs,
            "metadata": result.metadata,
            "agent": {
                "run_id": result.metadata.get("run_id"),
                "status": agent_state,
                "reason_code": result.reason_code,
                "decision_diagnostics": result.metadata.get("decision_diagnostics"),
                "iteration": result.metadata.get("agent_iterations"),
                "recovery_count": result.metadata.get("agent_recoveries"),
                "retrieval_used": result.metadata.get("retrieval_used"),
                "journal_path": result.metadata.get("agent_journal_path"),
                "metrics": result.metadata.get("agent_metrics"),
            },
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
                "planning": result.planning.model_dump() if result.planning else None,
                "exploration": result.exploration.model_dump() if result.exploration else None,
                "generation_result": result.generation_result.model_dump() if result.generation_result else None,
                "healing_result": result.healing_result.model_dump() if result.healing_result else None,
                "suite_plan": result.suite_plan.model_dump(),
                "discovery": result.discovery.model_dump() if result.discovery else None,
                "plan": result.plan.model_dump(),
                "execution": result.execution.model_dump(),
                "validation": result.validation.model_dump(),
            },
        }


def _build_retriever(graph: FlowKnowledgeGraph) -> KnowledgeRetriever:
    embedding_config = EmbeddingConfig.from_env()
    embedding = create_embedding_provider(embedding_config)
    qdrant_config = QdrantConfig.from_env()
    store = create_vector_store(qdrant_config, embedding)
    indexer = KnowledgeIndexer(
        discovery_root=graph.discovery_root,
        automation_dir=graph.automation_dir,
        config=qdrant_config,
        embedding_config=embedding_config,
        store=store,
        embedding=embedding,
    )
    return KnowledgeRetriever(
        graph,
        config=qdrant_config,
        store=store,
        embedding=embedding,
        embedding_config=embedding_config,
        indexer=indexer,
    )


def _build_executor() -> PlaywrightRunner | OpenClawAdapter:
    runner_mode = os.environ.get("QA_RUNNER", "playwright").lower()
    if runner_mode in {"openclaw", "mock"}:
        return OpenClawAdapter(mode="mock" if runner_mode == "mock" else None)
    return PlaywrightRunner()


def _default_explore_dry_run() -> bool:
    if os.environ.get("QA_EXPLORE_LIVE", "").lower() in {"1", "true", "yes"}:
        return False
    return _default_crawl_dry_run()


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
