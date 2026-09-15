"""P10.2 — atomic approval log append with file locking."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qa_orchestrator.execution_gate import CANONICAL_ARTIFACT
from qa_orchestrator.fs_atomic import atomic_write_json, mutate_json_file, resource_lock_path


def approval_log_lock_path(log_path: Path) -> Path:
    return resource_lock_path(log_path.parent, f"approval-log-{log_path.name}")


def load_approval_records(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    import json

    try:
        data = json.loads(log_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    records = data.get("records") if isinstance(data, dict) else None
    return list(records) if isinstance(records, list) else []


def append_approval_record(log_path: Path, record: dict[str, Any], *, max_records: int = 500) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lock = approval_log_lock_path(log_path)

    def _default() -> dict[str, Any]:
        return {"records": []}

    def _mutator(data: dict[str, Any]) -> dict[str, Any]:
        records = list(data.get("records") or [])
        records.insert(0, record)
        return {"records": records[:max_records]}

    mutate_json_file(log_path, lock_path=lock, default=_default, mutator=_mutator)


def bootstrap_record(
    *,
    flow_id: str,
    status: str,
    actor: str,
    source: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "flowId": flow_id,
        "artifact": CANONICAL_ARTIFACT,
        "status": status,
        "approver": actor,
        "decidedAt": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "reason": reason,
    }
