# Local-first run (canonical ScoutAI)

## Canonical stack

```text
Console (apps/console) → BFF → scripts/local_agent_server.py → QaOrchestrator → ControlledAgentLoop → Playwright
```

Legacy `python -m base_agent.api` remains for **CI skill smoke only**, not console or production Docker.

## LLM

**Default in docs:** set `LLM_ENABLED=false` for deterministic runs. Enable Groq via `.env` when classifying NL intents.

## Efficient local run

**Option A — one script (Git Bash / Linux):**

```bash
./scripts/start_local_stack.sh
```

**Option B — two terminals** (see [WINDOWS_LOCAL_STARTUP.md](../WINDOWS_LOCAL_STARTUP.md)):

Terminal 1:

```bash
cd /path/to/repo
set -a && source .env && set +a
export PYTHONPATH=services/agent-runtime:services/qa-orchestrator:.
python scripts/local_agent_server.py --host 127.0.0.1 --port 43124
```

Terminal 2:

```bash
cd apps/console
LOCAL_AGENT_URL=http://127.0.0.1:43124 npm run dev
```

## CLI (canonical agent)

```bash
export PYTHONPATH=services/agent-runtime:services/qa-orchestrator:.
QA_RUNNER=dry_run LLM_ENABLED=false python -m qa_orchestrator.agent_cli --json run "Check login"
```

Warm server avoids cold Python spawn on every console action.
