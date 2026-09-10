from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from base_agent.llm.gateway import LlmRequest, LlmResponse


DEFAULT_GROQ_FAST = "groq/qwen/qwen3.6-27b"
DEFAULT_GROQ_REASONING = "groq/openai/gpt-oss-120b"
DEFAULT_CLAUDE = "claude-sonnet-4-20250514"


@dataclass
class PlannerLlmClient:
    """Groq-first planner client; swap to Claude via env when ready."""

    enabled: bool = False
    provider: str = "groq"
    model_fast: str = DEFAULT_GROQ_FAST
    model_reasoning: str = DEFAULT_GROQ_REASONING
    max_calls: int = 3
    _calls: int = 0
    _tokens_in: int = 0
    _tokens_out: int = 0

    @classmethod
    def from_env(cls, *, model_id: str | None = None) -> "PlannerLlmClient":
        provider = os.environ.get("LLM_PROVIDER", "groq").lower()
        enabled = os.environ.get("LLM_ENABLED", "true").lower() in {"1", "true", "yes"}
        has_key = bool(os.environ.get("GROQ_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))
        if not has_key:
            enabled = False

        fast = os.environ.get("LLM_MODEL_FAST", DEFAULT_GROQ_FAST)
        reasoning = os.environ.get("LLM_MODEL_REASONING", DEFAULT_GROQ_REASONING)
        if model_id and model_id != "disabled":
            if "claude" in model_id:
                provider = "anthropic"
                reasoning = model_id if model_id.startswith("claude") else DEFAULT_CLAUDE
            elif model_id.startswith("groq/"):
                provider = "groq"
                reasoning = model_id
            else:
                reasoning = model_id

        return cls(
            enabled=enabled,
            provider=provider,
            model_fast=fast,
            model_reasoning=reasoning,
        )

    @property
    def tokens_in(self) -> int:
        return self._tokens_in

    @property
    def tokens_out(self) -> int:
        return self._tokens_out

    @property
    def llm_calls(self) -> int:
        return self._calls

    def complete_json(
        self,
        *,
        purpose: str,
        system: str,
        prompt: str,
        role: str = "reasoning",
    ) -> tuple[dict[str, Any] | None, LlmResponse]:
        if not self.enabled or self._calls >= self.max_calls:
            return None, LlmResponse(ok=False, error="llm.disabled_or_budget", used=False)

        model = self.model_reasoning if role == "reasoning" else self.model_fast
        req = LlmRequest(
            role=role,
            purpose=purpose,
            system=system,
            prompt=prompt,
            temperature=0.1,
            token_budget=1200,
        )
        resp = self._complete(req, model)
        if not resp.ok:
            return None, resp
        data = _extract_json(resp.text)
        return data, resp

    def summarize(self, *, prompt: str) -> tuple[str, LlmResponse]:
        if not self.enabled or self._calls >= self.max_calls:
            return "", LlmResponse(ok=False, error="llm.disabled_or_budget", used=False)
        req = LlmRequest(
            role="fast",
            purpose="report_summary",
            prompt=prompt,
            temperature=0.2,
            token_budget=400,
        )
        resp = self._complete(req, self.model_fast)
        return resp.text.strip(), resp

    def _complete(self, req: LlmRequest, model: str) -> LlmResponse:
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
            tokens_in = int(getattr(usage, "prompt_tokens", 0) or 0)
            tokens_out = int(getattr(usage, "completion_tokens", 0) or 0)
            self._tokens_in += tokens_in
            self._tokens_out += tokens_out
            return LlmResponse(
                ok=True,
                text=text,
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                used=True,
            )
        except ImportError:
            return LlmResponse(ok=False, error="llm.litellm_not_installed", model=model, used=False)
        except Exception as exc:  # noqa: BLE001
            return LlmResponse(ok=False, error=f"llm.error:{type(exc).__name__}:{exc}", model=model, used=False)


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None
