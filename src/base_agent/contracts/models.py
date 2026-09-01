from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Goal(BaseModel):
    raw_text: str
    intent_type: str = "execute"  # execute | validate | retrieve | discover | unknown
    entities: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    capability_hints: list[str] = Field(default_factory=list)
    ambiguity_score: float = 0.0
    needs_clarification: bool = False
    parse_method: str = "deterministic"  # deterministic | llm


class ToolCallRecord(BaseModel):
    name: str
    capability: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] | None = None
    ok: bool = True
    error_class: str | None = None
    latency_ms: float = 0.0
    attempt: int = 1


class Observation(BaseModel):
    id: str
    source_tool: str
    source_plugin: str | None = None
    trust: str = "untrusted_tool_output"
    payload: dict[str, Any] = Field(default_factory=dict)
    validation_outcome: str | None = None  # pass|fail|not_applicable|insufficient
    used_llm: bool = False
    reason_code: str | None = None


class DecisionRecord(BaseModel):
    action: str
    reason_code: str
    llm_used: bool = False
    confidence: float = 1.0
    details: dict[str, Any] = Field(default_factory=dict)


class RoutingDecision(BaseModel):
    capability: str | None = None
    tool_name: str | None = None
    candidates: list[str] = Field(default_factory=list)
    method: str = "rule"
    confidence: float = 0.0
    llm_used: bool = False
    reason_code: str = "ok"


class RunCounters(BaseModel):
    steps: int = 0
    tool_calls: int = 0
    llm_calls: int = 0
    retries: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    kb_lookups: int = 0
    pages_visited: int = 0


class RunBudget(BaseModel):
    """Hard caps — agent MUST stop; never loop until success."""

    max_steps: int = 20
    max_tool_calls: int = 30
    max_llm_calls: int = 8
    max_retries_per_tool: int = 2
    max_tokens: int = 50_000
    max_pages: int = 40
    wall_timeout_s: float = 180.0
    max_same_tool_signature: int = 2
    max_same_state_hash: int = 2


class Decision(BaseModel):
    action: str
    reason_code: str
    tool_name: str | None = None
    tool_input: dict[str, Any] = Field(default_factory=dict)
    capability: str | None = None
    conclusion: str | None = None
    summary: str | None = None
    llm_used: bool = False
    confidence: float = 1.0
    details: dict[str, Any] = Field(default_factory=dict)