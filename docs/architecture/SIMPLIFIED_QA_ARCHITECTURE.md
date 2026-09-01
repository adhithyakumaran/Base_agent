# Simplified QA architecture (GTM-first)

**Date:** 2026-09-01  
**Audience:** Client delivery / engineering pivot  
**Source:** Client need = **sanity + adhoc** only. OpenClaw discussion PDF. SME GT later.

---

## 1. Honest assessment — we overcomplicated

What the client asked for:

- Morning **sanity** (scheduled)
- **Ad-hoc** “check this” when something feels off
- **Report** (email / Teams / WhatsApp)
- GT will come — but product must work **before** GT

What we built (useful but heavy for v1):

- Full Base Agent kernel (LangGraph, budgets, many micro-skills)
- Custom Playwright crawler + KB-only probes
- LLM **disabled** by default
- Heavy `UNKNOWN` / `INSUFFICIENT_EVIDENCE` when no GT

**Verdict:** Good **platform foundation**, wrong **default product shape** for fast GTM.  
Sanity/adhoc does not need 10 deterministic skills replaying KB without a browser.

---

## 2. Simplified target (what to ship)

```
Tester / Console
      │
      ▼
┌─────────────────────────────────────┐
│  QA Orchestrator (thin)             │
│  • goal in (NL)                     │
│  • schedule sanity / adhoc          │
│  • one run at a time                │
│  • report out                       │
└──────────────┬──────────────────────┘
               │
     ┌─────────┴─────────┐
     ▼                   ▼
┌──────────┐      ┌──────────────┐
│ LLM      │      │ KB + GT      │
│ Planner  │◄────►│ (RAG)        │
│          │      │ pages/flows  │
└────┬─────┘      └──────────────┘
     │ plan steps
     ▼
┌──────────────┐
│ OpenClaw     │  ← browser: navigate, click, type, screenshot
│ (execution)  │  ← record exploration → KB candidates
└──────┬───────┘
       ▼
 Oracle APEX UAT
       │
       ▼
 Observations + evidence
       │
       ▼
 Validator (phase-dependent — see §4)
       │
       ▼
 PASS / FAIL / NEEDS_REVIEW + report
```

**OpenClaw** = do the work (per PDF). **Not** a replacement for LLM.  
**LLM** = understand goal, plan steps, reason about UI, use KB context.  
**Our layer** = QA KB, GT lifecycle, validation rules, evidence, reporting, console.

---

## 3. What we stop building (or demote)

| Stop / demote | Why |
|---|---|
| Custom Playwright crawler as primary | OpenClaw already does navigation + evidence |
| Many KB-only “skills” (mission pack, page probe, …) | Shallow without browser; duplicate planner work |
| LLM off for QA product | Planner needs LLM for adhoc NL |
| LangGraph as product kernel | Keep thin orchestrator; not every step needs a graph node |
| Azure/OCI before local GTM | Defer until demo works on laptop |

**Keep from current repo:**

| Keep | Why |
|---|---|
| `discovery/uat_ea/kb/` + approval checklist | Already captured UAT; feeds RAG |
| `qa-console/` | Trigger, schedule, channels, traces, history |
| GT/KB spec docs | SME approval path unchanged |
| No loop-until-success | Client requirement — one honest run, then report |
| Report delivery stubs | Email/WhatsApp/Teams |

---

## 4. Validation — two phases (your point is correct)

### Phase A — Pre-GT (GTM / demo / first weeks)

**Goal:** Useful sanity + adhoc **without** pretending we know business truth.

| Input | Behavior |
|---|---|
| NL goal + KB context | LLM plans steps |
| OpenClaw | Executes in browser, screenshots, records flow |
| Technical rules only | ORA page, login dead, obvious crash, stuck modal |
| Business checks | LLM + KB **suggests** pass/fail → report as **NEEDS_REVIEW** or **LIKELY_OK** — not fake deterministic PASS |

Deterministic where it matters (infra): timeouts, one run, no infinite retry, capture evidence.  
**Not** deterministic on business assertions until GT exists.

### Phase B — Post-GT (SME approved)

