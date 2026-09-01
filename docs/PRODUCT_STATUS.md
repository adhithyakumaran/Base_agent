# Product status — Base Agent + QA Console

## Phase: CLOSED (pause) — resume later

See [PHASE_COMPLETE.md](PHASE_COMPLETE.md).

## Honest readiness

| Area | Status |
|---|---|
| Base Agent control plane (budgets, no loop-until-success, UNKNOWN) | **Ready** |
| Folder layout vs Base Agent proposal §23 | **Followed** (plugins outside core) |
| QA skills (health, mission pack, probes, crawl, …) | **Local-demo ready**; deeper live APEX still pending |
| LLM | **Off by default** (API gateway optional later) |
| Console (dark) + warm local agent | **Ready** |
| SME Ground Truth | **Pending** (~1 week) |
| Azure / OCI production cutover | **Deferred** (local-first) |

## LLM model posture

- Transport: HTTP APIs only via gateway when enabled  
- **Current runs: 0 LLM calls** (`LLM_ENABLED=false`, model `disabled`)  
- Placeholders if enabled later: fast `gpt-4o-mini`, reasoning `gpt-4o`
