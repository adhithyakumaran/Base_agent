"""Validate orchestrator run parameters before passing to Playwright."""

from __future__ import annotations

import re
from typing import Any

_PARAM_PATTERNS: dict[str, re.Pattern[str]] = {
    "SKU": re.compile(r"^[A-Za-z0-9-]{3,32}$"),
}


def validate_run_params(params: dict[str, Any] | None) -> dict[str, str]:
    """Return sanitized params or raise ValueError for unsafe values."""
    if not params:
        return {}
    out: dict[str, str] = {}
    for key, value in params.items():
        name = str(key).strip().upper()
        if not name or not re.fullmatch(r"[A-Z0-9_]{1,32}", name):
            raise ValueError(f"invalid param name: {key!r}")
        text = str(value).strip()
        if not text:
            raise ValueError(f"empty param value for {name}")
        pattern = _PARAM_PATTERNS.get(name)
        if pattern and not pattern.fullmatch(text):
            raise ValueError(f"invalid param {name}: {text!r}")
        if re.search(r"[\r\n\0;|&$`<>]", text):
            raise ValueError(f"unsafe characters in param {name}")
        out[name.lower()] = text
    return out


def params_to_env(validated: dict[str, str]) -> dict[str, str]:
    """Map validated params to QA_PARAM_* environment variables."""
    return {f"QA_PARAM_{key.upper()}": value for key, value in validated.items()}
