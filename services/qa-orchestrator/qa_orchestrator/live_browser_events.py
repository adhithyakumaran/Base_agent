"""Live browser action events and SSE-friendly persistence."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from qa_orchestrator.live_browser_redaction import redact_event_payload


@dataclass
class AgentLiveEvent:
    run_id: str
    sequence: int
    timestamp: str
    phase: str
    action: str
    target: str = ""
    value_summary: str = ""
    status: str = "OK"
    duration_ms: int = 0
    evidence_ref: str = ""
    source: str = "PLAYWRIGHT"
    flow_id: str = ""
    step_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return redact_event_payload(asdict(self))


class LiveEventStore:
    def __init__(self, run_id: str, *, path: Path | None = None) -> None:
        self.run_id = run_id
        self._lock = threading.Lock()
        self._sequence = 0
        self._events: list[AgentLiveEvent] = []
        self._subscribers: list[threading.Event] = []
        if path is None:
            from qa_orchestrator.live_browser_config import events_path

            path = Path(events_path(run_id))
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(
        self,
        *,
        phase: str,
        action: str,
        target: str = "",
        value_summary: str = "",
        status: str = "OK",
        duration_ms: int = 0,
        evidence_ref: str = "",
        flow_id: str = "",
        step_id: str = "",
    ) -> AgentLiveEvent:
        with self._lock:
            self._sequence += 1
            event = AgentLiveEvent(
                run_id=self.run_id,
                sequence=self._sequence,
                timestamp=datetime.now(timezone.utc).isoformat(),
                phase=phase,
                action=action,
                target=target,
                value_summary=value_summary,
                status=status,
                duration_ms=duration_ms,
                evidence_ref=evidence_ref,
                flow_id=flow_id,
                step_id=step_id,
            )
            self._events.append(event)
            line = json.dumps(event.to_dict()) + "\n"
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line)
        return event

    def list_events(self, *, after_sequence: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self._events if e.sequence > after_sequence]

    def iter_sse(self, *, poll_ms: int = 400, timeout_s: float = 3600.0) -> Iterator[str]:
        deadline = time.time() + timeout_s
        cursor = 0
        while time.time() < deadline:
            batch = self.list_events(after_sequence=cursor)
            for item in batch:
                cursor = item["sequence"]
                yield f"data: {json.dumps(item)}\n\n"
            if _run_cancelled(self.run_id):
                yield f"data: {json.dumps({'phase': 'CANCEL', 'action': 'STOP', 'status': 'CANCELLED'})}\n\n"
                break
            time.sleep(poll_ms / 1000.0)


_STORES: dict[str, LiveEventStore] = {}
_CANCELLED: set[str] = set()
_STORE_LOCK = threading.Lock()


def get_event_store(run_id: str) -> LiveEventStore:
    with _STORE_LOCK:
        if run_id not in _STORES:
            _STORES[run_id] = LiveEventStore(run_id)
        return _STORES[run_id]


def mark_run_cancelled(run_id: str) -> None:
    with _STORE_LOCK:
        _CANCELLED.add(run_id)


def _run_cancelled(run_id: str) -> bool:
    return run_id in _CANCELLED


def load_events_from_file(path: Path, *, after_sequence: int = 0) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if int(row.get("sequence") or 0) > after_sequence:
            out.append(row)
    return out
