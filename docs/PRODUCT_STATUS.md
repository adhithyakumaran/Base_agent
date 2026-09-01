# Product status — Base Agent + QA Console

## Honest readiness (not “everything perfect” yet)

| Area | Status |
|---|---|
| Base Agent control plane (budgets, no loop-until-success, UNKNOWN) | **Ready** |
| QA skills: discover, crawl, sanity, flow catalog | **Partial** — more APEX interaction skills next |
| LLM | **API-only gateway** — models chosen in console / env; not a single locked vendor |
| Sanity + ad-hoc + report generation | **Console + runtime wired** |
| Daily morning sanity schedule | **Configurable in UI**; wire Azure/OCI cron to the same API in deploy |
| Report channels (email / Teams / WhatsApp / Slack) | **Configured + queued in traces**; live webhook send on OCI secrets |
| Enterprise frontend | **Shipped** (`qa-console`) — Vercel/GitHub-like light console |
| Knowledge dump → data pills | **Shipped** |
| Live side-panel traces + history + token usage | **Shipped** |
| Full Customer Order deep skills / approved GT pack | **Pending** SME + more recordings |

## LLM model posture

- Transport: **HTTP APIs only** via gateway (Azure OpenAI, OpenAI, Anthropic, OCI Generative AI)
- Roles: fast / reasoning / fallback
- Console picker stores selection; crawl/sanity remain deterministic-first (`disabled` = 0 LLM)
- Client can change models without redesigning the agent
