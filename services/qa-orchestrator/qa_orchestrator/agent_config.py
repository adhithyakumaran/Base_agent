"""P6 — bounded agent loop configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class AgentConfig:
    max_iterations: int = 5
    max_recoveries: int = 2
    max_steps: int = 50
    timeout_ms: int = 300_000
    safe_confidence_threshold: float = 0.55
    journal_dir: str = "reports/agent"

    @classmethod
    def from_env(cls) -> AgentConfig:
        return cls(
            max_iterations=_env_int("QA_AGENT_MAX_ITERATIONS", 5),
            max_recoveries=_env_int("QA_AGENT_MAX_RECOVERIES", 2),
            max_steps=_env_int("QA_AGENT_MAX_STEPS", 50),
            timeout_ms=_env_int("QA_AGENT_TIMEOUT_MS", 300_000),
            safe_confidence_threshold=_env_float("QA_AGENT_SAFE_CONFIDENCE", 0.55),
            journal_dir=os.environ.get("QA_AGENT_JOURNAL_DIR", "reports/agent"),
        )
