# Base Agent — Enterprise Runtime

Deterministic-first agent runtime for **QA Agent** and **Security Agent** plugins.

Oracle APEX Endless Aisle (Titan/Tanishq UAT) is the first target application. Ground Truth from SME is **optional later** — the runtime must perform well before GT exists, using KB + deterministic rules, and must **never loop until success**.

## Principles

- **Deterministic-first + LLM-when-required** (LLM is not the kernel)
- Structured results: `PASS` | `FAIL` | `BLOCKED` | `UNKNOWN` | `INSUFFICIENT_EVIDENCE`
- Hard budgets: steps / tools / LLM / pages / cycle detection
- Plugins: Mock Demo + QA APEX (discovery / sanity / flow catalog + anti-stuck crawler)
- Deploy path: Azure Pipelines → OCI (`azure-pipelines.yml`, `deploy/Dockerfile`)

## Quick start

```bash
python3 -m pip install -e '.[dev,browser]'
python3 -m pytest tests/unit -q
python3 -m base_agent.api "echo hello"
python3 -m base_agent.api "discover the application map" --kb-dir discovery/uat_ea/kb
python3 -m base_agent.api "list application flows" --kb-dir discovery/uat_ea/kb
python3 -m base_agent.api "sanity check endless aisle" --kb-dir discovery/uat_ea/kb
```

Live crawl (optional — secrets via env, never git):

```bash
export APEX_TARGET_URL='https://…/ords/r/tjdcom/ea/login'
export APEX_USERNAME='…'
export APEX_PASSWORD='…'
python3 -m base_agent.api "discover and crawl the application" --kb-dir discovery/uat_ea/kb
```

## Repo map

| Path | Purpose |
|---|---|
| `src/base_agent/` | Runtime core (state, router, executor, decision, GT/KB, LangGraph, LLM gateway) |
| `plugins/mock_demo/` | Deterministic mock tools |
| `plugins/qa_apex/` | APEX discover / sanity / flow catalog + Playwright crawler |
| `discovery/uat_ea/` | Live UAT KB candidates + approval checklist + recordings merge |
| `docs/BASE_AGENT_TECHNICAL_PROPOSAL.md` | Full runtime proposal (base agent contract) |
| `docs/APEX_GT_KB_COLLECTION_SPEC.md` | KB/GT schemas |
| `docs/architecture/OPERATING_WITHOUT_GT.md` | How we run before SME GT |
| `docs/architecture/APEX_APPLICATION_FLOWS.md` | APEX flow patterns for the QA agent |
| `docs/architecture/APEX_CRAWLER_PERFORMANCE.md` | Crawler anti-stuck / performance |
| `docs/architecture/AZURE_OCI_DEPLOYMENT.md` | Azure Pipelines → OCI |
| `azure-pipelines.yml` | CI test + image package stages |
| `deploy/Dockerfile` | OCI-ready runtime image |

## Without Ground Truth — what works now

| Capability | Status |
|---|---|
| KB map of Endless Aisle pages/flows/components | Yes |
| Platform APEX flow patterns (auth, LOV, modal, IG) | Yes |
| Technical FAIL (ORA, session dead, modal hang, auth blockers) | Yes |
| Live bounded crawl when credentials provided | Yes |
| Business PASS/FAIL (order totals, required modules) | Needs SME-approved GT |
| Honest stop (`UNKNOWN` / `INSUFFICIENT_EVIDENCE`) | Always — **no loop-until-success** |

SME GT later only increases deterministic PASS/FAIL coverage — it does not redesign the agent.

## UAT discovery artifacts

- [discovery/uat_ea/APPROVAL_CHECKLIST.md](discovery/uat_ea/APPROVAL_CHECKLIST.md)
- [discovery/uat_ea/kb/](discovery/uat_ea/kb/) (includes `pattern.apex.*` flow patterns)
- [discovery/uat_ea/kb_normalized/](discovery/uat_ea/kb_normalized/)

## Status

Base Agent runtime v0.2: enterprise crawler skill, APEX flow KB patterns, Azure→OCI packaging stubs, unit tests green with LLM disabled.
