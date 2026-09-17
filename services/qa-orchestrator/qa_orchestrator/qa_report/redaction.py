"""Redact secrets from report payloads and bundle exports."""

from __future__ import annotations

import re
from typing import Any

_SECRET_KEY_RE = re.compile(
    r"(password|passwd|token|secret|api[_-]?key|authorization|cookie|session|credential|bearer)",
    re.I,
)
_SENSITIVE_PATH_RE = re.compile(
    r"(storage-state|auth\.json|cookies|\.env|approval-log|credentials)",
    re.I,
)


def redact_string(value: str) -> str:
    if _SECRET_KEY_RE.search(value):
        return "[REDACTED]"
    return value


def redact_value(key: str, value: Any) -> Any:
    if _SECRET_KEY_RE.search(key):
        return "[REDACTED]"
    if isinstance(value, str):
        if _SECRET_KEY_RE.search(value) and len(value) > 8:
            return "[REDACTED]"
        return value
    if isinstance(value, dict):
        return redact_dict(value)
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    return value


def redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        out[key] = redact_value(str(key), value)
    return out


def path_allowed_in_bundle(path: str) -> bool:
    if _SENSITIVE_PATH_RE.search(path):
        return False
    lowered = path.lower()
    if "node_modules" in lowered:
        return False
    return True
