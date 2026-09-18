# Run resume UX report (executable vs SME-ready)

## Why RUN_4M14 pauses (Search SKU / BF-PRODUCT-003)

Parameterized ad-hoc goals set **`requires_human_approval`** in the planner when execution gates, coverage, or risk require operator sign-off **before Playwright** — even when the flow YAML is already `APPROVED`.

Persisted on disk (`reports/agent/<run_id>/state.json`):

- `state.status`: `WAITING_FOR_APPROVAL`
- `approval_pause_kind`: typically `execution_gate`
- `approval_reason` / `reason_code`: e.g. `approval.pending`
- `resume_token`: used by `POST /agent/{run_id}/resume` (idempotent via `last_applied_resume_token`)

**Continuing the run:** operator **Approve & Resume** in the Runs view → BFF `POST /api/runs/{id}/resume` → warm server `POST /agent/{id}/resume` → `AgentResumeService.resume()` re-validates ExecutionGate and continues the **same** `run_id`.

This is **not** flow artifact approval (`/api/approval`); do not use the SME queue for this pause.

## Dashboard: 19 SME-ready vs 0 executable

**Expected in many UAT checkouts:** `sme_ready` counts flows listed in `data/discovery-kb/flows/index.yaml`. **`executable`** counts flows passing the full gate in `evaluateFlowExecution()`:

- YAML `status: APPROVED`
- In `sme_ready` list
- Listed in automation catalog (`isCatalogAutomated`)
- Approval log not stale vs artifact mtime

Flows can show **Approved** in the UI but still have **`executable: false`** if catalog/KB/stale checks fail. Ad-hoc parameterized runs can also pause for **run-level HITL** while the flow remains approved.

See `apps/console/app/api/orchestrator/route.ts` and `apps/console/lib/approval-store.ts`.
