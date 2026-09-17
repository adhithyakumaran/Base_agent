# P11.6 — LIVE_DEMO browser lifecycle + report export fixes

## Root cause: multiple Chrome windows

| Question | Finding |
| --- | --- |
| Browser launches | One `launchPersistentContext` **per Playwright worker**; with `workers: 1` and shared registry, **one context per LIVE_DEMO run** |
| Contexts / pages | One persistent context; tests reuse `liveContext.pages()[0]` |
| `launchLiveContext` frequency | Once per worker when shared context absent; **reused** via `live-browser-shared.ts` |
| Repeated login | **Bug:** `page` fixture ran `performLogin` on **every test** when `EA_SKIP_GLOBAL_SETUP=true` |
| `EA_SKIP_GLOBAL_SETUP` | Set by orchestrator for LIVE runs so global-setup does not write `.auth/user.json`; login moved to **run-scoped** `ensureRunScopedLogin()` once per worker |
| Teardown 120s | **Bug:** `await watchCloseSignalWhileOpen()` in `liveContext` fixture teardown blocked until Playwright’s **120s fixture timeout** |

## Fix (LIVE_DEMO only)

- **Single session:** worker-scoped `liveContext` + shared context registry keyed by `QA_LIVE_PROFILE_DIR`
- **Login once:** `ensureRunScopedLogin()` after context launch; removed per-test login in `page` fixture
- **Keep browser open:** `QA_KEEP_BROWSER_OPEN=true` unchanged — teardown **does not** close context and **does not** await infinite watch loop
- **Explicit close:** detached `scripts/live-browser-keeper.mjs` polls `close.signal` and closes via Chrome `DevToolsActivePort` + CDP
- **CI unchanged:** standard fixtures when `QA_LIVE_BROWSER` is not `true`; global setup unchanged when `EA_SKIP_GLOBAL_SETUP` is unset

## Execution vs business validation

- `classify_playwright_output()` in `playwright_runner.py` sets `execution_status` (e.g. `PASS_WITH_WARNING`) when tests pass but teardown emits infrastructure errors
- `QAReport.business_validation_status` remains validator conclusion (`NEEDS_REVIEW`, etc.)
- `QAReport.execution.execution_status` and `infrastructure_warnings[]` surface Playwright/infra separately

## PDF renderer decision

| Primary | Playwright Chromium `page.pdf()` via `apps/automation/scripts/render-report-pdf.mjs` |
| Alternate | WeasyPrint if Playwright fails and native libs available |
| Windows | No GTK/Pango requirement for default path |

## HTML UTF-8

- `qa_report_cli` writes **UTF-8 bytes** for `json` and `html` formats (`ensure_ascii=False`, `.encode("utf-8")`)

## Tests

- `tests/unit/test_p11_6_live_browser_exports.py`
- `apps/automation/tests/unit/live-browser-lifecycle.spec.ts`
- Existing P11.4 export tests remain valid

## Before / after

| Before | After |
| --- | --- |
| Teardown awaits close watch → 120s fixture timeout | Teardown returns immediately; keeper handles close signal |
| Login on each test in LIVE_DEMO | One authenticated session per run (worker) |
| PDF default WeasyPrint (GTK on Windows) | PDF default Playwright Chromium |
| HTML Unicode fails on Windows cp1252 | UTF-8 explicit on CLI/API path |
