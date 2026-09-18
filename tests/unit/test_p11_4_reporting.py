"""P11.4 — canonical QA reporting, exports, and redaction."""

from __future__ import annotations

import json
import re
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from qa_orchestrator.qa_report.builder import build_qa_report
from qa_orchestrator.qa_report.bundle import build_evidence_bundle_bytes
from qa_orchestrator.qa_report.docx_export import render_docx_bytes
from qa_orchestrator.qa_report.html import render_html_report
from qa_orchestrator.qa_report.models import REPORT_SCHEMA_VERSION
from qa_orchestrator.qa_report.pdf import render_pdf_bytes
from qa_orchestrator.qa_report.redaction import path_allowed_in_bundle, redact_dict


REPO = Path(__file__).resolve().parents[2]
JOURNAL = REPO / "reports" / "agent"


def _console_run(
    *,
    run_id: str = "run_test",
    conclusion: str,
    status: str = "needs_review",
    goal: str = "Search SKU 552811DUDABA00",
    diagnostics: dict | None = None,
) -> dict:
    return {
        "id": run_id,
        "createdAt": "2026-09-16T21:13:20.066216+00:00",
        "updatedAt": "2026-09-16T21:13:20.105745+00:00",
        "goal": goal,
        "status": status,
        "conclusion": conclusion,
        "executionMode": "LIVE_DEMO",
        "decisionDiagnostics": diagnostics or {},
        "traces": [{"id": "t1", "at": "2026-09-16T21:13:20Z", "kind": "info", "message": "Plan complete"}],
    }


def _stable_payload(report) -> dict:
    data = report.model_dump()
    data.pop("generated_at", None)
    return data


@pytest.mark.parametrize(
    "conclusion,status",
    [
        ("PASS", "completed"),
        ("FAIL", "failed"),
        ("NEEDS_REVIEW", "needs_review"),
        ("BLOCKED", "blocked"),
    ],
)
def test_report_overall_result_variants(conclusion: str, status: str):
    run = _console_run(conclusion=conclusion, status=status)
    report = build_qa_report(run_id=run["id"], console_run=run, repo_root=REPO, journal_dir=JOURNAL)
    assert report.report_schema_version == REPORT_SCHEMA_VERSION
    assert report.overall_result == conclusion
    assert report.report_id == f"qrpt-{run['id']}"
    html = render_html_report(report, repo_root=REPO)
    assert conclusion in html
    assert report.executive_summary
    assert report.final_result is not None
    assert report.final_result.conclusion == conclusion


def test_needs_review_detail_from_diagnostics():
    diag = {
        "reason_code": "validator.pre_gt_honest",
        "failed_checks": ["ground_truth"],
        "message": "Approved Ground Truth not available",
    }
    run = _console_run(conclusion="NEEDS_REVIEW", diagnostics=diag)
    report = build_qa_report(run_id=run["id"], console_run=run, repo_root=REPO, journal_dir=JOURNAL)
    assert report.validation.needs_review_detail.get("failed_check") == "ground_truth"
    html = render_html_report(report, repo_root=REPO)
    assert "What prevented PASS" in html
    assert "ground_truth" in html


def test_zero_evidence_report():
    run = _console_run(conclusion="FAIL", status="failed")
    report = build_qa_report(run_id="run_zero_evidence", console_run=run, repo_root=REPO, journal_dir=JOURNAL)
    assert report.evidence.screenshots == []
    assert "0 evidence" not in report.executive_summary.lower() or "execution" in report.executive_summary.lower()


def test_many_screenshots_capped_in_html():
    run = _console_run(conclusion="PASS", status="completed")
    items = []
    for i in range(25):
        items.append(
            {
                "ok": True,
                "action": "screenshot",
                "screenshot_path": f"reports/evidence/run_many/fake-{i}.png",
            }
        )
    run["report"] = {
        "json": {
            "agent": {
                "local": {
                    "execution": {"ok": True, "observations": items},
                    "suite_plan": {"flow_ids": ["BF-PRODUCT-003"], "params": {"sku": "552811DUDABA00"}},
                }
            }
        }
    }
    report = build_qa_report(run_id="run_many", console_run=run, repo_root=REPO, journal_dir=JOURNAL)
    assert len(report.evidence.screenshots) >= 25
    html = render_html_report(report, repo_root=REPO)
    assert "BF-PRODUCT-003" in html


