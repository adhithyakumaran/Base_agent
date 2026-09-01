# Phase status — CLOSED for now (continue later)

**Marked done:** 2026-09-01  
**Next session:** resume local deepening + SME GT when ready

## This phase delivered

- Base Agent runtime (deterministic-first, budgets, no loop-until-success)
- QA APEX plugin skills (discover/crawl/sanity/health/login/probes/flow replay/mission pack/report)
- Dark enterprise console (`qa-console/`)
- Local warm agent server (`scripts/local_agent_server.py`) — **LLM off by default**
- Endless Aisle KB candidates + approval checklist (GT pending SME ~1 week)
- Docs aligned to Base Agent proposal

## Folder structure vs docs

We follow `docs/BASE_AGENT_TECHNICAL_PROPOSAL.md` §23:

| Docs layout | This repo |
|---|---|
| `src/base_agent/` core runtime | Yes |
| `plugins/` outside core (QA not forked into kernel) | Yes — `plugins/qa_apex/`, `plugins/mock_demo/` |
| `docs/` | Yes |
| `tests/unit` (+ graph/eval stubs) | Yes |
| `examples/` | Yes |
| Extra (product surface) | `qa-console/`, `discovery/uat_ea/`, `scripts/`, `deploy/` — allowed product layers on top of the kernel |

Core rule held: **no APEX/QA browser logic inside `src/base_agent`** — skills live in `plugins/`.

## LLM

Default **off**. No model called until gateway enabled. Catalog placeholders only: `gpt-4o-mini` / `gpt-4o`.

## Resume later — simplified direction

**Pivot agreed:** see [architecture/SIMPLIFIED_QA_ARCHITECTURE.md](architecture/SIMPLIFIED_QA_ARCHITECTURE.md).

Next build (GTM):

1. OpenClaw adapter (browser execution + record)  
2. LLM planner (sanity + adhoc from KB)  
3. Phase A validator (technical + NEEDS_REVIEW)  
4. Phase B GT compare when SME approves  

Deprioritize: custom Playwright crawler + KB-only micro-skills on product hot path.

Local run (current stack until cutover): `docs/architecture/LOCAL_RUN.md`.
