# P10.2 — Runtime & State Reliability Report

## Files changed (implementation)

| Area | Files |
|------|--------|
| Atomic FS + locks (Python) | `services/qa-orchestrator/qa_orchestrator/fs_atomic.py` |
| Agent state | `services/qa-orchestrator/qa_orchestrator/agent_state_store.py` |
| Approval log (Python) | `services/qa-orchestrator/qa_orchestrator/approval_log.py`, `bootstrap_approval.py` |
| Healing overlays | `services/qa-orchestrator/qa_orchestrator/healing_overlay.py` |
| Resume idempotency | `services/qa-orchestrator/qa_orchestrator/agent_resume.py` |
| Live browser close meta | `services/qa-orchestrator/qa_orchestrator/live_browser_close.py` |
| Playwright session | `services/qa-orchestrator/qa_orchestrator/playwright_runner.py` |
| Warm server logging | `scripts/local_agent_server.py` |
| Console atomic FS | `apps/console/lib/fs-atomic.ts` |
| Console run state | `apps/console/lib/store.ts` |
| Console approvals | `apps/console/lib/approval-store.ts` |
| SSE stream | `apps/console/app/api/runs/[id]/stream/route.ts` |
| Live browser lifecycle | `apps/automation/src/core/live-browser-lifecycle.ts` |
| Tests | `tests/unit/test_p10_2_reliability.py` |

## Concurrency risks found

1. **Run state (`state.json`)** — read-modify-write without locking could lose updates when console BFF and warm server both write, or when resume overlaps with loop persistence.
2. **Approval log** — append + artifact YAML transition were non-atomic; parallel approve/reject could interleave JSONL lines or corrupt artifact status.
3. **Healing overlays** — last-write-wins on full JSON store under concurrent approvals.
4. **Live events** — sequence already file-locked in Python `LiveEventStore`; verified under multi-thread stress (TS path unchanged, uses existing lock in `live-event-sequence.ts`).
5. **Live browser session meta** — partial writes visible to close-signal poller.

## Lifecycle risks found

1. **Browser context closed** without explicit user close — run could hang; now emits `BROWSER_DISCONNECTED` and closes signal.
2. **Repeated close** — idempotent close meta + signal file already present; reinforced with atomic writes.
3. **SSE** — missing event file or client disconnect could spin; stream now checks `req.signal.aborted`, terminal browser states, and file size before full re-read.

## Guarantees now provided

- Per-run **file locks** (`run_file_lock`) for agent snapshots and named locks for overlays.
- **Temp + atomic replace** for critical JSON/YAML/text runtime files (Python + Node).
- **Locked append** for approval audit log (console + bootstrap script).
- **Idempotent resume** token check inside `mutate_snapshot` lock.
- **Monotonic live-event sequence** under concurrent Python producers (stress test).
- **Isolated run directories** under concurrent run creation (regression test).
- **P10.1 auth** preserved on SSE (`requireRunAccess`); structured `security_log` on run accept includes `run_id`.

## Tests executed / results

| Suite | Result |
|-------|--------|
| `pytest tests/unit/test_p10_2_reliability.py tests/unit/test_p10_security.py tests/unit/test_live_browser.py` | **41 passed** |
| `pytest tests/unit` | **342 passed**, 4 skipped, **1 failed** (`test_p61_agent_resume::test_agent_cli_subcommand_not_legacy_runtime` — pre-existing `ModuleNotFoundError: base_agent` in subprocess; unchanged by P10.2) |
| `npm run typecheck` (console) | pass |
| `npm run lint` (console) | pass |
| `npm run build` (console) | pass |

## Remaining limitations

- Locking is **process-local** (`fcntl` / sync file lock); multi-host replicas still require single writer or external coordination (out of scope: no Redis).
- **Restart/resume** after killing `local_agent_server.py` relies on existing snapshot + resume token semantics; no new daemon supervisor.
- SSE still polls filesystem every 500ms (by design); only avoids redundant full reads when file size unchanged.
- Subprocess **P6.1 legacy CLI test** failure remains until `base_agent` package layout is fixed in CI.

## Architecture

Unchanged: Next.js console → BFF → `scripts/local_agent_server.py` → QaOrchestrator → ControlledAgentLoop → AgentExecutor → Playwright → evidence. No PostgreSQL, Redis, K8s, Browser Use, or LangGraph.
