"""P6.1 / P10.2 — persist resumable agent run state with per-run locking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel, Field

from qa_orchestrator.agent_models import AgentRunState
from qa_orchestrator.fs_atomic import atomic_write_json, run_file_lock

STATE_SCHEMA_VERSION = "p6.1-v1"


class ResumableAgentSnapshot(BaseModel):
    schema_version: str = STATE_SCHEMA_VERSION
    run_id: str
    state: AgentRunState
    checkpoint: str = "after_plan"
    pending_action: str | None = None
    approval_reason: str = ""
    approval_pause_kind: str = "none"
    completed_steps: list[str] = Field(default_factory=list)
    resume_token: str = Field(default_factory=lambda: uuid4().hex)
    last_applied_resume_token: str | None = None
    artifact_fingerprints: dict[str, str] = Field(default_factory=dict)
    artifact_status_at_pause: dict[str, str] = Field(default_factory=dict)
    run_request: dict[str, Any] = Field(default_factory=dict)


def state_path(base_dir: str | Path, run_id: str) -> Path:
    return Path(base_dir) / run_id / "state.json"


def save_snapshot(snapshot: ResumableAgentSnapshot, *, base_dir: str | Path = "reports/agent") -> Path:
    path = state_path(base_dir, snapshot.run_id)
    with run_file_lock(Path(base_dir), snapshot.run_id):
        atomic_write_json(path, snapshot.model_dump())
    return path


def load_snapshot(run_id: str, *, base_dir: str | Path = "reports/agent") -> ResumableAgentSnapshot:
    path = state_path(base_dir, run_id)
    if not path.exists():
        raise FileNotFoundError(f"agent state not found for run_id={run_id}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"corrupt agent state JSON for run_id={run_id}") from exc
    snapshot = ResumableAgentSnapshot.model_validate(data)
    if snapshot.run_id != run_id:
        raise ValueError(f"run_id mismatch: expected {run_id}, found {snapshot.run_id}")
    if snapshot.schema_version != STATE_SCHEMA_VERSION:
        raise ValueError(f"incompatible state schema: {snapshot.schema_version}")
    return snapshot


def mutate_snapshot(
    run_id: str,
    mutator: Callable[[ResumableAgentSnapshot], None],
    *,
    base_dir: str | Path = "reports/agent",
) -> ResumableAgentSnapshot:
    with run_file_lock(Path(base_dir), run_id):
        snapshot = load_snapshot(run_id, base_dir=base_dir)
        mutator(snapshot)
        path = state_path(base_dir, run_id)
        atomic_write_json(path, snapshot.model_dump())
        return snapshot


def artifact_fingerprint(path: Path) -> str:
    if not path.exists():
        return ""
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
