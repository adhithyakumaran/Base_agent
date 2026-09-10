from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from base_agent.budget.guard import BudgetGuard
from base_agent.contracts.models import Goal, RunBudget, RunCounters
from base_agent.contracts.result import AgentResult
from base_agent.decision.engine import DecisionEngine
from base_agent.graph.builder import build_graph
from base_agent.ground_truth.protocol import GroundTruthFact, GroundTruthProvider, InMemoryGroundTruthProvider
from base_agent.knowledge.protocol import InMemoryKnowledgeProvider, KnowledgeProvider
from base_agent.observation.pipeline import ObservationPipeline
from base_agent.routing.hybrid import GoalHandler, HybridRouter
from base_agent.tools.registry import ToolExecutor, ToolRegistry


class AgentRuntime:
    """Enterprise entrypoint: run(goal) -> AgentResult.

    Guarantees:
    - Deterministic-first control plane
    - Hard budgets (never loop-until-success)
    - Structured conclusions including UNKNOWN / INSUFFICIENT_EVIDENCE
    - Works without Ground Truth (rules + KB only)
    """

    def __init__(
        self,
        *,
        registry: ToolRegistry | None = None,
        kb: KnowledgeProvider | None = None,
        gt: GroundTruthProvider | None = None,
        budget: RunBudget | None = None,
        permissions: list[str] | None = None,
        llm_enabled: bool = False,
    ) -> None:
        self.registry = registry or ToolRegistry()
        self.kb = kb or InMemoryKnowledgeProvider()
        self.gt = gt or InMemoryGroundTruthProvider()
        self.budget = budget or RunBudget()
        self.permissions = permissions or [
            "tool.execute:mock.demo.*",
            "tool.execute:qa.apex.*",
            "knowledge.write",
            "knowledge.read",
        ]
        self.llm_enabled = llm_enabled
        self.executor = ToolExecutor(self.registry)
        self.router = HybridRouter(self.registry)
        self.decision_engine = DecisionEngine(BudgetGuard(self.budget))
        self.observation_pipeline = ObservationPipeline(self.gt)
        self.graph = build_graph(
            registry=self.registry,
            executor=self.executor,
            router=self.router,
            decision_engine=self.decision_engine,
            observation_pipeline=self.observation_pipeline,
            permissions=self.permissions,
        )

    def run(self, goal: str, *, metadata: dict[str, Any] | None = None, recursion_limit: int | None = None) -> AgentResult:
        run_id = uuid.uuid4().hex
        parsed = GoalHandler().parse(goal)
        init = {
            "run_id": run_id,
            "thread_id": run_id,
            "goal": parsed,
            "status": "new",
            "current_step": 0,
            "counters": RunCounters(),
            "budget": self.budget,
            "observations": [],
            "tool_calls": [],
            "decisions": [],
            "errors": [],
            "kb_refs": [],
            "gt_refs": [],
            "evidence_refs": [],
            "recent_signatures": [],
            "recent_state_hashes": [],
            "metadata": metadata or {},
            "llm_enabled": self.llm_enabled,
            "plugins_loaded": sorted({t.plugin_id for t in self.registry.list()}),
        }
        # recursion_limit bounds LangGraph supersteps; product budget is authoritative inside nodes
        limit = recursion_limit or (self.budget.max_steps * 4 + 5)
        out = self.graph.invoke(init, config={"recursion_limit": limit})
        result = out.get("result")
        if not result:
            return AgentResult.unknown(goal, "runtime.no_result", "Graph completed without result assembler output")
        return AgentResult.model_validate(result)


def build_default_runtime(*, kb_dir: str | None = None) -> AgentRuntime:
    """Factory used by CI/examples — loads mock + QA apex tools and optional KB pack."""
    import sys

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from plugins.mock_demo.tools import register_mock_demo
    from plugins.qa_apex.tools import load_kb_docs_from_dir, register_qa_apex

    kb = InMemoryKnowledgeProvider()
    gt = InMemoryGroundTruthProvider()
    # Seed banner GT for deterministic demo (playground-style)
    gt.record_approved_result(
        GroundTruthFact(
            id="gt.promo.banner.visibility",
            subject="promo.banner.visibility",
            predicate="visible_between",
            expected={"start": "09:00", "end": "18:00", "tz": "Asia/Kolkata"},
            applies_when={},
            compare_mode="expr",
        )
    )
    # Seed add expected value as GT example
    gt.record_approved_result(
        GroundTruthFact(
            id="gt.demo.add.2_2",
            subject="demo.add.result",
            predicate="equals",
            expected=4,
            compare_mode="equals",
        )
    )

    registry = ToolRegistry()
    register_mock_demo(registry)
    if kb_dir and Path(kb_dir).exists():
        load_kb_docs_from_dir(kb, kb_dir)
    register_qa_apex(registry, kb)

    return AgentRuntime(registry=registry, kb=kb, gt=gt, llm_enabled=False)


def main() -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Base Agent runtime CLI")
    parser.add_argument("goal", help="Natural language goal")
    parser.add_argument("--kb-dir", default="discovery/uat_ea/kb", help="KB JSON directory")
    args = parser.parse_args()
    runtime = build_default_runtime(kb_dir=args.kb_dir)
    result = runtime.run(args.goal)
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()