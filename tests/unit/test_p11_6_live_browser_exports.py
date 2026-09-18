"""P11.6 — LIVE_DEMO browser lifecycle, export fixes, execution vs validation separation."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from qa_orchestrator.playwright_runner import classify_playwright_output
from qa_orchestrator.qa_report.builder import build_qa_report
from qa_orchestrator.qa_report.html import render_html_report
from qa_orchestrator.qa_report.pdf import render_pdf_bytes
from qa_orchestrator.qa_report_cli import main as cli_main  # noqa: F401

REPO = Path(__file__).resolve().parents[2]
JOURNAL = REPO / "reports" / "agent"

REAL_STDOUT = """
Running 2 tests using 1 worker
  2 passed (3.9m)
  1 error was not a part of any test
Fixture "liveContext" timeout of 120000ms exceeded during teardown.
"""

REAL_STDERR = "Skipping auth storage — EA_SKIP_GLOBAL_SETUP=true\n"


def test_classify_pass_with_teardown_warning():
    status, warnings = classify_playwright_output(REAL_STDOUT, REAL_STDERR, returncode=1)
    assert status == "PASS_WITH_WARNING"
    assert "live_context_fixture_teardown_timeout" in warnings


def test_classify_ci_pass():
    status, warnings = classify_playwright_output("3 passed (10s)\n", "", 0)
    assert status == "PASS"
    assert warnings == []


def test_report_separates_execution_and_business_validation():
    console = {
        "id": "run_82h6r7abut2w",
        "goal": "Search SKU 552811DUDABA00",
        "conclusion": "NEEDS_REVIEW",
        "status": "needs_review",
        "executionMode": "LIVE_DEMO",
        "report": {
            "json": {
                "agent": {
                    "local": {
                        "suite_plan": {"flow_ids": ["BF-PRODUCT-003"], "params": {"sku": "552811DUDABA00"}},
                        "execution": {
                            "ok": True,
                            "observations": [
                                {
                                    "meta": {
                                        "execution_status": "PASS_WITH_WARNING",
                                        "infrastructure_warnings": ["live_context_fixture_teardown_timeout"],
                                        "stdout_tail": REAL_STDOUT,
                                        "stderr_tail": REAL_STDERR,
                                    }
                                }
                            ],
                        },
                    }
                }
            }
        },
    }
    report = build_qa_report(run_id=console["id"], console_run=console, repo_root=REPO, journal_dir=JOURNAL)
    assert report.execution.execution_status == "PASS_WITH_WARNING"
    assert report.business_validation_status == "NEEDS_REVIEW"
    assert report.overall_result == "NEEDS_REVIEW"


def test_html_utf8_unicode_arrow_and_checkmark():
    console = {
        "id": "run_unicode",
        "goal": "Verify flow → step ✓ NEEDS_REVIEW",
        "conclusion": "NEEDS_REVIEW",
        "status": "needs_review",
    }
    report = build_qa_report(run_id="run_unicode", console_run=console, repo_root=REPO, journal_dir=JOURNAL)
    html = render_html_report(report, repo_root=REPO)
    assert "→" in html
    assert "✓" in html
    encoded = html.encode("utf-8")
    assert encoded.decode("utf-8") == html


def test_pdf_playwright_or_skip():
    html = "<!DOCTYPE html><html><body><h1>ScoutAI QA Report</h1><p>→ ✓</p></body></html>"
    try:
        pdf = render_pdf_bytes(html, base_url=REPO)
    except RuntimeError as exc:
        pytest.skip(str(exc))
    assert pdf[:4] == b"%PDF"


def test_html_export_bytes_are_valid_utf8():
    report = build_qa_report(
        run_id="run_cli_utf8",
        console_run={
            "id": "run_cli_utf8",
            "goal": "Unicode → ✓ — NEEDS_REVIEW",
            "conclusion": "NEEDS_REVIEW",
            "status": "needs_review",
        },
        repo_root=REPO,
        journal_dir=JOURNAL,
    )
    blob = render_html_report(report, repo_root=REPO).encode("utf-8")
    assert "→".encode("utf-8") in blob
    assert blob.decode("utf-8").count("NEEDS_REVIEW") >= 1
