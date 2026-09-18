"""PDF export — Playwright primary, WeasyPrint optional fallback."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


def _render_weasyprint(html: str, base_url: Path) -> bytes:
    from weasyprint import HTML

    return HTML(string=html, base_url=str(base_url.resolve())).write_pdf()


def _render_playwright(html: str, repo_root: Path) -> bytes:
    script = repo_root / "apps" / "automation" / "scripts" / "render-report-pdf.mjs"
    if not script.is_file():
        raise RuntimeError("Playwright PDF script missing at apps/automation/scripts/render-report-pdf.mjs")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".html", delete=False) as tmp:
        tmp.write(html)
        html_path = tmp.name
    try:
        automation_dir = repo_root / "apps" / "automation"
        env = os.environ.copy()
        env.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(automation_dir / "node_modules" / "playwright-core"))
        proc = subprocess.run(
            ["node", str(script), html_path, str(repo_root.resolve())],
            cwd=str(automation_dir),
            capture_output=True,
            check=False,
            env=env,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace")
            raise RuntimeError(f"Playwright PDF render failed: {err.strip() or proc.returncode}")
        if not proc.stdout.startswith(b"%PDF"):
            raise RuntimeError("Playwright PDF render did not produce a valid PDF")
        return proc.stdout
    finally:
        try:
            os.unlink(html_path)
        except OSError:
            pass


def render_pdf_bytes(html: str, *, base_url: Path) -> bytes:
    repo_root = base_url
    try:
        return _render_playwright(html, repo_root)
    except Exception as playwright_err:
        try:
            return _render_weasyprint(html, base_url)
        except ImportError as imp_err:
            raise RuntimeError(
                "PDF export unavailable: Playwright render failed and WeasyPrint is not installed."
            ) from playwright_err
        except OSError as os_err:
            raise RuntimeError(
                "PDF export unavailable: Playwright render failed and WeasyPrint native libs missing "
                "(use Playwright path on Windows)."
            ) from os_err
