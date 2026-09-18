"""P10.1 — canonical production runtime entrypoint selection."""

from __future__ import annotations

from pathlib import Path

CANONICAL_WARM_ENTRY = "scripts/local_agent_server.py"
CANONICAL_RUNTIME = "qa_orchestrator.ControlledAgentLoop"
LEGACY_RUNTIME_ENTRY = "python -m base_agent.api"
LEGACY_RUNTIME_LABEL = "base_agent.AgentRuntime"


def production_entrypoint_path(repo_root: Path) -> Path:
    return repo_root / CANONICAL_WARM_ENTRY


def assert_production_entrypoint(repo_root: Path, dockerfile_text: str) -> None:
    entry_section = dockerfile_text.split("ENTRYPOINT", 1)[-1]
    if "base_agent.api" in entry_section:
        raise AssertionError("Dockerfile must not use base_agent.api as production ENTRYPOINT")
    if "local_agent_server.py" not in dockerfile_text:
        raise AssertionError("Dockerfile must start scripts/local_agent_server.py (canonical warm orchestrator)")
    if not production_entrypoint_path(repo_root).exists():
        raise AssertionError(f"Missing canonical entrypoint: {CANONICAL_WARM_ENTRY}")
