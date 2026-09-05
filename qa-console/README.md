# Apex QA Agent Console

Enterprise light-theme UI for the QA orchestrator.

## Run locally

```bash
# From repo root (starts orchestrator + this console)
./scripts/start_local_stack.sh
```

Or:

```bash
# Terminal 1 — agent API (requires .env with GROQ_API_KEY)
cd .. && set -a && source .env && set +a
PYTHONPATH=src:. python3 scripts/local_agent_server.py --port 43124

# Terminal 2 — console
npm install
npm run dev
```

Open **http://127.0.0.1:43123**

## Features

- Natural language prompt → Groq intent classification → Playwright suite execution
- **Generate sanity report** — all 19 READY flows
- **Agent output panel** — intent, suites, discovery/LLM insights, live trace
- **Export** combined report as MD, PDF, or DOCX

## Theme

Light background, orange primary buttons (`#EA580C`), black text, Inter sans-serif.

## Environment

| Variable | Default |
|---|---|
| `LOCAL_AGENT_URL` | `http://127.0.0.1:43124` |
| `GROQ_API_KEY` | Set in repo root `.env` (never commit) |

Playwright automation credentials: `automation/config/.env` (copy from `environments.example.env`).