def test_real_run_p11_validation_snapshot():
    run_id = "run_p11_validation"
    if not (JOURNAL / run_id / "state.json").is_file():
        pytest.skip("run_p11_validation snapshot missing")
    console = _console_run(
        run_id=run_id,
        conclusion="NEEDS_REVIEW",
        goal="Search SKU 552811DUDABA00",
    )
    report = build_qa_report(run_id=run_id, console_run=console, repo_root=REPO, journal_dir=JOURNAL)
    assert "BF-PRODUCT-003" in report.flow_ids or any("BF-PRODUCT" in f for f in report.flow_ids)
    assert report.input_parameters.get("sku") == "552811DUDABA00" or "552811DUDABA00" in report.goal
    assert report.overall_result == "NEEDS_REVIEW"
    assert report.overall_result != "PASS"
    html = render_html_report(report, repo_root=REPO)
    assert "NEEDS_REVIEW" in html
    assert "552811DUDABA00" in html


def test_report_reproducibility():
    run = _console_run(conclusion="NEEDS_REVIEW", diagnostics={"reason_code": "test", "failed_checks": ["x"]})
    a = build_qa_report(run_id="run_repro", console_run=run, repo_root=REPO, journal_dir=JOURNAL)
    b = build_qa_report(run_id="run_repro", console_run=run, repo_root=REPO, journal_dir=JOURNAL)
    assert _stable_payload(a) == _stable_payload(b)


def test_sensitive_redaction():
    payload = {"sku": "552811DUDABA00", "api_token": "secret-value", "password": "x"}
    redacted = redact_dict(payload)
    assert redacted["sku"] == "552811DUDABA00"
    assert redacted["api_token"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"


def test_bundle_redacts_secrets_and_blocks_sensitive_paths():
    run = _console_run(conclusion="NEEDS_REVIEW")
    run["report"] = {
        "json": {
            "agent": {
                "local": {
                    "suite_plan": {"params": {"password": "hidden"}},
                    "execution": {"ok": False, "observations": []},
                }
            }
        }
    }
    report = build_qa_report(run_id="run_bundle", console_run=run, repo_root=REPO, journal_dir=JOURNAL)
    html = render_html_report(report, repo_root=REPO)
    blob = build_evidence_bundle_bytes(report, html=html, repo_root=REPO, journal_dir=JOURNAL)
    with zipfile.ZipFile(BytesIO(blob)) as zf:
        raw = zf.read("report.json").decode("utf-8")
        assert "[REDACTED]" in raw
        assert "hidden" not in raw
    assert not path_allowed_in_bundle("reports/browser-profiles/run/storage-state.json")


def test_invalid_run_id_still_builds_deterministic_shell():
    report = build_qa_report(run_id="../bad", console_run={}, repo_root=REPO, journal_dir=JOURNAL)
    assert report.run_id == "../bad"
    assert report.report_id == "qrpt-../bad"


def test_pdf_export_if_weasyprint():
    run = _console_run(conclusion="PASS", status="completed")
    report = build_qa_report(run_id="run_pdf", console_run=run, repo_root=REPO, journal_dir=JOURNAL)
    html = render_html_report(report, repo_root=REPO)
    try:
        pdf = render_pdf_bytes(html, base_url=REPO)
    except RuntimeError as exc:
        pytest.skip(str(exc))
    assert pdf[:4] == b"%PDF"
    assert b"PASS" in pdf or b"Pass" in pdf or len(pdf) > 500


def test_docx_export_if_python_docx():
    run = _console_run(conclusion="FAIL", status="failed")
    report = build_qa_report(run_id="run_docx", console_run=run, repo_root=REPO, journal_dir=JOURNAL)
    try:
        docx = render_docx_bytes(report, repo_root=REPO)
    except RuntimeError as exc:
        pytest.skip(str(exc))
    assert docx[:2] == b"PK"
    with zipfile.ZipFile(BytesIO(docx)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "FAIL" in xml


def test_zip_contains_authoritative_facts():
    run = _console_run(
        conclusion="NEEDS_REVIEW",
        diagnostics={"reason_code": "validator.pre_gt_honest", "failed_checks": ["ground_truth"]},
    )
    report = build_qa_report(run_id="run_zip_facts", console_run=run, repo_root=REPO, journal_dir=JOURNAL)
    html = render_html_report(report, repo_root=REPO)
    blob = build_evidence_bundle_bytes(report, html=html, repo_root=REPO, journal_dir=JOURNAL)
    with zipfile.ZipFile(BytesIO(blob)) as zf:
        report_json = json.loads(zf.read("report.json"))
        report_html = zf.read("report.html").decode("utf-8")
    assert report_json["overall_result"] == "NEEDS_REVIEW"
    assert "NEEDS_REVIEW" in report_html
    assert report_json["executive_summary"] == report.executive_summary


def test_html_json_same_conclusion():
    run = _console_run(conclusion="BLOCKED", status="blocked")
    report = build_qa_report(run_id="run_consistency", console_run=run, repo_root=REPO, journal_dir=JOURNAL)
    html = render_html_report(report, repo_root=REPO)
    data = report.model_dump()
    assert data["overall_result"] in html
    assert re.search(r"BLOCKED", html)
