"""CLI for QA report export (used by console BFF)."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

from qa_orchestrator.qa_report.builder import build_qa_report
from qa_orchestrator.qa_report.bundle import build_evidence_bundle_bytes
from qa_orchestrator.qa_report.docx_export import render_docx_bytes
from qa_orchestrator.qa_report.html import render_html_report
from qa_orchestrator.qa_report.pdf import render_pdf_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description="Export canonical QA report")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--format", required=True, choices=["json", "html", "pdf", "docx", "bundle"])
    parser.add_argument("--console-run-json", help="Path to console run JSON")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--journal-dir", default="reports/agent")
    parser.add_argument("--environment", default=None)
    args = parser.parse_args()

    console_run: dict = {}
    if args.console_run_json:
        console_run = json.loads(Path(args.console_run_json).read_text(encoding="utf-8"))

    repo_root = Path(args.repo_root)
    report = build_qa_report(
        run_id=args.run_id,
        console_run=console_run,
        journal_dir=args.journal_dir,
        repo_root=repo_root,
        environment=args.environment,
    )
    html = render_html_report(report, repo_root=repo_root)

    if args.format == "json":
        sys.stdout.write(json.dumps(report.model_dump(), indent=2))
        return
    if args.format == "html":
        sys.stdout.write(html)
        return
    if args.format == "pdf":
        pdf = render_pdf_bytes(html, base_url=repo_root)
        sys.stdout.buffer.write(pdf)
        return
    if args.format == "docx":
        docx = render_docx_bytes(report, repo_root=repo_root)
        sys.stdout.buffer.write(docx)
        return
    if args.format == "bundle":
        blob = build_evidence_bundle_bytes(
            report,
            html=html,
            repo_root=repo_root,
            journal_dir=Path(args.journal_dir),
        )
        sys.stdout.buffer.write(blob)


if __name__ == "__main__":
    main()