**Goal:** Same stack, **stronger** validation.

| Input | Behavior |
|---|---|
| Approved GT facts | Deterministic expected vs actual |
| LLM | Disambiguation only when GT + KB insufficient |
| OpenClaw | Same execution + **record** golden paths for regression |

**Become more deterministic as GT grows** — exactly as you said.  
GT turns `NEEDS_REVIEW` into `PASS`/`FAIL` without redesigning the agent.

---

## 5. Product flows (only two + exploration)

### 5.1 Scheduled sanity (morning)

1. Console/cron fires: `sanity check Endless Aisle`
2. LLM loads KB slice (home, login, key modules from discovery)
3. OpenClaw: login → home → spot-check modules from KB
4. Technical rules + LLM summary
5. Report → email / WhatsApp / Teams

### 5.2 Ad-hoc

1. Tester: “check find price with SKU X” (console or NL)
2. LLM plans from KB + optional context packet
3. OpenClaw executes + screenshots
4. Report with evidence

### 5.3 Exploration (builds KB — can be manual + agent-assisted)

1. Tester explores UAT (or OpenClaw guided tour)
2. **Record** clicks, pages, fields → KB candidates (already have recording merge pattern)
3. SME approves → GT later

No separate “discover skill”, “mission pack”, “flow replay” product surface — **one execution path**.

---

## 6. Minimal repo shape after simplification

```
base-agent/                    # rename mentally to qa-platform if you want
├── qa-console/                # UI: sanity, adhoc, schedule, reports
├── discovery/uat_ea/          # KB + GT candidates (keep)
├── docs/                      # specs (keep)
├── src/qa_orchestrator/       # NEW thin layer (or slim base_agent)
│   ├── planner.py             # LLM: goal → steps (uses KB RAG)
│   ├── openclaw_adapter.py    # execute plan, return observations
│   ├── validator.py           # phase A rules / phase B GT compare
│   └── reporter.py            # markdown + channel send
└── plugins/                   # optional: mock for tests only
```

**Deprecate for product path (keep in repo until cutover):**

- `plugins/qa_apex/crawler/` as primary
- `plugins/qa_apex/skills.py` micro-skills
- Heavy `base_agent/graph/` for QA runs

Base Agent runtime can remain for **future Security agent** or internal policy — QA product does not need full Week-1 kernel on the hot path.

---

## 7. LLM model (product default)

| Role | When | Example |
|---|---|---|
| Planner / reasoner | **On** for sanity + adhoc | Claude / GPT-4o via API (client choice) |
| Fast summarizer | Report text | gpt-4o-mini or equivalent |
| Deterministic compare | **After GT** | Code, not LLM |

OpenClaw picks its own provider stack for browser agent; our planner stays **replaceable** (per PDF §8).

---

## 8. Fastest path to client demo

1. **Wire OpenClaw adapter** — one function: `run_plan(steps) → observations + screenshots`
2. **Wire LLM planner** — `goal + kb_context → steps` (use existing KB JSON)
3. **Console** — two buttons: **Sanity** / **Ad-hoc** + prompt (already there)
4. **Validator phase A** — technical rules + LLM narrative; no fake PASS
5. **Report** — existing channel stubs
6. **When GT arrives** — flip validator to phase B for approved subjects only

Estimated cut: **remove ~70% of custom browser/skill code** from the hot path; reuse KB + console + GT docs.

---

## 9. Alignment with OpenClaw PDF

| PDF point | Simplified architecture |
|---|---|
| OpenClaw = browser execution | Yes — primary executor |
| LLM = brain, not replaced | Yes — planner on for product |
| Interactive exploration → KB | Yes — record via OpenClaw + merge to `discovery/` |
| We build QA intelligence | KB, GT, validation, reports, console |
| “Go check the cart” | Ad-hoc flow: planner + OpenClaw + report |

---

## 10. Decision

**Yes — simplify.**  
Deliver **sanity + adhoc + report** with **LLM + OpenClaw + KB**.  
Add **deterministic GT validation** when SME approves — not before.

Current repo is **phase 0 platform**; next increment is **phase 1 product** per this doc.
