"""Redact sensitive values from live browser event streams."""

from __future__ import annotations

import re
from typing import Any

_SENSITIVE_KEYS = re.compile(
    r"(password|passwd|token|cookie|authorization|api[_-]?key|secret|bearer)",
    re.I,
)
_SENSITIVE_ENV = re.compile(r"EA_USER_PASSWORD|AUTH|TOKEN|COOKIE", re.I)


def redact_value(key: str, value: Any) -> Any:
    if value is None:
        return None
    text = str(value)
    if _SENSITIVE_KEYS.search(key) or _SENSITIVE_ENV.search(key):
        return "[redacted]"
    if _SENSITIVE_KEYS.search(text):
        return "[redacted]"
    return value


def redact_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            out[key] = {k: redact_value(k, v) for k, v in value.items()}
        elif isinstance(value, list):
            out[key] = [redact_value(key, v) for v in value]
        else:
            out[key] = redact_value(key, value)
    target = str(payload.get("target") or "")
    if _SENSITIVE_KEYS.search(target) and "value_summary" in out:
        out["value_summary"] = "[redacted]"
    return out
