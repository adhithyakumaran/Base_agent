# Enterprise QA Orchestrator

**Version 2.0** — aligned with `docs/finalized-proposal/ARCHITECTURE_LOCKED.md`

## Pipeline

```text
User prompt (NL)
    → IntentClassifier (Groq/Claude or deterministic fallback)
    → FlowKnowledgeGraph (19 READY primary + 6 DRAFT supporting)
    → SuiteSelector (deterministic approved Playwright suites)
    → PlaywrightRunner (zero LLM at execution)
    → DiscoveryService (new_feature / discover modes)
    → Validator + enterprise Markdown report
```

## Execution modes

| Mode | Example prompt | LLM at run time |
|---|---|---|
| `morning_sanity` | "morning sanity check" | No |
| `adhoc_existing` | "check login" | Classify only |
| `adhoc_parameterized` | "SKU 12345 in search" | Classify + extract params |
| `incident_multi_flow` | "payment failing" | Classify + graph traverse |
| `new_feature` | "new banner on product page" | Classify + crawl |
| `discover` | "crawl product area" | Classify + crawl |

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | — | Groq intent classification |
| `LLM_MODEL_FAST` | `groq/qwen/qwen3.6-27b` | Fast intent/summary (replaces retired Llama 3.3 70B for speed) |
| `LLM_MODEL_REASONING` | `groq/openai/gpt-oss-120b` | Primary reasoning model per Groq deprecations guide |
| `LLM_PROVIDER` | `groq` | Set `anthropic` for Claude |
| `ANTHROPIC_API_KEY` | — | Claude when swapping provider |
| `LLM_ENABLED` | `true` | Disable for deterministic-only |
| `QA_RUNNER` | `playwright` | `dry_run` for CI; `openclaw` legacy |
| `QA_CRAWL_LIVE` | — | Set `true` for live browser crawl |
| `QA_DISCOVERY_ROOT` | `discovery/uat_ea` | KB + graph root |

## Run locally

```bash
# Install Python deps
pip install -e ".[llm]"

# Dry-run orchestrator (no npm)
QA_RUNNER=dry_run LLM_ENABLED=false python -m qa_orchestrator.api "morning sanity check" --type sanity

# HTTP server (console / chat clients)
PYTHONPATH=src:. QA_RUNNER=dry_run python3 scripts/local_agent_server.py --port 43124

# Live Playwright execution
QA_RUNNER=playwright cd automation && npm ci && npm run test:sanity
```

## API

- `POST /run` — full orchestrator payload
- `POST /chat` — same body + `chat` summary block
- `GET /health` — service metadata

## Swap Groq → Claude

```bash
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-...
export LLM_MODEL_REASONING=claude-sonnet-4-20250514
```

No code changes required — `PlannerLlmClient` uses LiteLLM.

## Groq model note (Sep 2026)

`llama-3.3-70b-versatile` was retired on Groq Free/Developer tiers. Defaults are now:

- **Reasoning:** `groq/openai/gpt-oss-120b`
- **Fast classify/summary:** `groq/qwen/qwen3.6-27b`

Override via `LLM_MODEL_REASONING` and `LLM_MODEL_FAST` in `.env`.
