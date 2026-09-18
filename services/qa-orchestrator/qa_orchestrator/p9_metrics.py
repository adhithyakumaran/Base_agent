"""P9 metric helpers with bounded rate semantics."""

from __future__ import annotations

from typing import Any


def parameter_traceability_applicable(row: dict[str, Any]) -> bool:
    """True when this run row requires end-to-end parameter trace validation."""
    expected = (row.get("parameter_trace") or {}).get("expected")
    if isinstance(expected, dict) and len(expected) > 0:
        return True
    return bool(row.get("parameter_trace_required"))


def compute_parameter_traceability_rate(rows: list[dict[str, Any]]) -> float | None:
    """Rate of successful parameter traces among applicable cases only (0.0–1.0)."""
    applicable = [r for r in rows if parameter_traceability_applicable(r)]
    if not applicable:
        return None
    ok = sum(1 for r in applicable if (r.get("parameter_trace") or {}).get("parameter_ok") is True)
    rate = ok / len(applicable)
    return round(min(1.0, max(0.0, rate)), 4)
