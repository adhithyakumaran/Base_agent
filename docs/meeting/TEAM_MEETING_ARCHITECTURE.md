# Apex QA Agent — Team Meeting Brief

**Date:** 4 Sep 2026 · **App:** Oracle APEX Endless Aisle (Titan/Tanishq UAT)  
**Status:** Local demo ready · **GT session:** today with SME

> **One-liner:** Morning sanity + ad-hoc NL checks + multi-channel reports. LLM plans; Playwright executes; GT validates after SME approval. No loop-until-success.

---

## 1. Client requirement

| Need | Answer |
|---|---|
| Morning sanity | 08:00 IST → login + home + modules → report |
| Ad-hoc checks | NL command → plan → Playwright → report |
| Reports | Email / WhatsApp / Teams |
| Pre-GT | Phase A: `NEEDS_REVIEW` (honest) |
| Post-GT (today) | Phase B: deterministic PASS/FAIL |

---

## 2. Architecture (linear)

```
┌─────────────────────────────────────────────────────────────┐
│  QA Console (Next.js) — command · schedule · traces · reports │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  QA Orchestrator — single-run lock · budgets · report        │
└───────┬─────────────────────┬─────────────────────────────┘
        ▼                     ▼
┌───────────────┐     ┌────────────────┐
│ LLM Planner   │◄───►│ KB + GT (RAG)  │
│ Groq → Claude │     │ 64 docs · 22 GT│
└───────┬───────┘     └────────────────┘
        ▼ plan
┌─────────────────────────────────────────────────────────────┐
│  Playwright Browser Executor (QA plugin)                     │
└────────────────────────────┬────────────────────────────────┘
                             ▼
                  Oracle APEX UAT (Endless Aisle)
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  Validator Phase A / B → PASS · FAIL · NEEDS_REVIEW          │
└────────────────────────────┬────────────────────────────────┘
                             ▼
                    Report → email · WA · Teams
```

### Control-plane flow

```
Goal → Goal Handler → Decision Engine → Tool Executor (Playwright)
                    ↘ LLM Planner (if NL ambiguous)
Observations → Validator → Report
```

### LLM vs deterministic

| Layer | Mode |
|---|---|
| Budgets, routing, GT compare | Deterministic |
| NL goal → plan | LLM (Groq → Claude) |
| Browser steps | Deterministic (Playwright) |
| Pre-GT business | LLM + rules → `NEEDS_REVIEW` |
| Post-GT business | Deterministic PASS/FAIL |

---

## 3. Plugin model (QA + Security)

```
base_agent kernel (shared)
    ├── plugins/qa_apex      → Playwright, sanity, flows, reports
    └── plugins/security_*   → authz, session, OWASP (later)
              └── discovery/uat_ea/gt/  (shared GT store)
```

---

## 4. Folder structure

See `docs/meeting/folder_tree.txt` and PDF section 5 for the full working tree (316 lines).

Key roots:

- `qa-console/` — Next.js UI  
- `src/base_agent/` — shared runtime kernel  
- `src/qa_orchestrator/` — thin sanity/adhoc path  
- `plugins/qa_apex/` — Playwright crawler + skills  
- `discovery/uat_ea/` — KB, GT candidates, recordings  
- `azure-pipelines.yml` — CI → OCI

---

## 5. Requirements checklist

| Item | Owner |
|---|---|
| `GROQ_API_KEY` | Dev |
| `APEX_*` credentials | Client vault |
| SME GT approval (today) | SME |
| SMTP / Twilio / Teams | Client IT |
| Azure + OCI registry | Client IT |

---

## 6. Delivery: local → Azure → OCI

1. Local dev (laptop)  
2. Azure Pipelines (pytest + Docker)  
3. Push images to OCI registry  
4. Deploy with vault secrets — **no raw source to client**

---

## 7. Tech stack

Python · Pydantic · LangGraph · Playwright · LiteLLM (Groq/Claude) · Next.js · Azure Pipelines · OCI containers

---

## 8. UI screenshots

Embedded in `TEAM_MEETING_ARCHITECTURE.pdf` (section 10).

**Regenerate PDF:** `python3 scripts/build_meeting_pdf.py`
