# ScoutAI Console — Enterprise SaaS UI v2

This document summarizes the v2 frontend redesign for client demos.

## Design tokens

- Palette and typography live in `apps/console/styles/design-tokens.css` and `apps/console/styles/scout-v2.css`.
- Primary actions use near-black buttons (`btn-black`); accents use blue/cyan gradients selectively.

## Layout

- Sidebar: ~260px, `#F3F5F8`, grouped navigation (Operate / Investigate / Govern / Configure).
- Main content: up to ~1500px width, 32–48px padding, no narrow centered column.

## Key screens

| Screen | Component | Notes |
|--------|-----------|--------|
| Ask Agent | `views/ask-agent-view.tsx` | Wide command card, suggestions, readiness strip, horizontal latest-run timeline |
| Flows | `views/flows-view.tsx` | 3-column cards, gradient selected state, tabbed detail incl. Automation terminal |
| Connectors | `views/connectors-view.tsx` | Sectioned cards, modal configure for channels/schedule |
| Evidence | `views/evidence-view.tsx` | Filters, grid, full-screen lightbox |
| Runs | `views/live-runs-view.tsx` | Execution metrics strip, horizontal timeline, collapsible diagnostics |
| Agent chat | `agent-chat-panel.tsx` | FAB + panel; `/api/agent-chat` with scoped read-only tools |

## Agent chat security

- Tools implemented in `lib/agent-chat-tools.ts`.
- No shell execution, no `.env` or credential paths; repository reads limited to QA/design paths.
- Tool calls are returned in the API `audit` array for traceability.

## API additions

- `POST /api/agent-chat` — workspace Q&A over flows, runs, evidence metadata, and allowed source files.
- `GET /api/flows/[id]` — extended with scenarios, suites, automation metadata, and overview fields for the Flow detail tabs.

## Running locally

```bash
cd apps/console
npm run dev
```

Open the console on port 43123 (see `package.json`).
