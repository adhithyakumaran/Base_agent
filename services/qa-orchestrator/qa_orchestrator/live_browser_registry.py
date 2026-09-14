"""Runtime registry for live browser sessions (in-memory only)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class LiveBrowserSessionMeta:
    run_id: str
    browser_session_id: str
    profile_dir: str
    status: str = "STARTING"
    current_url: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    channel: str = "chromium"
    headless: bool = True
    keep_open: bool = False
    host_pid: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "browser_session_id": self.browser_session_id,
            "profile_dir": self.profile_dir,
            "status": self.status,
            "current_url": self.current_url,
            "started_at": self.started_at,
            "channel": self.channel,
            "headless": self.headless,
            "keep_open": self.keep_open,
            "host_pid": self.host_pid,
        }


@dataclass
class LiveBrowserSession:
    meta: LiveBrowserSessionMeta
    host_process: Any = None


_REGISTRY: dict[str, LiveBrowserSession] = {}
_LOCK = threading.Lock()


def register_session(session: LiveBrowserSession) -> None:
    with _LOCK:
        _REGISTRY[session.meta.run_id] = session


def get_session(run_id: str) -> LiveBrowserSession | None:
    with _LOCK:
        return _REGISTRY.get(run_id)


def get_session_meta(run_id: str) -> dict[str, Any] | None:
    session = get_session(run_id)
    return session.meta.to_dict() if session else None


def update_session_status(run_id: str, *, status: str, current_url: str = "") -> None:
    with _LOCK:
        session = _REGISTRY.get(run_id)
        if not session:
            return
        session.meta.status = status
        if current_url:
            session.meta.current_url = current_url


def close_session(run_id: str) -> bool:
    with _LOCK:
        session = _REGISTRY.pop(run_id, None)
    if not session:
        return False
    proc = session.host_process
    if proc and getattr(proc, "poll", lambda: None)() is None:
        try:
            proc.terminate()
        except OSError:
            pass
    session.meta.status = "CLOSED"
    return True
