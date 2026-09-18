"""SSE live-event cursor helpers (dedupe by monotonic sequence)."""

from __future__ import annotations

from typing import Any


def events_after_sequence(events: list[dict[str, Any]], after_sequence: int) -> list[dict[str, Any]]:
    ordered = sorted(events, key=lambda row: int(row.get("sequence") or 0))
    out: list[dict[str, Any]] = []
    for row in ordered:
        seq = int(row.get("sequence") or 0)
        if seq <= after_sequence:
            continue
        out.append(row)
    return out


def advance_sse_cursor(cursor: int, batch: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    """Apply one SSE batch; skip duplicates already at or below cursor."""
    delivered: list[dict[str, Any]] = []
    next_cursor = cursor
    for row in events_after_sequence(batch, cursor):
        seq = int(row.get("sequence") or 0)
        if seq <= next_cursor:
            continue
        delivered.append(row)
        next_cursor = seq
    return next_cursor, delivered
