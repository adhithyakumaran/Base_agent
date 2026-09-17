"""Sanitize QA knowledge before indexing — never store secrets in retrieval payloads."""

from __future__ import annotations

import re

_SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)(token|api[_-]?key|secret|authorization)\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)bearer\s+[a-z0-9\-._~+/]+=*", re.I), "Bearer [REDACTED]"),
    (re.compile(r"(?i)(session[_-]?id|cookie)\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)(APEX_USERNAME|APEX_PASSWORD|QA_PARAM_\w+)\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
]


def sanitize_for_index(text: str) -> str:
    if not text:
        return ""
    out = text.replace("\r\n", "\n")
    for pattern, repl in _SENSITIVE_PATTERNS:
        out = pattern.sub(repl, out)
    return out.strip()


def sanitize_metadata(meta: dict) -> dict:
    blocked = {"password", "token", "secret", "authorization", "cookie", "session_id"}
    clean: dict = {}
    for key, value in meta.items():
        if str(key).lower() in blocked:
            continue
        if isinstance(value, str):
            clean[key] = sanitize_for_index(value)
        elif isinstance(value, dict):
            clean[key] = sanitize_metadata(value)
        elif isinstance(value, list):
            clean[key] = [
                sanitize_for_index(v) if isinstance(v, str) else v for v in value
            ]
        else:
            clean[key] = value
    return clean
