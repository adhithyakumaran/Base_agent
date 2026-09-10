# ScoutAI — Enterprise QA Agent

Deterministic-first agent runtime + **ScoutAI** orchestrator for Oracle APEX Endless Aisle UAT.

> **Repo layout v2:** See [docs/REPO_LAYOUT.md](docs/REPO_LAYOUT.md) for the enterprise folder structure.

## Quick start (local)

**Python 3.10+** and **Node 20+** required. On Windows use `python` not `python3`.

```bash
# One command — backend + ScoutAI console
./scripts/start_local_stack.sh
```

Open **http://127.0.0.1:43123**

### Two terminals (Windows Git Bash)

**Terminal 1 — backend** (repo root `baseagentmain/`):

```bash
cd ~/Downloads/baseagentmain
set -a && source .env && set +a
export PYTHONPATH=services/agent-runtime:services/qa-orchestrator:.
export QA_DISCOVERY_ROOT=data/discovery-kb
export QA_AUTOMATION_DIR=apps/automation
export QA_RUNNER=playwright
python scripts/local_agent_server.py --port 43124
```

**Terminal 2 — frontend** (`apps/console/`):

```bash
cd ~/Downloads/baseagentmain/apps/console
npm install
export LOCAL_AGENT_URL=http://127.0.0.1:43124
npm run dev
```

### Playwright sanity (19 flows)

```bash
cd apps/automation
npm run test:sanity
npm run test:regression    # full regression
npm run test:negative      # negative / edge cases
```

Credentials: `apps/automation/config/.env`

## Enterprise repo map

| Path | Purpose |
|---|---|
| `apps/console/` | ScoutAI Next.js UI |
| `apps/automation/` | Playwright tests + scenarios/cases/suites |
| `services/agent-runtime/` | Base Agent kernel |
| `services/qa-orchestrator/` | LLM classify → suite select → run → report |
| `data/discovery-kb/` | Flow KB YAML, recordings, crawl snapshots |
| `plugins/qa_apex/` | Crawler + APEX skills |
| `docs/` | Architecture & proposals |
| `infra/` | Deploy + CI |

## Scenarios location

```text
apps/automation/test-design/flows/{BF-*}/scenarios.yaml
apps/automation/test-design/flows/{BF-*}/test-cases.yaml
data/discovery-kb/flows/{BF-*}.yaml          ← KB source
```

## Orchestrator modes (NL → suites)

| Ask | Mode | Runs |
|---|---|---|
| "morning sanity" | `morning_sanity` | All 19 @sanity suites |
| "sanity for login" | `adhoc_existing` | BF-LOGIN-001 suite |
| "full regression" | `regression_suite` | All @regression |
| "negative login test" | `negative_suite` | @negative tagged tests |
| "test payment flow" | `incident_multi_flow` | Billing + related flows (synonym map) |

|---|---|
| `src/qa_orchestrator/` | **Phase 1 product** — intent classify + suite select + Playwright + KB graph |
| `plugins/mock_demo/` | Deterministic mock tools |
| `plugins/qa_apex/` | APEX discover / sanity / flow catalog + Playwright crawler |
## Canonical Application KB (Sep 2026)

Flow-centric YAML lives in `discovery/uat_ea/flows/`. See `discovery/uat_ea/KB_FORMAT.md` and [KB_REFORMAT_REPORT.md](finalized-proposal/KB_REFORMAT_REPORT.md).

| Path | Purpose |
|---|---|
| `discovery/uat_ea/flows/` | **Canonical** flow KB (YAML) |
| `discovery/uat_ea/kb/` | Legacy JSON archive |
| `docs/finalized-proposal/` | **LOCKED** AI QA automation proposal + architecture + KB readiness |
| `docs/APEX_GT_KB_COLLECTION_SPEC.md` | KB/GT schemas |
| `docs/architecture/OPERATING_WITHOUT_GT.md` | How we run before SME GT |
| `docs/architecture/APEX_APPLICATION_FLOWS.md` | APEX flow patterns for the QA agent |
| `docs/architecture/APEX_CRAWLER_PERFORMANCE.md` | Crawler anti-stuck / performance |
| `docs/architecture/AZURE_OCI_DEPLOYMENT.md` | Azure Pipelines → OCI |
| `azure-pipelines.yml` | CI test + image package stages |
| `deploy/Dockerfile` | OCI-ready runtime image |

## Without Ground Truth — what works now

| Capability | Status |
|---|---|
| KB map of Endless Aisle pages/flows/components | Yes |
| Platform APEX flow patterns (auth, LOV, modal, IG) | Yes |
| Technical FAIL (ORA, session dead, modal hang, auth blockers) | Yes |
| Live bounded crawl when credentials provided | Yes |
| Business PASS/FAIL (order totals, required modules) | Needs SME-approved GT |
| Honest stop (`UNKNOWN` / `INSUFFICIENT_EVIDENCE`) | Always — **no loop-until-success** |

SME GT later only increases deterministic PASS/FAIL coverage — it does not redesign the agent.

## UAT discovery artifacts

- [discovery/uat_ea/APPROVAL_CHECKLIST.md](discovery/uat_ea/APPROVAL_CHECKLIST.md)
- [discovery/uat_ea/kb/](discovery/uat_ea/kb/) (includes `pattern.apex.*` flow patterns)
- [discovery/uat_ea/kb_normalized/](discovery/uat_ea/kb_normalized/)

## Status

**Phase closed for now** — [docs/PHASE_COMPLETE.md](docs/PHASE_COMPLETE.md). Continue later (live UAT depth + SME GT).

Folder layout follows Base Agent proposal §23 (`src/base_agent/` + top-level `plugins/`).

```bash
PYTHONPATH=src:. python3 scripts/local_agent_server.py --port 43124
cd qa-console && LOCAL_AGENT_URL=http://127.0.0.1:43124 npm run dev
```

LLM: **off** by default. Test report routes: `adhithyakumaran2005@gmail.com` · `+919965985951`.
