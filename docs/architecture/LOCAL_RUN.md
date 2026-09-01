# Local-first run (priority over Azure/OCI for now)

## Why QA skills are not “deep” yet

Deep browser QA (click Customer Order, fill LOVs, edit Interactive Grids, assert business totals) is blocked by **inputs**, not by the Base Agent kernel:

| Blocker | Effect |
|---|---|
| No always-on live UAT session in this env | Skills stay KB/rules depth unless `APEX_*` creds + Playwright crawl are used |
| SME Ground Truth not approved yet (~1 week) | Agent can map/probe/replay candidates but cannot assert business **PASS/FAIL** |
| Some Endless Aisle paths still thin in KB (e.g. Customer Order) | Flow replay cannot invent steps it never observed |

What **is** deep locally today: health pack, login readiness, component probes (`P6_SKU`…), flow replay from KB, **mission pack** (runs those together in one tool call).

## LLM model — what we actually use

**Default: no LLM.**  
`LLM_ENABLED=false`, console model gateway default = `disabled`.

Catalog placeholders (only if you enable the gateway later):

- fast: `gpt-4o-mini`
- reasoning: `gpt-4o`
- fallback: `gpt-4o-mini`

Those are **API gateway options**, not an active model. Local demo runs with **0 LLM calls**.

## Efficient local run

Terminal 1 — warm agent (keeps runtime in memory):

```bash
cd /workspace
PYTHONPATH=src:. python3 scripts/local_agent_server.py --port 43124
```

Terminal 2 — console:

```bash
cd qa-console
LOCAL_AGENT_URL=http://127.0.0.1:43124 npm run dev
```

CLI (no console):

```bash
PYTHONPATH=src:. python3 -m base_agent.api "mission pack" --kb-dir discovery/uat_ea/kb
PYTHONPATH=src:. python3 -m base_agent.api "health check endless aisle" --kb-dir discovery/uat_ea/kb
```

Warm server avoids cold Python process spawn on every console click.
