# Apex QA Agent — Team Meeting Brief

**Date:** 4 Sep 2026 · **Target:** Oracle APEX Endless Aisle (Titan/Tanishq UAT)  
**Audience:** Internal team + client stakeholders  
**Status:** Working local demo · SME Ground Truth expected today

---

## 1. Client requirement (what we are building)

| Need | Our answer |
|---|---|
| **Morning sanity** — scheduled health check | Cron / Azure schedule → login + home + key modules → report |
| **Ad-hoc checks** — “check find price with SKU X” | Natural-language command in console → plan → browser run → report |
| **Reports** — email / WhatsApp / Teams | Structured markdown + JSON; delivery via configured channels |
| **Works before GT** | Phase A: technical rules + honest `NEEDS_REVIEW` |
| **Stronger after GT** | Phase B: deterministic expected vs actual (SME-approved facts) |
| **No loop-until-success** | One honest run, budgets enforced, then report |

**Not in v1 scope:** full regression suite, security pentest automation, multi-app platform.

---

## 2. Proposed architecture (simple, linear, efficient)

**Design choice:** Keep the **first working stack** (Base Agent kernel + Playwright browser + KB/GT).  
**Remove complexity:** no OpenClaw, no 10+ micro-skills on the hot path, no LLM-as-kernel.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  QA Console (Next.js) — command center, schedule, alerts, live traces   │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ HTTP (local) / API (OCI)
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  QA Orchestrator (thin) — one run at a time, budgets, report assembly   │
└───────┬─────────────────────────────┬───────────────────────┬───────────┘
        │                             │                       │
        ▼                             ▼                       ▼
┌───────────────┐            ┌────────────────┐      ┌──────────────────┐
│ LLM Planner   │◄──────────►│ KB + GT (RAG)  │      │ Report delivery  │
│ Groq → Claude │            │ discovery/uat  │      │ email/WA/Teams   │
└───────┬───────┘            └────────────────┘      └──────────────────┘
        │ plan steps
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Playwright Browser Executor (QA plugin) — navigate, click, screenshot  │
└───────────────────────────────┬─────────────────────────────────────────┘
                                ▼
                     Oracle APEX UAT (Endless Aisle)
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Validator — Phase A (pre-GT) or Phase B (post-SME GT)                 │
│  PASS / FAIL / NEEDS_REVIEW + evidence                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### LLM vs deterministic (who does what)

| Layer | Mode | Responsibility |
|---|---|---|
| Routing & budgets | **Deterministic** | One run lock, step/tool/LLM caps, no retry loops |
| KB / GT lookup | **Deterministic** | RAG over JSON docs; GT compare after SME approval |
| NL goal → plan | **LLM** (Groq free tier now; Claude API later) | Understand ad-hoc commands, pick flows from KB |
| Browser execution | **Deterministic** | Playwright steps, screenshots, timeouts |
| Technical validation | **Deterministic** | Login dead, crash, timeout, stuck modal |
| Business validation (pre-GT) | **LLM + rules** | Report `NEEDS_REVIEW` — never fake PASS |
| Business validation (post-GT) | **Deterministic** | Approved facts → PASS/FAIL |
| Report narrative | **LLM (optional)** | Short summary for email/WhatsApp |

---

## 3. Ground Truth — today’s SME session

**Current KB:** 64 documents · **GT candidates:** 22 · **Approval checklist:** `discovery/uat_ea/APPROVAL_CHECKLIST.md`

| Phase | When | Validation behaviour |
|---|---|---|
| **A — Pre-GT** | Now (demo / first weeks) | Technical PASS/FAIL; business → `NEEDS_REVIEW` |
| **B — Post-GT** | After SME marks facts **APPROVED** | Deterministic expected vs actual per subject |

**Action today:** SME reviews checklist → approve/reject each candidate → we load approved facts into `discovery/uat_ea/gt/` → validator flips to Phase B for those subjects.

---

## 4. Folder structure

```
base-agent/
├── qa-console/                 # Web UI (command center, schedule, reports)
│   ├── app/api/                # /runs, /state, /knowledge, /settings
│   ├── components/             # Dark enterprise console
│   └── lib/                    # Agent bridge, notify, store
│
├── src/
│   ├── base_agent/             # Shared runtime kernel (both agents)
│   │   ├── decision/           # Decision engine, budgets
│   │   ├── llm/                # LiteLLM gateway (Groq / Claude / Azure)
│   │   ├── ground_truth/       # GT provider protocol
│   │   ├── knowledge/          # KB provider protocol
│   │   └── graph/              # LangGraph control plane
│   │
│   └── qa_orchestrator/        # Thin product layer (sanity + adhoc hot path)
│       ├── planner.py          # LLM + KB → execution plan
│       ├── openclaw_adapter.py # → Playwright executor (browser)
│       ├── validator.py        # Phase A / B
│       └── reporter.py         # Markdown + channel payload
│
├── plugins/
│   ├── qa_apex/                # QA Agent plugin
│   │   ├── crawler/            # Playwright APEX navigation
│   │   ├── skills.py           # Sanity / flow / probe skills
│   │   └── tools.py            # Tool registry entries
│   │
│   └── mock_demo/              # Deterministic test plugin
│   # plugins/security_*/       # Security Agent (future — same kernel)
│
├── discovery/uat_ea/
│   ├── kb/                     # 64 KB JSON docs (pages, flows, components)
│   ├── gt/                     # SME-approved Ground Truth (today)
│   └── APPROVAL_CHECKLIST.md
│
├── scripts/
│   ├── local_agent_server.py   # Warm HTTP server for console
│   └── morning_patrol.py       # Scheduled sanity runner
│
├── deploy/                     # Dockerfile (runtime image)
├── azure-pipelines.yml         # CI → package → OCI deploy gate
├── tests/unit/                 # 26+ unit tests
└── docs/                       # Architecture & specs
```

