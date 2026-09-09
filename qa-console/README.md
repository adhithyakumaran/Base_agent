# ScoutAI · Enterprise QA Console

Dark emerald enterprise UI for the ScoutAI QA orchestrator.

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

- **ScoutAI** branding with emerald dark theme + animated background
- Natural language prompt → high-clarity intent classification → Playwright suite execution
- **Run 19 sanity suites** — all READY flows with screenshot/DOM evidence on clicks
- **Browser Recorder** panel — capture console, network, interactions, DOM snapshots for KB discovery
- **Report channels** — save email & WhatsApp test inboxes; scheduled sanity delivery
- **Delivery inbox** — view queued/sent report deliveries
- **Automation suggestions** when new features are detected
- Export combined report as MD, PDF, or DOCX (Inter typography)

## Theme

Dark background, emerald accent (`#34d399`), Inter sans-serif, `>>` `-` company mark in header.

## Environment

| Variable | Default |
|---|---|
| `LOCAL_AGENT_URL` | `http://127.0.0.1:43124` |
| `GROQ_API_KEY` | Set in repo root `.env` (never commit) |

Playwright automation credentials: `automation/config/.env` (copy from `environments.example.env`).
