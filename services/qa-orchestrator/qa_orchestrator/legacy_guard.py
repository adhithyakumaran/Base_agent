"""P6.1 / P10.1 — guardrails for canonical vs legacy orchestration paths."""

from __future__ import annotations

import os

CANONICAL_ORCHESTRATOR = "qa_orchestrator.ControlledAgentLoop"
LEGACY_RUNTIME = "base_agent.AgentRuntime"
CANONICAL_WARM_SERVER = "scripts/local_agent_server.py"
LEGACY_API_MODULE = "base_agent.api"


def legacy_runtime_requested() -> bool:
    return os.environ.get("QA_USE_LEGACY_AGENT_RUNTIME", "").lower() in {"1", "true", "yes"}


def assert_canonical_agent_path(entrypoint: str) -> None:
    """Reject accidental legacy runtime selection on canonical agent entrypoints."""
    if legacy_runtime_requested() and entrypoint in {"agent_cli", "local_agent_server", "qa_orchestrator.api"}:
        raise RuntimeError(
            f"{entrypoint} uses canonical ControlledAgentLoop; set QA_USE_LEGACY_AGENT_RUNTIME=false"
        )


def canonical_path_metadata() -> dict[str, str]:
    return {
        "orchestrator_path": CANONICAL_ORCHESTRATOR,
        "warm_server_entry": CANONICAL_WARM_SERVER,
        "legacy_runtime": LEGACY_RUNTIME,
        "legacy_api_module": LEGACY_API_MODULE,
        "legacy_runtime_enabled": str(legacy_runtime_requested()).lower(),
        "legacy_runtime_canonical": "false",
        "production_runtime": CANONICAL_ORCHESTRATOR,
    }
