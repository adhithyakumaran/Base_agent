"""Plain-text helpers for LLM fields embedded in markdown reports."""

from __future__ import annotations

import re


def strip_markdown(text: str) -> str:
    """Remove common markdown artifacts so PDF/email exports stay readable."""
    if not text:
        return ""
    out = text.replace("\r\n", "\n").strip()
    out = re.sub(r"```[\s\S]*?```", " ", out)
    out = re.sub(r"`([^`]+)`", r"\1", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"\1", out)
    out = re.sub(r"\*([^*]+)\*", r"\1", out)
    out = re.sub(r"_([^_]+)_", r"\1", out)
    out = re.sub(r"^#{1,6}\s+", "", out, flags=re.MULTILINE)
    out = re.sub(r"^\s*[-*]\s+", "• ", out, flags=re.MULTILINE)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()
