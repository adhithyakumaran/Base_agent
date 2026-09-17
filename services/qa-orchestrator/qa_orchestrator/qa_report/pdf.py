"""PDF export via WeasyPrint (HTML source of truth)."""

from __future__ import annotations

from pathlib import Path


def render_pdf_bytes(html: str, *, base_url: Path) -> bytes:
    try:
        from weasyprint import HTML
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("WeasyPrint is not installed. pip install weasyprint") from exc
    return HTML(string=html, base_url=str(base_url.resolve())).write_pdf()
