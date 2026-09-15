"""File-based live browser close signal and session metadata (graceful close contract)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qa_orchestrator.fs_atomic import atomic_write_json


def session_meta_path(profile_dir: Path) -> Path:
    return profile_dir / "session.json"


def close_signal_path(profile_dir: Path) -> Path:
    return profile_dir / "close.signal"


def read_session_meta(profile_dir: Path) -> dict[str, Any]:
    path = session_meta_path(profile_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_session_meta(profile_dir: Path, meta: dict[str, Any]) -> None:
    profile_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(session_meta_path(profile_dir), meta)


def close_signal_present(profile_dir: Path) -> bool:
    return close_signal_path(profile_dir).exists()


def consume_close_signal(profile_dir: Path) -> bool:
    path = close_signal_path(profile_dir)
    if not path.exists():
        return False
    path.unlink(missing_ok=True)
    return True


def mark_session_closed(profile_dir: Path, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = read_session_meta(profile_dir)
    if meta.get("status") == "CLOSED":
        consume_close_signal(profile_dir)
        return meta
    meta = {
        **meta,
        "status": "CLOSED",
        "closed_at": datetime.now(timezone.utc).isoformat(),
        **(extra or {}),
    }
    write_session_meta(profile_dir, meta)
    consume_close_signal(profile_dir)
    return meta


def process_close_signal(profile_dir: Path) -> tuple[bool, dict[str, Any]]:
    """
    If close.signal exists, mark session CLOSED and consume signal.
    Returns (changed, session_meta).
    """
    if not close_signal_present(profile_dir):
        meta = read_session_meta(profile_dir)
        return False, meta
    meta = mark_session_closed(profile_dir)
    return True, meta
