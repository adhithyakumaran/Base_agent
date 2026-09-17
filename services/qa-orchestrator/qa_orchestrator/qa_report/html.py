"""Render canonical HTML report (ScoutAI design tokens)."""

from __future__ import annotations

import html
from pathlib import Path

from qa_orchestrator.qa_report.models import QAReport


def _esc(value: str | None) -> str:
    return html.escape(str(value or ""), quote=True)


def _status_class(conclusion: str) -> str:
    c = conclusion.upper()
    if c == "PASS":
        return "status-pass"
    if c == "FAIL":
        return "status-fail"
    if c == "NEEDS_REVIEW":
        return "status-pending"
    if c == "BLOCKED":
        return "status-blocked"
    return "status-running"


def _image_src(path: str, repo_root: Path) -> str:
    abs_path = (repo_root / path).resolve()
    if abs_path.is_file():
        return abs_path.as_uri()
    return ""


def render_html_report(report: QAReport, *, repo_root: Path | None = None) -> str:
    repo_root = repo_root or Path(".")
    flows = ", ".join(report.flow_ids) or "—"
    badge = _status_class(report.overall_result)
    evidence_rows = ""
    for ev in report.evidence.screenshots:
        src = _image_src(ev.path, repo_root)
        img = f'<img src="{_esc(src)}" alt="{_esc(ev.description)}" class="evidence-img" />' if src else ""
        evidence_rows += f"""
        <article class="evidence-card">
          <header><strong>{_esc(ev.evidence_id)}</strong> · {_esc(ev.action)}</header>
          <p>{_esc(ev.description)}</p>
          <p class="muted">{_esc(ev.path)}</p>
          {img}
        </article>"""

    timeline_rows = "".join(
        f"<tr><td>{_esc(t.timestamp)}</td><td>{_esc(t.stage)}</td><td>{_esc(t.action)}</td><td>{_esc(t.result)}</td></tr>"
        for t in report.timeline[:40]
    )

    needs_review = ""
    if report.overall_result == "NEEDS_REVIEW" and report.validation.needs_review_detail:
        d = report.validation.needs_review_detail
        needs_review = f"""
        <div class="callout">
          <p><strong>Reason:</strong> {_esc(d.get('reason'))}</p>
          <p><strong>Failed check:</strong> {_esc(d.get('failed_check'))}</p>
          <p><strong>Expected:</strong> {_esc(d.get('expected'))}</p>
          <p><strong>Actual:</strong> {_esc(d.get('actual'))}</p>
          <p><strong>What prevented PASS:</strong> {_esc(d.get('what_prevented_pass'))}</p>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>ScoutAI QA Report — {_esc(report.run_id)}</title>
  <style>
    @page {{ size: A4; margin: 18mm 16mm 20mm 16mm;
      @bottom-center {{ content: "Page " counter(page) " of " counter(pages); font-size: 9pt; color: #64748b; }}
    }}
    body {{ font-family: Inter, system-ui, sans-serif; color: #0f172a; background: #f8fafc; margin: 0; }}
    .page {{ max-width: 920px; margin: 0 auto; background: #fff; padding: 32px; }}
    h1,h2,h3 {{ color: #0f172a; }}
    .cover {{ border-bottom: 2px solid #0f766e; padding-bottom: 24px; margin-bottom: 24px; }}
    .badge {{ display: inline-block; padding: 4px 12px; border-radius: 999px; font-weight: 600; font-size: 12px; }}
    .status-pass {{ background: #ecfdf5; color: #059669; }}
    .status-fail {{ background: #fef2f2; color: #dc2626; }}
    .status-pending {{ background: #fffbeb; color: #d97706; }}
    .status-blocked {{ background: #f1f5f9; color: #64748b; }}
    .status-running {{ background: #e0f2fe; color: #0284c7; }}
    .muted {{ color: #64748b; font-size: 13px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f1f5f9; }}
    .evidence-card {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin: 12px 0; }}
    .evidence-img {{ max-width: 100%; max-height: 280px; border: 1px solid #cbd5e1; border-radius: 4px; }}
    .callout {{ background: #fffbeb; border-left: 4px solid #d97706; padding: 12px 16px; margin: 12px 0; }}
    footer {{ margin-top: 32px; font-size: 11px; color: #64748b; }}
  </style>
</head>
<body>
  <div class="page">
    <section class="cover">
      <p class="muted">ScoutAI · Enterprise QA Execution Report</p>
      <h1>{_esc(report.goal)}</h1>
      <p><strong>Flow:</strong> {_esc(flows)}</p>
      <p><strong>Run:</strong> {_esc(report.run_id)}</p>
      <p><strong>Environment:</strong> {_esc(report.environment)}</p>
      <p><strong>Execution:</strong> {_esc(report.execution.runner)} / {_esc(report.execution_mode)}</p>
      <p><span class="badge {badge}">{_esc(report.overall_result)}</span></p>
      <p class="muted">Generated: {_esc(report.generated_at)} · Schema: {_esc(report.report_schema_version)}</p>
    </section>

    <section>
      <h2>Executive summary</h2>
      <p>{_esc(report.executive_summary)}</p>
    </section>

    <section>
      <h2>Test details</h2>
      <table>
        <tr><th>Goal</th><td>{_esc(report.goal)}</td></tr>
        <tr><th>Flow IDs</th><td>{_esc(flows)}</td></tr>
        <tr><th>Parameters</th><td>{_esc(str(report.input_parameters))}</td></tr>
        <tr><th>Environment</th><td>{_esc(report.environment)}</td></tr>
        <tr><th>Execution mode</th><td>{_esc(report.execution_mode)}</td></tr>
        <tr><th>Runner</th><td>{_esc(report.runner)}</td></tr>
        <tr><th>Duration</th><td>{_esc(str(report.duration_ms or report.execution.elapsed_ms))} ms</td></tr>
      </table>
    </section>

    <section>
      <h2>Execution summary</h2>
      <table>
        <tr><th>Command</th><td><code>{_esc(report.execution.command)}</code></td></tr>
        <tr><th>Result mode</th><td>{_esc(report.execution.execution_result)}</td></tr>
        <tr><th>Exit code</th><td>{_esc(str(report.execution.exit_code))}</td></tr>
        <tr><th>Evidence count</th><td>{len(report.evidence.screenshots)}</td></tr>
        <tr><th>Errors</th><td>{_esc("; ".join(report.execution.errors))}</td></tr>
      </table>
    </section>

    <section>
      <h2>Step-by-step timeline</h2>
      <table>
        <thead><tr><th>Timestamp</th><th>Stage</th><th>Action</th><th>Result</th></tr></thead>
        <tbody>{timeline_rows or "<tr><td colspan=4>No timeline entries</td></tr>"}</tbody>
      </table>
    </section>

    <section>
      <h2>Evidence</h2>
      {evidence_rows or "<p>No evidence captures recorded.</p>"}
    </section>

    <section>
      <h2>Validation</h2>
      <p><strong>Phase:</strong> {_esc(report.validation.phase)} · <strong>Result:</strong> {_esc(report.validation.validation_result)}</p>
      <p><strong>Reason code:</strong> {_esc(report.validation.reason_code)}</p>
      <p><strong>Failed checks:</strong> {_esc(", ".join(report.validation.failed_checks))}</p>
      {needs_review}
    </section>

    <section>
      <h2>Final result</h2>
      <p class="badge {badge}">{_esc(report.final_result.conclusion if report.final_result else report.overall_result)}</p>
      <p>{_esc(report.final_result.explanation if report.final_result else "")}</p>
    </section>

    <footer>
      <p>{_esc(report.allure_note)}</p>
      <p>Report ID: {_esc(report.report_id)} · Deterministic structured report (authoritative).</p>
    </footer>
  </div>
</body>
</html>"""
