from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class LlmRole(str):
    FAST = "fast"
    REASONING = "reasoning"
    FALLBACK = "fallback"


class LlmRequest(BaseModel):
    role: str = "fast"
    purpose: str
    prompt: str
    schema_name: str | None = None
    token_budget: int = 512
    timeout_ms: int = 15_000


class LlmResponse(BaseModel):
    text: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = "disabled"


class LlmGateway(Protocol):
    def complete(self, req: LlmRequest) -> LlmResponse: ...


class DisabledLlmGateway:
    """Enterprise-safe default: LLM off unless explicitly configured."""

    def complete(self, req: LlmRequest) -> LlmResponse:
        raise RuntimeError("LLM disabled — deterministic path required or enable gateway")


class CountingNullLlmGateway:
    """Test double that records calls but returns empty structured data."""

    def __init__(self) -> None:
        self.calls: list[LlmRequest] = []

    def complete(self, req: LlmRequest) -> LlmResponse:
        self.calls.append(req)
        return LlmResponse(text="", data={}, tokens_in=0, tokens_out=0, model="null")