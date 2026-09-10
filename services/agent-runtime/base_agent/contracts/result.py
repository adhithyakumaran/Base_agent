from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from base_agent.contracts.enums import Conclusion


class EvidenceRef(BaseModel):
    id: str
    kind: str = "observation"
    uri: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Structured terminal result — never a free-form LLM essay as the control output."""

    conclusion: Conclusion
    reason_code: str
    summary: str
    goal: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    kb_refs: list[str] = Field(default_factory=list)
    gt_refs: list[str] = Field(default_factory=list)
    tool_calls: int = 0
    llm_calls: int = 0
    steps: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def blocked(cls, goal: str, reason_code: str, summary: str, **kwargs: Any) -> AgentResult:
        return cls(conclusion=Conclusion.BLOCKED, reason_code=reason_code, summary=summary, goal=goal, **kwargs)

    @classmethod
    def unknown(cls, goal: str, reason_code: str, summary: str, **kwargs: Any) -> AgentResult:
        return cls(conclusion=Conclusion.UNKNOWN, reason_code=reason_code, summary=summary, goal=goal, **kwargs)

    @classmethod
    def insufficient(cls, goal: str, reason_code: str, summary: str, **kwargs: Any) -> AgentResult:
        return cls(
            conclusion=Conclusion.INSUFFICIENT_EVIDENCE,
            reason_code=reason_code,
            summary=summary,
            goal=goal,
            **kwargs,
        )