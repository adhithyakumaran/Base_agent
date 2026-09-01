"""Enterprise LLM gateway — consultant only, never the control plane."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


Role = Literal["fast", "reasoning", "fallback"]


class LlmRole:
    FAST = "fast"
    REASONING = "reasoning"
    FALLBACK = "fallback"


class LlmRequest(BaseModel):
    role: str = "fast"
    purpose: str = "generic"
    prompt: str
    schema_name: str | None = None
    token_budget: int = 512
    timeout_ms: int = 15_000
    system: str | None = None
    temperature: float = 0.0


class LlmResponse(BaseModel):
    text: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = "disabled"
    ok: bool = True
    error: str | None = None
    used: bool = False


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
        return LlmResponse(text="", data={}, tokens_in=0, tokens_out=0, model="null", used=True)


@dataclass
class EnterpriseLlmGateway:
    """Dynamic multi-role gateway for production.

    - Default disabled (crawl/sanity = 0 LLM)
    - Roles: fast / reasoning / fallback
    - Optional LiteLLM when extras installed and LLM_ENABLED=true
    - Never owns budgets, routing loops, or GT comparison
    """

    enabled: bool = False
    models: dict[str, str] = field(
        default_factory=lambda: {
            "fast": os.environ.get("LLM_MODEL_FAST", "gpt-4o-mini"),
            "reasoning": os.environ.get("LLM_MODEL_REASONING", "gpt-4o"),
            "fallback": os.environ.get("LLM_MODEL_FALLBACK", "gpt-4o-mini"),
        }
    )
    max_calls_per_run: int = 3
    _calls: int = 0

    @classmethod
    def from_env(cls) -> "EnterpriseLlmGateway":
        flag = os.environ.get("LLM_ENABLED", "false").lower() in {"1", "true", "yes"}
        return cls(enabled=flag)

    def available(self) -> bool:
        return self.enabled and self._calls < self.max_calls_per_run

    def complete(self, req: LlmRequest) -> LlmResponse:
        role: Role = req.role if req.role in {"fast", "reasoning", "fallback"} else "fast"
        if not self.available():
            return LlmResponse(
                ok=False,
                error="llm.disabled_or_budget" if not self.enabled else "llm.run_budget",
                model=self.models.get(role, "disabled"),
                used=False,
            )
        model = self.models.get(role) or self.models["fast"]
        self._calls += 1
        try:
            import litellm  # type: ignore

            messages: list[dict[str, str]] = []
            if req.system:
                messages.append({"role": "system", "content": req.system})
            messages.append({"role": "user", "content": req.prompt})
            resp = litellm.completion(model=model, messages=messages, temperature=req.temperature)
            text = resp.choices[0].message.content or ""
            usage = getattr(resp, "usage", None)
            return LlmResponse(
                ok=True,
                text=text,
                model=model,
                tokens_in=int(getattr(usage, "prompt_tokens", 0) or 0),
                tokens_out=int(getattr(usage, "completion_tokens", 0) or 0),
                used=True,
            )
        except ImportError:
            return LlmResponse(ok=False, error="llm.litellm_not_installed", model=model, used=False)
        except Exception as exc:  # noqa: BLE001
            if role != "fallback":
                fb = req.model_copy(update={"role": "fallback"})
                return self.complete(fb)
            return LlmResponse(ok=False, error=f"llm.error:{type(exc).__name__}", model=model, used=False)

    def health(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "calls": self._calls,
            "max_calls_per_run": self.max_calls_per_run,
            "models": dict(self.models),
            "control_plane": False,
            "note": "LLM never owns budgets, routing loops, or GT comparison",
        }
