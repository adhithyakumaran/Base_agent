# Windows local startup — canonical ScoutAI (P10.3)

Validated against the same entrypoints as Linux/Git Bash; paths use `python` on Windows CMD/PowerShell.

## Prerequisites

- Python 3.10+ (`python --version`)
- Node.js 20+ (`node --version`)
- Git Bash or PowerShell at repo root
- Playwright browsers: `cd apps/automation && npx playwright install chromium`
- Oracle APEX credentials in `apps/automation/config/.env` (copy from `config/environments.example.env`)

## Required environment variables

| Variable | Purpose |
|---|---|
| `PYTHONPATH` | `services\agent-runtime;services\qa-orchestrator;.` (use `;` on Windows CMD) |
| `QA_DISCOVERY_ROOT` | `data\discovery-kb` |
| `QA_AUTOMATION_DIR` | `apps\automation` |
| `QA_RUNNER` | `playwright` (live) or `dry_run` (no browser) |
| `LLM_ENABLED` | `true` or `false` |
| `GROQ_API_KEY` | When LLM enabled |

### P10.1 security (development)

| Variable | Typical dev value |
|---|---|
| `SCOUT_ENV` | `development` |
| `SCOUT_ALLOW_INSECURE_LOCAL` | `true` (loopback only, no tokens) |
| `SCOUT_ALLOWED_ORIGIN` | `http://127.0.0.1:43123` |
| `SCOUT_AGENT_BIND_HOST` | `127.0.0.1` |

### Production-like authenticated local

```bash
SCOUT_ENV=development
SCOUT_ALLOW_INSECURE_LOCAL=false
SCOUT_API_TOKEN=dev-console-token
SCOUT_INTERNAL_API_TOKEN=dev-warm-token
SCOUT_AUTO_BROWSER_SESSION=true
```

Console BFF sends `Authorization: Bearer <SCOUT_API_TOKEN>` to protected routes and `internalAgentHeaders()` to the warm server. Warm server requires `SCOUT_INTERNAL_API_TOKEN` on `/run`, `/chat`, and `/agent/*`. `/health` stays unauthenticated.

## Startup sequence (two terminals)

**Terminal 1 — warm server** (repo root):

```bash
set -a && source .env && set +a   # Git Bash; use `$env:VAR=` in PowerShell
export PYTHONPATH=services/agent-runtime:services/qa-orchestrator:.
export QA_DISCOVERY_ROOT=data/discovery-kb
export QA_AUTOMATION_DIR=apps/automation
export QA_RUNNER=playwright
python scripts/local_agent_server.py --host 127.0.0.1 --port 43124
```

Windows CMD:

```cmd
set PYTHONPATH=services\agent-runtime;services\qa-orchestrator;.
set QA_DISCOVERY_ROOT=data\discovery-kb
set QA_AUTOMATION_DIR=apps\automation
set QA_RUNNER=playwright
python scripts\local_agent_server.py --host 127.0.0.1 --port 43124
```

**Terminal 2 — console**:

```bash
cd apps/console
npm install
set LOCAL_AGENT_URL=http://127.0.0.1:43124
npm run dev
```

Open **http://127.0.0.1:43123**.

Or use `./scripts/start_local_stack.sh` from Git Bash (sets `PYTHONPATH` automatically).

## LIVE_DEMO (visible Chrome)

```bash
export QA_RUN_MODE=LIVE_DEMO
export QA_LIVE_BROWSER=true
export QA_BROWSER_HEADLESS=false
export QA_KEEP_BROWSER_OPEN=true
```

Then start the warm server and run a LIVE_DEMO goal from the console. Profile directory is run-scoped under `reports/agent/<run_id>/live-browser/`.

## Canonical runtime (not legacy)

| Use | Entry |
|---|---|
| **Production / console** | `scripts/local_agent_server.py` |
| **Agent CLI** | `python -m qa_orchestrator.agent_cli run "<goal>"` |
| **Legacy skills smoke only** | `python -m base_agent.api` (CI label `legacy-runtime-smoke`, not product path) |

`services/agent-runtime/base_agent` is a **library** (LLM gateway, skill tests). It is **not** the ScoutAI product runtime (`AgentRuntime` / `base_agent.api`).

## Docker

Production image entrypoint: `python scripts/local_agent_server.py` — see `infra/deploy/Dockerfile`.
