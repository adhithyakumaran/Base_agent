"""Evidence bundle ZIP export."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

from qa_orchestrator.qa_report.models import QAReport
from qa_orchestrator.qa_report.redaction import path_allowed_in_bundle, redact_dict


def build_evidence_bundle_bytes(
    report: QAReport,
    *,
    html: str,
    repo_root: Path,
    journal_dir: Path,
) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("report.json", json.dumps(redact_dict(report.model_dump()), indent=2))
        zf.writestr("report.html", html)
        state_path = journal_dir / report.run_id / "state.json"
        if state_path.is_file():
            try:
                state_obj = json.loads(state_path.read_text(encoding="utf-8"))
                zf.writestr("run-state.json", json.dumps(redact_dict(state_obj), indent=2))
            except json.JSONDecodeError:
                pass
        journal_path = journal_dir / report.run_id / "journal.json"
        if journal_path.is_file():
            try:
                journal_obj = json.loads(journal_path.read_text(encoding="utf-8"))
                zf.writestr("decision-journal.json", json.dumps(redact_dict(journal_obj), indent=2))
            except json.JSONDecodeError:
                pass
        for ev in report.evidence.screenshots:
            if not path_allowed_in_bundle(ev.path):
                continue
            src = repo_root / ev.path
            if src.is_file():
                zf.write(src, f"screenshots/{src.name}")
        logs_dir = repo_root / "reports" / "live-events"
        log_file = logs_dir / f"{report.run_id}.jsonl"
        if log_file.is_file() and path_allowed_in_bundle(str(log_file)):
            zf.write(log_file, "logs/live-events.jsonl")
    return buf.getvalue()
