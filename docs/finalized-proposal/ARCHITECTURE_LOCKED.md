# Locked Architecture — AI QA Automation Platform

**Version:** 1.0 · **Status:** LOCKED · **Date:** September 2026

This document is the authoritative architecture reference. All implementation must align with this model.

---

## Operating model (four stages)

| Stage | Purpose |
|---|---|
| **Discover** | Browser + APEX metadata + recordings → application model |
| **Generate** | Flow knowledge → LLM → scenario/case/script/suite → **human approve** |
| **Execute** | NL prompt → orchestrator classifies → run **approved suites** → evidence → report |
| **Adapt** | Change detection → impact analysis → self-heal / maintenance → human approve |

---

## Request path (every user prompt)

```text
USER (natural language)
        │
        ▼
┌───────────────────┐
│  AI ORCHESTRATOR  │  ← LLM: intent, capability, flow, scope, params
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ KNOWLEDGE LAYER   │  KB + Knowledge Graph + Test Repository
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  SUITE SELECTION  │  Approved automation only (deterministic pick)
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ EXECUTION LAYER   │  Playwright · API · DB tools
└─────────┬─────────┘
          │
          ▼
       UAT APP
          │
    ┌─────┴─────┐
    ▼           ▼
  PASS         FAIL
                 │
         ┌───────┴────────┐
         ▼                ▼
   Self-Healing    Failure Analysis
         │                │
         └───────┬────────┘
                 ▼
              REPORT
```

---

## Four responsibilities (never merge)

| Layer | Question | Owner |
|---|---|---|
| **Knowledge** | What does the app do? | KB + Graph + GT |
| **Reasoning** | What does the user want? | LLM orchestrator |
| **Execution** | How do we test it? | Approved automation + tools |
| **Adaptation** | What changed / broke? | Discovery + self-heal + maintenance |

---

## LLM vs deterministic

| LLM | Deterministic |
|---|---|
| Intent / flow / capability classification | Browser clicks, API calls, DB queries |
| Multi-suite selection reasoning | Test execution, screenshots, network capture |
| Test generation (draft) | Evidence storage, result storage |
| Failure analysis narrative | Locator retry (bounded self-heal) |
| Maintenance recommendations | GT comparison after SME approval |

**LLM must not:** invent behavior, declare PASS without evidence, auto-modify production automation without approval.

---

## KB hierarchy (flow-centric)

```text
APPLICATION
 ├── BUSINESS CAPABILITIES  (Authentication, Product, Cart, Payment, Order…)
 │     └── BUSINESS FLOWS   (Login, Checkout, Find Price, Item Search…)
 │           ├── PAGES
 │           ├── COMPONENTS
 │           ├── BUSINESS RULES
 │           ├── APIs
 │           └── TEST SCENARIOS → CASES → SCRIPTS → SUITES
 └── METADATA (APEX app/pages/regions/items)
```

**Primary QA unit = business flow**, not page.

---

## Execution modes

| Mode | Trigger | LLM? | Action |
|---|---|---|---|
| **Morning sanity** | Schedule | No | Run all approved sanity suites → merge report |
| **Adhoc — existing** | "Check product page" | Classify only | Run existing page/flow suite |
| **Adhoc — parameterized** | "SKU 12345 404 in search" | Classify + extract param | Run search suite with `id=12345` |
| **Incident — multi-flow** | "Payment failing" | Classify + graph traverse | Run **all** payment-involved suites |
| **New feature** | "New banner on product page" | Classify + crawl | Run suite + discovery + suggest new tests → SME approve |

---

## Artifact hierarchy (locked)

```text
Business Flow → Scenario → Test Case → Test Script → Test Suite → Execution → Evidence
```

Generated assets require **human approval** before entering `automation/` repository.

---

## Knowledge graph (minimum edges)

```text
Capability ──HAS_FLOW──► Flow
Flow ──USES_PAGE──► Page
Page ──CONTAINS──► Component
Flow ──HAS_SUITE──► TestSuite
TestCase ──IMPLEMENTED_BY──► TestScript
Component ──IMPACTS──► Flow
```

---

## Repo mapping (target)

```text
discovery/uat_ea/          Application KB + GT + recordings
automation/                Approved test scripts & suites (TO BUILD)
src/base_agent/            Shared kernel
src/qa_orchestrator/       Intent classifier + suite runner
plugins/qa_apex/           Playwright + discovery tools
qa-console/                Command center + approval UI
```

---

## Final principle

```text
User → LLM (reason) → Structured Knowledge → Approved Automation → Deterministic Execute → Evidence → LLM (analyze) → Report
```

Not: `User → LLM clicks randomly → Result`
