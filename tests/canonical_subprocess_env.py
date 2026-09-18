"""Canonical ScoutAI subprocess environment (P10.3).

Production runtime is ``qa_orchestrator`` + ``scripts/local_agent_server.py``.
``services/agent-runtime`` remains on PYTHONPATH for shared LLM gateway imports only —
not as ``base_agent.api`` / AgentRuntime entrypoint.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def canonical_pythonpath() -> str:
    return os.pathsep.join(
        (
            str(REPO_ROOT / "services" / "agent-runtime"),
            str(REPO_ROOT / "services" / "qa-orchestrator"),
            str(REPO_ROOT),
        )
    )


def canonical_subprocess_env(**overrides: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if isinstance(v, str)}
    env["PYTHONPATH"] = canonical_pythonpath()
    env.setdefault("QA_RUNNER", "dry_run")
    env.setdefault("LLM_ENABLED", "false")
    env.setdefault("QA_QDRANT_ENABLED", "false")
    env.setdefault("QA_EMBEDDING_PROVIDER", "deterministic")
    env.setdefault("QA_USE_LEGACY_AGENT_RUNTIME", "false")
    env.update({k: str(v) for k, v in overrides.items()})
    return env
