# P11.4 — Professional QA Reporting + Export

Enterprise QA reports are generated **deterministically** from structured run data. LLM narrative is optional and never authoritative.

## Report architecture

| Layer | Role |
| --- | --- |
| **Sources** | Console run JSON (`apps/console/data/state.json`), agent snapshot `reports/agent/{run_id}/state.json`, evidence under `reports/evidence/{run_id}/`, live-events logs |
| **Canonical model** | `QAReport` in `services/qa-orchestrator/qa_orchestrator/qa_report/models.py` |
| **Schema version** | `report_schema_version = qa-report-v1` |
| **Builder** | `build_qa_report()` merges console + snapshot, redacts parameters, builds timeline, validation, and final result |
| **Summaries** | `summary.py` — executive summary and final explanation from structured fields only |

Sections: Planning, Execution, Evidence, Validation (including NEEDS_REVIEW detail), Approvals, Recovery, Timeline, Final Result.

## Rendering pipeline

```
run JSON + agent state.json
        ↓
   build_qa_report()  →  QAReport (JSON)
        ↓
   render_html_report()  →  HTML (web + PDF source)
        ├─ WeasyPrint → PDF
        ├─ python-docx → DOCX
        └─ bundle.py → ZIP (report.html, report.json, screenshots/, logs/, run-state.json, decision-journal.json)
```

Console BFF spawns:

```bash
python3 -m qa_orchestrator.qa_report_cli --run-id <id> --format <json|html|pdf|docx|bundle> \
  --console-run-json <tmp> --repo-root <repo> --journal-dir reports/agent
```

Optional Python deps: `pip install -e ".[reporting]"` (WeasyPrint, python-docx). WeasyPrint may require system libraries (Pango, Cairo) on the host.

## API endpoints

| Method | Path | Auth |
| --- | --- | --- |
| `GET` | `/api/runs/{id}/report?format=html` | `requireRunAccess` (P10.1) |
| | `format=json\|pdf\|docx\|bundle` | |
| | `download=1` forces attachment (HTML default inline for “View report”) | |

Non-terminal runs return **409** with: `Report available when execution completes.`

Unknown run: **404**. Unauthorized: **401/403** via existing BFF auth.

Legacy `/api/export` (markdown/jspdf) remains for older console flows; run detail **Export Report** uses the canonical endpoint.

## Console UI

Run detail (`LiveRunsView`) includes **Export Report ▾**:

- View report (HTML)
- Download PDF / DOCX / JSON / Evidence Bundle

Disabled while status is `queued`, `running`, `resuming`, or `waiting_approval`.

## Redaction model

`redaction.py`:

- Keys matching `password`, `token`, `secret`, `api_key`, `cookie`, etc. → `[REDACTED]`
- Bundle excludes paths matching `storage-state`, `auth.json`, `.env`, credentials
- `run-state.json` and `decision-journal.json` in ZIP are JSON-redacted before write

## Security model

- Same boundary as P10.1: `requireApiAuth` + `assertRunAccessible(run_id)`
- No second authorization mechanism
- Evidence bundle never includes auth storage or cookies

## Allure integration decision

**Allure is not the business-result authority.** It may be linked later for Playwright technical attachments (screenshots, traces, test-level history). ScoutAI **ExecutionGate**, **Ground Truth**, **Validator**, and **approval model** remain authoritative. The canonical report includes an `allure_note` field documenting this split.

## PDF / DOCX implementation

- **PDF**: Single HTML template (`html.py`) rendered with WeasyPrint (`pdf.py`), A4 `@page`, margins, page numbers via CSS, embedded `file://` screenshots when present on disk.
- **DOCX**: `docx_export.py` builds title, tables, validation, final result, and embeds screenshot files when paths resolve under `repo_root`.

## Reproducibility

- `report_id` is deterministic: `qrpt-{run_id}`
- Factual fields are derived only from run/snapshot inputs
- `generated_at` changes per build; comparisons for tests exclude it

## Tests

`tests/unit/test_p11_4_reporting.py` covers PASS/FAIL/NEEDS_REVIEW/BLOCKED, zero/many evidence, PDF/DOCX (skip if libs missing), ZIP consistency, redaction, reproducibility, and `run_p11_validation` snapshot (BF-PRODUCT-003, SKU `552811DUDABA00`, NEEDS_REVIEW — no invented PASS).

## Real run validation

Use agent snapshot `run_p11_validation` when present in the workspace, or any completed Playwright run with matching structured fields. Reports must reflect actual execution mode, evidence count, Ground Truth state, and validator conclusion — never upgrade NEEDS_REVIEW to PASS.