---

## 5. How QA and Security plug in (same kernel, different plugins)

```
                    ┌─────────────────────┐
                    │   base_agent kernel  │
                    │ budgets · GT · KB    │
                    │ LLM gateway · graph  │
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
    ┌──────────────────┐              ┌──────────────────┐
    │  plugins/qa_apex  │              │ plugins/security  │
    │  · Playwright     │              │  · authz probes   │
    │  · flow replay    │              │  · session checks │
    │  · sanity skills  │              │  · OWASP subjects │
    └────────┬─────────┘              └────────┬─────────┘
             │                                  │
             └────────────┬─────────────────────┘
                          ▼
              discovery/uat_ea/gt/  (shared GT store)
              tags: [qa] | [security]
```

- **QA Agent (now):** browser flows, sanity, adhoc, morning patrol, reports.  
- **Security Agent (later):** same GT/KB shapes; adds subjects like `authz.idor`, `session.fixation`.  
- **No fork:** plugins register tools only; core runtime unchanged.

---

## 6. Requirements checklist (completion blockers)

### QA Agent — must have

| Item | Owner | Notes |
|---|---|---|
| `GROQ_API_KEY` | Dev | Free-tier planner (swap to `ANTHROPIC_API_KEY` + Claude later) |
| `APEX_TARGET_URL` | Client/SME | UAT login URL |
| `APEX_USERNAME` / `APEX_PASSWORD` | Client | Store in vault only — never git |
| **SME Ground Truth approval** | SME (today) | Mark checklist in `APPROVAL_CHECKLIST.md` |
| SMTP or SendGrid | Client/IT | Email report delivery |
| Twilio (or Meta WA Business) | Client/IT | WhatsApp report delivery |
| Teams incoming webhook | Client/IT | Optional channel |
| Azure DevOps project + repo access | Client/IT | CI/CD |
| OCI tenancy + container registry | Client/IT | Runtime host (data residency) |
| OCI Vault / Azure Key Vault | Client/IT | Secret injection at deploy |

### Security Agent — later (same platform)

| Item | Notes |
|---|---|
| Security test scope sign-off | Which OWASP / APEX subjects |
| Non-prod UAT only | No production creds in agent |
| Pen-test rules of engagement | Rate limits, allowed hours |

### Already built (demo-ready)

- Enterprise dark console UI  
- Local warm agent server + console bridge  
- KB pack (64 docs) + approval workflow  
- Unit tests (26 passing)  
- Azure pipeline skeleton + Docker images  
- Report routing stubs (email / WhatsApp / Teams)

---

## 7. Execution plan — local → Azure → client OCI

| Step | Where | What | Source-code safety |
|---|---|---|---|
| **1. Local build** | Developer laptop | `pip install`, `npm run dev`, Playwright, Groq key | Full repo on our side |
| **2. CI test** | Azure Pipelines | `pytest`, skill smoke, build Docker images | Tests only; no secrets in YAML |
| **3. Package** | Azure Pipelines | `base-agent:<buildId>` + `apex-qa-console:<buildId>` | **Compiled container images** — not raw source |
| **4. Push** | OCI Container Registry | Client-approved registry in their tenancy | Images only |
| **5. Deploy** | OCI Container Instances / OKE | Pull image + inject vault secrets | Runtime config only |
| **6. Schedule** | Azure cron or OCI Events | Morning patrol 08:00 IST | Report artifacts to channels |

**IP protection:** Client receives **versioned container images** + deployment manifests — not the git repository. Optional: private artifact feed, license on image, no shell in production image.

**Manual gate:** `DeployOCI=true` in Azure Pipeline after client UAT sign-off.

---

## 8. Tech stack (and why)

| Layer | Choice | Why |
|---|---|---|
| Runtime | **Python 3.10+**, Pydantic | Team skill, fast iteration, strong typing for GT/KB contracts |
| Control plane | **LangGraph** (bounded) | Explicit state machine; not LLM-driven loops |
| Browser | **Playwright** | Reliable APEX SPA navigation, screenshots, headless CI |
| LLM | **LiteLLM** → Groq / Claude | One gateway; swap models without code changes |
| Console | **Next.js 15**, TypeScript, Tailwind | Modern dark UI, fast local dev, Vercel-style UX |
| CI/CD | **Azure Pipelines** | Client enterprise standard |
| Runtime host | **OCI containers** | Client data residency requirement |
| Secrets | **Azure Key Vault / OCI Vault** | No credentials in repo or images |

---

## 9. Progress summary (for the meeting)

| Area | Status |
|---|---|
| Architecture | Simplified linear path agreed — **no OpenClaw** |
| Console UI | **Done** — command center, patrol, alerts, model picker |
| KB / discovery | **64 docs** from crawl + recordings |
| GT | **22 candidates** — **SME session today** |
| LLM planner | Groq wired; Claude-ready |
| Browser execution | Playwright plugin + mock/local path |
| Reports | Email / WhatsApp / Teams stubs |
| Tests | 26 unit tests green |
| Deploy skeleton | Azure → OCI pipeline + Dockerfiles |

**Next after GT today:** Load approved facts → enable Phase B validation → wire live SMTP/Twilio → first scheduled morning patrol in client OCI.

---

## 10. Console UI (screenshots)

See attached PDF pages for full screenshots.

- **Command center** — NL prompt, mission presets, report channels, live pipeline  
- **Model gateway** — Groq default; Claude when ready  
- **Morning patrol & alert routes** — 08:00 IST schedule, email/WhatsApp/Teams
