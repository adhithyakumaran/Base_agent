# Base Agent — Enterprise Runtime

Deterministic-first agent runtime for **QA Agent** and **Security Agent** plugins.

Oracle APEX Endless Aisle (Titan/Tanishq UAT) is the first target application. Ground Truth from SME is **optional later** — the runtime must perform well before GT exists, using KB + deterministic rules, and must **never loop until success**.

## Principles

- **Deterministic-first + LLM-when-required** (LLM is not the kernel)
- Structured results: `PASS` | `FAIL` | `BLOCKED` | `UNKNOWN` | `INSUFFICIENT_EVIDENCE`
- Hard budgets: steps / tools / LLM / pages / cycle detection
- Plugins: Mock Demo + QA APEX (discovery/sanity) on top of the core
- Deploy path: Azure Pipelines → OCI (see docs)

## Quick start

```bash
python3 -m pip install -e '.[dev]'
python3 -m pytest tests/unit -q
python3 -m base_agent.api "echo hello"
python3 -m base_agent.api "discover the application map" --kb-dir discovery/uat_ea/kb
```

## Repo map

| Path | Purpose |
|---|---|
| `src/base_agent/` | Runtime core (state, router, executor, decision, GT/KB interfaces, LangGraph) |
| `plugins/mock_demo/` | Deterministic mock tools |
| `plugins/qa_apex/` | APEX discover/sanity tools (bounded, anti-stuck metadata) |
| `discovery/uat_ea/` | Live UAT KB candidates + approval checklist + recordings merge |
| `docs/BASE_AGENT_TECHNICAL_PROPOSAL.md` | Full runtime proposal |
| `docs/APEX_GT_KB_COLLECTION_SPEC.md` | KB/GT schemas |
| `docs/architecture/OPERATING_WITHOUT_GT.md` | How we run before SME GT |
| `docs/architecture/APEX_CRAWLER_PERFORMANCE.md` | Crawler anti-stuck / APEX notes |
| `docs/architecture/AZURE_OCI_DEPLOYMENT.md` | Azure Pipelines → OCI |

## Without Ground Truth — what works now

- Discover/map Endless Aisle from KB + future live crawler skill
- Technical FAIL via rules (ORA/error pages, authz, budgets)
- Honest `UNKNOWN` when business expectation is missing
- Zero LLM on echo/discover happy paths

SME GT later only increases deterministic PASS/FAIL coverage — it does not redesign the agent.

## UAT discovery artifacts

- [discovery/uat_ea/APPROVAL_CHECKLIST.md](discovery/uat_ea/APPROVAL_CHECKLIST.md)
- [discovery/uat_ea/kb_normalized/](discovery/uat_ea/kb_normalized/) (schema-normalized KB)
- Recordings merged under `discovery/uat_ea/recordings/`

## Status

Base Agent runtime v0.1 is implemented and unit-tested. Next: live Playwright crawler skill wired to budgets, Azure pipeline YAML, OCI image packaging.
