# P10.3 — Real Production-Path Validation + Legacy Cleanup Report

## Overall verdict

| Area | Verdict |
|------|---------|
| Legacy `base_agent` CLI test / PYTHONPATH | **PASS** |
| Canonical warm-server HTTP auth | **PASS** (Linux integration) |
| Canonical pipeline (Search SKU dry-run) | **PASS** |
| Restart / resume (simulated new orchestrator) | **PASS** |
| Concurrent runs (dry-run) | **PASS** |
| Failure paths (subset, dry-run) | **PASS** |
| Windows startup documentation | **PASS** (doc + same commands as validated Linux path) |
| Real Windows GUI validation | **NEEDS_REVIEW** (not executed in cloud agent VM) |
| Real Oracle APEX Playwright E2E | **NEEDS_REVIEW** (no client credentials in this environment) |
| LIVE_DEMO visible Chrome on Windows | **NEEDS_REVIEW** (headful Chrome not validated here) |
| Full failure matrix A–H against live APEX | **NEEDS_REVIEW** (requires client `.env`) |

---

## Environment tested

| Item | Value |
|------|--------|
| Host | Linux cloud agent VM (Ubuntu, Python 3.12, Node 20+) |
| Branch | `cursor/p10-3-production-path-validation-00bf` (from P10.2) |
| Repo root | `/workspace` |
| Client Oracle APEX | **Not available** — only `apps/automation/config/environments.example.env` present |

Windows-specific steps are documented in [`docs/WINDOWS_LOCAL_STARTUP.md`](WINDOWS_LOCAL_STARTUP.md) and aligned with [`scripts/start_local_stack.sh`](../scripts/start_local_stack.sh).

---

## Exact commands executed

```bash
# Full unit suite
python3 -m pytest tests/unit -q
# → 353 passed, 4 skipped

# P10.3 focused
python3 -m pytest tests/unit/test_p10_3_warm_server_http.py \
  tests/unit/test_p10_3_canonical_pipeline.py \
  tests/unit/test_p10_3_failure_paths.py \
  tests/unit/test_p61_agent_resume.py::test_agent_cli_subcommand_not_legacy_runtime \
  tests/unit/test_p10_security.py tests/unit/test_p10_2_reliability.py \
  tests/unit/test_live_browser.py -q

# Console
cd apps/console && npm run typecheck && npm run lint && npm run build
```

Warm-server auth tests spawn:

```bash
python3 scripts/local_agent_server.py --host 127.0.0.1 --port <ephemeral>
```

with `SCOUT_ALLOW_INSECURE_LOCAL=false` and `SCOUT_INTERNAL_API_TOKEN=p10-test-internal`.

---

## 1. Legacy runtime cleanup

### Root cause of `test_agent_cli_subcommand_not_legacy_runtime`

The subprocess used `PYTHONPATH=services/qa-orchestrator` only. Canonical CLI loads `QaOrchestrator` → `llm_client` → `base_agent.llm.gateway`. That import is a **library dependency**, not the legacy **product** entrypoint (`python -m base_agent.api` / `AgentRuntime`).

### Fix (not a skip)

- Added [`tests/canonical_subprocess_env.py`](../tests/canonical_subprocess_env.py) mirroring CI:  
  `PYTHONPATH=services/agent-runtime:services/qa-orchestrator:.`
- Updated `test_agent_cli_subcommand_not_legacy_runtime` to use it.

**We did not restore `base_agent` as the runtime.** We fixed the test to assert canonical behavior with the same PYTHONPATH production uses.

### Stale production/runtime references (audit)

| Location | Status |
|----------|--------|
| `infra/deploy/Dockerfile` | **OK** — `local_agent_server.py` |
| `scripts/local_agent_server.py` | **OK** — canonical warm server |
| `infra/ci/azure-pipelines.yml` | **Intentional** — `legacy-runtime-smoke` using `base_agent.api` (labeled) |
| `azure-pipelines.yml` (root) | Same legacy smoke block |
| `scripts/morning_patrol.py` | **Legacy patrol** — still uses `base_agent` (test documents this) |
| `services/qa-orchestrator/qa_orchestrator/llm_client.py` | **Library import** — not entrypoint |
| `tests/unit/test_qa_skills.py`, `tests/conftest.py` | **Skill unit tests** for legacy API |
| `docs/architecture/LOCAL_RUN.md`, `QA_ORCHESTRATOR.md`, `apps/console/README.md` | **Updated** P10.3 — removed `PYTHONPATH=src:.` / `base_agent.api` as primary path |
| `docs/REPO_LAYOUT.md`, `README.md` | **Updated** — agent-runtime described as library, not product kernel |

---

## 2. Real Windows startup validation

**Documentation:** [`docs/WINDOWS_LOCAL_STARTUP.md`](WINDOWS_LOCAL_STARTUP.md) — env vars, two-terminal flow, production-like tokens, LIVE_DEMO flags, Docker note.

