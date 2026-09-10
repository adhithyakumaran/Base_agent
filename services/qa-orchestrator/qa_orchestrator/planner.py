from __future__ import annotations

from typing import Any

from qa_orchestrator.intent_classifier import IntentClassifier
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.llm_client import PlannerLlmClient
from qa_orchestrator.models import ExecutionPlan, IntentClassification, PlanStep


class Planner:
    """Intent classification planner — maps NL prompts to execution modes and flows."""

    def __init__(self, graph: FlowKnowledgeGraph, llm: PlannerLlmClient) -> None:
        self.graph = graph
        self.llm = llm
        self.classifier = IntentClassifier(graph, llm)

    def classify(
        self,
        goal: str,
        *,
        run_type: str = "adhoc",
        context_packets: list[dict[str, Any]] | None = None,
    ) -> IntentClassification:
        return self.classifier.classify(goal, run_type=run_type, context_packets=context_packets)

    def plan(
        self,
        goal: str,
        *,
        run_type: str = "adhoc",
        context_packets: list[dict[str, Any]] | None = None,
    ) -> ExecutionPlan:
        """Backward-compatible plan view synthesized from intent classification."""
        intent = self.classify(goal, run_type=run_type, context_packets=context_packets)
        return intent_to_execution_plan(intent)


def intent_to_execution_plan(intent: IntentClassification) -> ExecutionPlan:
    steps: list[PlanStep] = []
    for i, cmd in enumerate(intent.suite_ids or ["pending-suite-selection"]):
        steps.append(
            PlanStep(
                action="custom",
                target=cmd,
                note=f"{intent.execution_mode}: {intent.reasoning}",
                kb_ref=intent.flow_ids[0] if intent.flow_ids else None,
            )
        )
    if not steps:
        steps.append(
            PlanStep(
                action="custom",
                target=intent.execution_mode,
                note=intent.reasoning,
            )
        )
    refs = list(dict.fromkeys(intent.flow_ids + intent.supporting_flow_ids))
    return ExecutionPlan(
        goal=intent.goal,
        run_type=intent.run_type,
        summary=intent.reasoning,
        steps=steps,
        kb_refs=refs,
        planner=intent.classifier,
    )
