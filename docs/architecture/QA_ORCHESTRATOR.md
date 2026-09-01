# QA Orchestrator — Phase 1 product path

Thin orchestrator: **LLM planner (Groq → Claude later) + OpenClaw browser execution + KB RAG + validation + reports**.

Console UI (`qa-console/`) is unchanged — it calls this layer via `scripts/local_agent_server.py`.

## Architecture

```
Console → local_agent_server.py → qa_orchestrator
  ├─ planner.py      (Groq/Claude via LiteLLM)
  ├─ kb_rag.py       (discovery/uat_ea/kb)
  ├─ openclaw_adapter.py
  ├─ validator.py    (Phase A pre-GT / Phase B post-GT)
  └─ reporter.py
```

## Environment

| Variable | Purpose | Default |
|---|---|---|
| `GROQ_API_KEY` | Groq free-tier planner | required for LLM |
| `LLM_ENABLED` | Enable planner LLM | `true` |
| `LLM_PROVIDER` | `groq` or `anthropic` | `groq` |
| `LLM_MODEL_FAST` | Fast model | `groq/llama-3.1-8b-instant` |
| `LLM_MODEL_REASONING` | Planner model | `groq/llama-3.3-70b-versatile` |
| `ANTHROPIC_API_KEY` | Claude (later swap) | — |
| `OPENCLAW_MODE` | `mock` / `http` / `cli` | `mock` |
| `OPENCLAW_URL` | OpenClaw HTTP endpoint | `http://127.0.0.1:18789` |
| `APEX_USERNAME` / `APEX_PASSWORD` | UAT credentials (never commit) | — |

## Run locally

```bash
# Terminal 1
export GROQ_API_KEY='gsk_...'   # optional — without it, deterministic planner fallback
PYTHONPATH=src:. python3 scripts/local_agent_server.py --port 43124

# Terminal 2
cd qa-console && LOCAL_AGENT_URL=http://127.0.0.1:43124 npm run dev
```

CLI:

```bash
PYTHONPATH=src:. python3 -m qa_orchestrator.api "sanity check endless aisle" --type sanity
```

## OpenClaw

Set `OPENCLAW_MODE=http` when your OpenClaw instance is running and exposes `POST /execute` with plan JSON.

Until then, `mock` mode simulates steps and writes placeholder evidence under `artifacts/qa-evidence/`.

## Validation phases

- **Phase A (now):** technical rules + honest `NEEDS_REVIEW` — no fake business PASS
- **Phase B (post-SME):** deterministic GT compare from `discovery/uat_ea/gt/` approved facts

See `docs/architecture/SIMPLIFIED_QA_ARCHITECTURE.md`.
