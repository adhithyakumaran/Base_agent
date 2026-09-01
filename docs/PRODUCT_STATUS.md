# Product status — Base Agent + QA Console

## Phase: CLOSED (pause) — **simplify next**

See [PHASE_COMPLETE.md](PHASE_COMPLETE.md) and **[SIMPLIFIED_QA_ARCHITECTURE.md](architecture/SIMPLIFIED_QA_ARCHITECTURE.md)**.

| Area | Status |
|---|---|
| Base Agent control plane | Built (may be **too heavy** for QA v1 hot path) |
| **Recommended product path** | **LLM planner + OpenClaw execution + KB + reports** |
| QA micro-skills / custom crawler | **Deprioritize** — OpenClaw does navigation |
| Deterministic validation | **Light pre-GT**; **strong post-GT** when SME approves |
| Console | Keep — sanity/adhoc/schedule/channels |
| SME Ground Truth | Pending (~1 week) |

## LLM model posture

- Transport: HTTP APIs only via gateway when enabled  
- **Current runs: 0 LLM calls** (`LLM_ENABLED=false`, model `disabled`)  
- Placeholders if enabled later: fast `gpt-4o-mini`, reasoning `gpt-4o`