**Execution:** Cloud VM ran the equivalent Linux/Git Bash sequence (`start_local_stack.sh` semantics). **NEEDS_REVIEW:** confirm on your Windows machine with `python` and `apps/automation/config/.env`.

---

## 3. Real authentication validation

| Check | Result |
|-------|--------|
| Unauthenticated `POST /run` → rejected | **PASS** (`test_run_rejects_missing_auth`) |
| Valid `Bearer` internal token → accepted | **PASS** (`test_run_accepts_valid_internal_token`) |
| Wrong token → rejected | **PASS** |
| `GET /health` without auth | **PASS** |
| Token absent from JSON body | **PASS** (assertions on response) |
| Console run access / credential masking | **PASS** (existing `test_p10_security.py` static + unit tests) |

Live log scraping for tokens was not performed in this VM; HTTP responses verified clean.

---

## 4. Real Oracle APEX E2E

**NEEDS_REVIEW** — no live APEX URL/password in this environment.

**Proxy validation (dry-run canonical pipeline):**

| Field | Value |
|-------|--------|
| Goal | `Search SKU ABC123 in endless aisle` |
| Flow | `BF-PRODUCT-003` in planning candidates |
| Gate | Execution blocked pending approval when login/search artifacts unapproved |
| Terminal | `WAITING_FOR_APPROVAL` / deterministic non-hanging status |
| LLM | Disabled (`LLM_ENABLED=false`) |

To complete **PASS** on Windows: set credentials, approve `BF-PRODUCT-003` / login as needed, run with `QA_RUNNER=playwright` from console or CLI and attach `run_id`, evidence paths, and Ground Truth conclusion.

---

## 5. LIVE_DEMO validation

| Check | Cloud VM |
|-------|----------|
| Env combo `LIVE_DEMO` + headless false + keep open | **PASS** (`test_live_demo_config_regression`) |
| Visible Chrome, SSE, locator lines, API close | **NEEDS_REVIEW** on Windows workstation |

---

## 6. Failure-path validation

Dry-run tests in `test_p10_3_failure_paths.py`:

| Scenario | Terminal |
|----------|----------|
| Invalid `run_id` resume | **Raises** `AgentResumeError` (deterministic) |
| Unapproved login | **WAITING_FOR_APPROVAL** |
| Search SKU routing | Non-hanging terminal in allowed set |

Live APEX scenarios A–H (invalid locator, disconnect, stale approval, GT missing, bad credentials) → **NEEDS_REVIEW** with real browser and client config.

---

## 7. Restart / resume validation

**PASS** (in-process, simulates server restart):

1. Start run → persist snapshot under `QA_AGENT_JOURNAL_DIR`
2. New `QaOrchestrator` instance (fresh process equivalent)
3. Resume with fixed token → journal length stable on second idempotent resume

**NEEDS_REVIEW:** kill `local_agent_server.py` on Windows mid-run and resume from console (manual checklist in `WINDOWS_LOCAL_STARTUP.md`).

---

## 8. Concurrent real runs

**PASS** — `test_concurrent_dry_runs_isolated` + P10.2 concurrency tests; distinct `state.json` per `run_id`.

---

## 9. Documentation updates

- `docs/WINDOWS_LOCAL_STARTUP.md` (new)
- `docs/architecture/LOCAL_RUN.md`
- `docs/architecture/QA_ORCHESTRATOR.md`
- `apps/console/README.md`
- `README.md`, `docs/REPO_LAYOUT.md`

---

## 10. Test suite results

| Suite | Result |
|-------|--------|
| `pytest tests/unit` | **353 passed**, 4 skipped |
| P10 security + P10.2 + live browser + P10.3 | **Pass** |
| Console typecheck / lint / build | **Pass** |

---

## 11. Files changed (P10.3)

- `tests/canonical_subprocess_env.py` (new)
- `tests/unit/test_p61_agent_resume.py` (PYTHONPATH fix)
- `tests/unit/test_p10_3_warm_server_http.py` (new)
- `tests/unit/test_p10_3_canonical_pipeline.py` (new)
- `tests/unit/test_p10_3_failure_paths.py` (new)
- Docs listed above

---

## Remaining limitations

- No multi-host lock coordination (unchanged from P10.2).
- Legacy `base_agent.api` smoke remains in CI by design.
- `morning_patrol.py` still legacy — out of scope for runtime swap.
- Real Oracle + headful LIVE_DEMO require your Windows client environment to move items from **NEEDS_REVIEW** to **PASS**.

---

## Architecture

Unchanged canonical path:

**Console → BFF → `scripts/local_agent_server.py` → QaOrchestrator → ControlledAgentLoop → AgentExecutor → Playwright → evidence → GroundTruth / Validator**

No PostgreSQL, Redis, Kubernetes, multi-tenancy, Browser Use, or LangGraph migration.
