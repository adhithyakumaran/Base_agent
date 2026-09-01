from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from base_agent.contracts.models import (
    Decision,
    DecisionRecord,
    Goal,
    Observation,
    RunBudget,
    RunCounters,
    ToolCallRecord,
)


def _append(existing: list, new: list) -> list:
    return (existing or []) + (new or [])


class AgentState(TypedDict, total=False):
    run_id: str
    thread_id: str
    goal: Goal
    status: str
    current_step: int
    current_capability: str | None
    pending_decision: Decision | None
    observations: Annotated[list[Observation], _append]
    tool_calls: Annotated[list[ToolCallRecord], _append]
    decisions: Annotated[list[DecisionRecord], _append]
    errors: Annotated[list[dict[str, Any]], _append]
    kb_refs: Annotated[list[str], operator.add]
    gt_refs: Annotated[list[str], operator.add]
    evidence_refs: Annotated[list[str], operator.add]
    counters: RunCounters
    budget: RunBudget
    recent_signatures: Annotated[list[str], _append]
    recent_state_hashes: Annotated[list[str], _append]
    result: dict[str, Any] | None
    metadata: dict[str, Any]
    context_packet: dict[str, Any] | None
    routing: dict[str, Any] | None
    last_raw_result: dict[str, Any] | None
    last_observation: Observation | None
    llm_enabled: bool
    plugins_loaded: list[str]