# AI-Powered Enterprise QA Automation Agent

## Technical & Solution Proposal (Finalized)

**Status:** LOCKED · **Version:** 1.0 · **Date:** September 2026  
**Target application:** Oracle APEX Endless Aisle (Titan / Tanishq UAT)  
**Audience:** Client stakeholders, QA leadership, engineering

---

## Table of contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Proposed Solution](#3-proposed-solution)
4. [Core Architectural Principle](#4-core-architectural-principle)
5. [Application Knowledge Base](#5-application-knowledge-base)
6. [KB Hierarchy](#6-kb-hierarchy)
7. [Business Flow Knowledge](#7-business-flow-knowledge)
8. [Why Flows Beat Pages](#8-why-business-flows-are-more-important-than-pages)
9. [Application Discovery](#9-application-discovery)
10. [APEX-Specific Discovery](#10-apex-specific-discovery)
11. [Scenario → Case → Script → Suite](#11-scenario--test-case--test-script--suite)
12. [LLM-Based Test Generation](#12-llm-based-test-generation)
13. [Human Approval](#13-human-approval)
14. [Automation Repository](#14-automation-repository)
15. [Orchestration](#15-orchestration)
16. [Natural Language Examples](#16-natural-language-example)
17. [Sanity Testing](#17-sanity-testing)
18. [Regression Testing](#18-regression-testing)
19. [Impact-Based Test Selection](#19-impact-based-test-selection)
20. [Self-Healing](#20-self-healing)
21. [Self-Healing Safety](#21-self-healing-safety-model)
22. [Maintenance vs Self-Healing](#22-maintenance-through-application-discovery)
23. [New Product Example](#23-example-new-product)
24. [Capability Comparison Table](#24-difference-between-self-healing-and-maintenance)
25. [Knowledge Graph](#25-knowledge-graph)
26. [Recommended Knowledge Model](#26-recommended-knowledge-model)
27. [Agent Tool Layer](#27-agent-tool-layer)
28. [Example Orchestration](#28-example-orchestration)
29. [Execution Architecture](#29-execution-architecture)
30. [Evidence Collection](#30-evidence-collection)
31. [Failure Analysis](#31-failure-analysis)
32. [Failure Report Example](#32-example-failure-report)
33. [HTTP/API Validation](#33-httpapi-validation)
34. [Multi-Layer QA](#34-multi-layer-qa)
35. [End-to-End Checkout Example](#35-end-to-end-example)
36. [Payment Investigation Example](#36-payment-investigation-example)
37. [New Flow Onboarding](#37-new-flow-onboarding)
38. [Phase 1 Manual Baseline](#38-why-manual-test-writing-is-still-useful-initially)
39. [Role of the LLM](#39-recommended-role-of-the-llm)
40. [What the LLM Must Not Do](#40-what-the-llm-should-not-do)
41. [End-to-End Architecture](#41-proposed-end-to-end-architecture)
42. [Technology Direction](#42-recommended-technology-direction)
43. [Security](#43-security)
44. [Auditability](#44-auditability)
45. [Human-in-the-Loop](#45-human-in-the-loop-model)
46. [Key Benefits](#46-key-benefits)
47. [Design Principle](#47-important-design-principle)
48. [Final Concept Diagram](#48-final-concept)
49. [Operating Model (Four Stages)](#49-proposed-operating-model)
50. [Final Recommendation](#50-final-recommendation)
51. [Architecture Lock Statement](#51-architecture-lock-statement)
52. [Current Platform Inventory & KB Readiness](#52-current-platform-inventory--kb-readiness-assessment)

---

## 1. Executive Summary

The proposed solution is an **AI-powered QA automation platform** designed to understand an enterprise application from its **business flows**, generate and maintain automated test assets, execute tests based on natural-language requests, analyze failures, and continuously adapt to application changes.

The system does **not** replace conventional automation frameworks. It places an intelligent orchestration and knowledge layer **above** deterministic automation tools.

### Core principle

> **Business knowledge is stored in a structured Application Knowledge Base and Knowledge Graph. The LLM is responsible for reasoning, test generation, orchestration, maintenance recommendations, failure analysis, and self-healing. Deterministic tools execute approved automation.**

### Supported requests

- "Run sanity testing for checkout."
- "Payment is not working. Test everything involving payment."
- "Verify the login flow."
- "Check whether the newly added product works across the purchase flow."
- "Product ID 12345 shows 404 in search — why?"

The agent interprets the request, identifies the relevant **business capability and flow**, retrieves approved test suites, selects automation tools, executes tests, analyzes results, and presents **evidence**.

### Platform capabilities

| Capability | Description |
|---|---|
| Application discovery | Human-guided + automated crawl |
| Business-flow modeling | Flow-centric KB, not page-only |
| Test-case generation | LLM from flow knowledge |
| Test-script generation | Playwright/API scripts |
| Test-suite generation | Grouped approved assets |
| Human approval | SME/QA gate before production automation |
| Automated execution | Deterministic suite runner |
| Failure analysis | Evidence-based root cause |
| Locator self-healing | Bounded retry with confidence |
| Change detection | Discovery diff vs model |
| Test maintenance | Impact analysis + LLM recommendations |
| Regression/sanity selection | Graph-driven suite pick |

---

## 2. Problem Statement

Traditional enterprise QA automation suffers from:

### 2.1 Manual test creation

QA engineers manually create scenarios, cases, scripts, suites, locators, and regression packs — expensive as functionality grows.

### 2.2 Automation coupled to UI implementation

A locator change (`#checkout-button` → `#checkout-btn`) breaks tests though business behavior is unchanged.

### 2.3 Fragmented knowledge

Knowledge lives in documents, Excel, TMS, code, APEX metadata, APIs, scripts, and individual engineers — no unified model.

### 2.4 Page-based testing is insufficient

Payment failure requires testing **Checkout, Subscription, Wallet, Buy Now** — not only the Payment page.

### 2.5 Reactive maintenance

UI changes cause failures first; investigation is manual.

### 2.6 NL cannot control conventional automation

"Check the payment flow" requires knowing flows, pages, tests, suites, and tools — the platform provides this layer.

---

## 3. Proposed Solution

An **AI QA Orchestration Layer** over existing automation infrastructure:

```text
                    USER
                     │
                     ▼
             Natural Language
                     │
                     ▼
          ┌────────────────────┐
          │  AI ORCHESTRATOR   │
          │       LLM          │
          └─────────┬──────────┘
                    │
          Intent / Flow / Scope
                    │
                    ▼
       ┌─────────────────────────┐
       │ APPLICATION KNOWLEDGE   │
       │         LAYER           │
       └────────────┬────────────┘
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
 Application     Business      Test
   Model          Flows       Repository
       │            │            │
       └────────────┼────────────┘
                    ▼
              Test Selection
                    │
                    ▼
            Automation Engine
                    │
                    ▼
              UAT Application
                    │
             ┌──────┴──────┐
             ▼             ▼
           PASS           FAIL
                           │
                  ┌────────┴────────┐
                  ▼                 ▼
             Self-Healing      Failure Analysis
                  │
                  ▼
             Retry / Repair
                  │
                  ▼
            Human Approval
```

---

## 4. Core Architectural Principle

Four separated responsibilities:

| # | Layer | Question |
|---|---|---|
| 1 | **Knowledge** | What does the application do? |
| 2 | **Reasoning** | What does the user want? |
| 3 | **Execution** | How do we perform the test? |
| 4 | **Adaptation** | What happens when the app changes or tests fail? |

---

## 5. Application Knowledge Base

The **Application Knowledge Base (KB)** is the foundation.

It must be **flow-centric and business-oriented**, with technical metadata supporting each flow — not merely a collection of scraped pages.

---

## 6. KB Hierarchy

```text
APPLICATION
    │
    ├── BUSINESS CAPABILITIES
    │       ├── Authentication
    │       ├── Product Management
    │       ├── Cart / Checkout
    │       ├── Payment
    │       └── Order Management
    │
    ├── BUSINESS FLOWS
    │       ├── Login
    │       ├── Product Purchase
    │       ├── Find Price
    │       ├── Item Search
    │       └── Checkout
    │
    ├── PAGES
    ├── COMPONENTS
    ├── APIs
    ├── BUSINESS RULES
    └── APPLICATION METADATA
```

> **Business flows are the primary QA unit. Pages and components are supporting technical objects.**

---

## 7. Business Flow Knowledge

Each flow record should contain:

- Flow name, purpose, business capability
- Entry point, preconditions, actors
- Pages and components involved
- Business rules, success/failure states
- Navigation path, test data variants

Example — **Login Flow:** authenticate user; pages Login → Dashboard; rules for valid/invalid/locked accounts; success = dashboard displayed.

This gives the LLM enough context to generate meaningful tests.

---

## 8. Why Business Flows Are More Important Than Pages

Checkout spans: Product → Cart → Address → Payment → Confirmation.

If the client says **"Payment is not working"**, the agent must identify:

```text
Payment Capability → Impacted Flows → Checkout · Subscription · Wallet · Buy Now
```

Then execute **all relevant approved suites** — not only Payment page tests.

---

## 9. Application Discovery

Human-guided discovery: user navigates UAT; system records session.

Captured: URLs, titles, breadcrumbs, buttons, inputs, forms, clicks, navigation, DOM, locators, network, API calls, console errors, screenshots, workflow sequences.

Transformed into structured KB objects.

---

## 10. APEX-Specific Discovery

Combine:

```text
Browser Discovery + APEX Metadata + API Information + Business Knowledge
```

APEX metadata: application, pages, regions, items, buttons, dynamic actions, processes, validations, LOVs, grids, navigation, authorization.

---

## 11. Scenario → Test Case → Test Script → Suite

```text
Business Flow → Scenario → Test Case → Test Script → Test Suite → Execution
```

| Level | Defines |
|---|---|
| **Scenario** | What business behavior to test |
| **Test Case** | Steps, data, expected outcome |
| **Test Script** | Executable automation |
| **Test Suite** | Grouped cases (sanity / regression / flow) |

---

## 12. LLM-Based Test Generation

```text
Flow Knowledge (rules, components, states) → LLM → Scenarios · Cases · Scripts → Suite
```

Generates positive, negative, boundary, validation, and error-handling coverage.

---

## 13. Human Approval

```text
Flow Knowledge → LLM Generation → Generated Suite → Validation → Human Review → Approve/Reject/Edit → Approved Automation Repository
```

Generated automation **never** auto-promotes to production without approval.

---

## 14. Automation Repository

```text
automation/
    authentication/login/
    checkout/
    payment/
    search/
    find_price/
```

Each script links to: capability, flow, scenario, case, pages, components, tags, suite.

**This repository is the execution source of truth.**

---

## 15. Orchestration

The orchestrator converts natural language into an executable plan:

> "Run sanity for checkout."

```text
Intent: SANITY · Capability: Checkout · Flow: Checkout · Suite: Checkout Sanity Suite
```

Retrieves **approved scripts only** — does not regenerate unless discovery/new-feature mode requires it.

---

## 16. Natural Language Example

**User:** "Check payment."

**Orchestrator:**

```text
Intent: Test/investigate · Capability: Payment
Scope: All flows involving payment
Flows: Checkout · Subscription · Wallet · Buy Now
→ Retrieve suites → Execute → Collect → Analyze → Report
```

---

## 17. Sanity Testing

> "Do sanity testing for checkout."

Identifies Checkout flow (Cart → Address → Payment → Confirmation), retrieves **Checkout Sanity Suite**, executes approved sanity tests only.

**Morning scheduled sanity:** run **all** approved sanity suites — **no LLM agent loop** — merge report and send.

---

## 18. Regression Testing

> "Run regression for payment."

Retrieves Payment Regression Suite: successful, declined, invalid card, expired, retry, duplicate, cancellation cases.

---

## 19. Impact-Based Test Selection

When Payment component changes:

```text
Payment Component → Payment Page → Checkout Flow → Purchase Flow → Order Flow
→ Affected test cases → Affected suites → Run impacted subset only
```

---

## 20. Self-Healing

Runtime locator failure:

```text
Failure → Analyze DOM → Find intended element → Candidate locators → Retry
→ If success: suggest permanent fix with confidence score → Human approve
```

Example: `#checkout-button` → `#checkout-btn` at 96% confidence.

---

## 21. Self-Healing Safety Model

| Confidence | Action |
|---|---|
| High | Auto-retry |
| Medium | Retry + flag for review |
| Low | Escalate — no auto-modify |

---

## 22. Maintenance Through Application Discovery

| Trigger | When |
|---|---|
| **Self-healing** | Test fails during execution |
| **Maintenance** | Application itself changed |
| **Discovery** | New/changed application areas |
| **Test generation** | New business flow onboarded |
| **Impact analysis** | Component/flow change detected |

```text
Existing Model + New Discovery → Comparison → Change Detection → Impact → LLM Recommendation → Human Approval
```

---

## 23. Example: New Product

Discovery finds Product D added → maps to Purchase Flow → LLM proposes new purchase test case → human approves → script added to suite.

---

## 24. Difference Between Self-Healing and Maintenance

| Capability | Trigger | Purpose |
|---|---|---|
| Self-Healing | Test failure | Repair execution |
| Maintenance | App change | Keep automation current |
| Discovery | New/changed app | Update application model |
| Test Generation | New flow | Create test assets |
| Impact Analysis | App change | Identify affected tests |

---

## 25. Knowledge Graph

Combine **vector KB** (semantic) with **knowledge graph** (deterministic relationships):

```text
Payment ──USED_BY──► Checkout
Payment ──HAS_TEST_SUITE──► Payment Sanity · Payment Regression
```

Enables: "What tests should I run if payment is broken?"

---

## 26. Recommended Knowledge Model

```text
Application → Capability → Flow → Page → Component
Flow → Scenario → TestCase → TestScript
TestSuite → TestCase
Component → IMPACTS → Flow
API → SUPPORTS → Flow
```

---

## 27. Agent Tool Layer

```text
Agent
 ├── Browser Tool (Playwright)
 ├── API Tool
 ├── Database Tool
 ├── Discovery Tool
 ├── KB Retrieval Tool
 ├── Test Execution Tool
 ├── Evidence Tool
 └── Self-Healing Tool
```

LLM selects tools; tools perform deterministic operations.

---

## 28. Example Orchestration

**User:** "Payment is not working."

1. Identify capability = Payment  
2. Graph traverse impacted flows  
3. Retrieve associated approved suites  
4. Execute all payment-involved tests  
5. Collect evidence  
6. Analyze failures  
7. Attempt permitted self-healing  
8. Produce report  

LLM creates the plan — it does not randomly click the UI.

---

## 29. Execution Architecture

```text
ORCHESTRATOR → Execution Plan → Test Execution API
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
    Browser Agent           API Agent
    (Playwright)            (REST)
         │                     │
         └──────────┬──────────┘
                    ▼
                   UAT
```

---

## 30. Evidence Collection

Every run produces: screenshots, DOM snapshot, network trace, API response, console log, execution video/trace.

**Evidence validates results — not LLM opinion.**

---

## 31. Failure Analysis

Classify: locator issue · UI change · API failure · data issue · environment · business-rule change · genuine defect.

LLM analyzes collected evidence for probable root cause.

---

## 32. Example Failure Report

Structured report with: test name, failed step, network (HTTP 500), self-healing status, probable root cause, recommendation, attached evidence.

Not merely: "Payment test failed."

---

## 33. HTTP/API Validation

Validate status codes (200, 400, 401, 403, 404, 409, 500) to distinguish UI vs backend failures.

---

## 34. Multi-Layer QA

```text
UI → API → Database
```

Example payment: confirmation UI + payment API success + order record created.

---

## 35. End-to-End Example

**User:** "Run checkout sanity."

Classify → Sanity → Checkout Flow → Checkout Sanity Suite → Execute steps → Evidence → Per-step pass/fail report.

---

## 36. Payment Investigation Example

**User:** "Payment is not working."

Graph query returns Checkout, Subscription, Wallet, Buy Now suites → execute all → combined incident report.

This matches the client requirement: **test complete flows involving payment, not one page.**

---

## 37. New Flow Onboarding

```text
New Flow → Discovery → KB → LLM Generate → Human Approve → Automation Repository → Available to orchestrator
```

---

## 38. Why Manual Test Writing Is Still Useful Initially

**Phase 1:** QA manually validates Login, Checkout, Payment, Product Purchase — golden baseline.

**Phase 2:** New flows use KB → LLM generation → approval.

---

## 39. Recommended Role of the LLM

**LLM:** intent classification, flow ID, suite selection reasoning, generation, failure analysis, maintenance recommendations, self-healing reasoning, NL reporting.

**Deterministic:** browser, API, DB, execution, evidence, storage, GT compare.

---

## 40. What the LLM Should NOT Do

- Randomly modify production automation  
- Invent application behavior  
- Assume pages exist without KB  
- Rewrite large test sets without validation  
- Declare PASS without execution evidence  
- Replace deterministic automation unnecessarily  

> **LLM reasons; tools execute; evidence validates.**

---

## 41. Proposed End-to-End Architecture

```text
USER → NL → ORCHESTRATOR (LLM)
              │
    Intent · Target · Test Type
              │
    KB + Graph + Test Repo → Test Selection
              │
    Execution Layer (Browser · API · DB) → UAT
              │
    Evidence → PASS / FAIL → Self-Heal · Analysis → Report

Parallel path:
UAT → Discovery Agent → Application Model → Change Detection → Impact → LLM Recommendation → Human Approval → KB / Test Repo
```

---

## 42. Recommended Technology Direction

| Layer | Choice |
|---|---|
| Browser | **Playwright** |
| Backend | Python agent API, KB API, execution API, discovery API |
| Knowledge | Relational DB + vector store + graph representation |
| LLM | Enterprise gateway (Groq → Claude / client choice) — never system of record |
| Console | Next.js TypeScript UI |
| CI/CD | Azure Pipelines → OCI containers |

---

## 43. Security

Credentials: encrypted, vault-stored, never in prompts or LLM history, masked in logs, minimum permissions.

---

## 44. Auditability

Every AI-generated change: change ID, reason, old/new locator, confidence, approver, timestamp.

---

## 45. Human-in-the-Loop Model

Human approval required for: new suites, permanent self-heal changes, test deletion, major modifications, business-rule changes.

---

## 46. Key Benefits

- Reduced manual test authoring  
- Faster flow onboarding  
- Intelligent capability/flow-based test selection  
- Proactive maintenance via discovery  
- Self-healing for minor UI drift  
- Multi-layer defect analysis (UI + API + DB)  
- Reusable approved automation assets  

---

## 47. Important Design Principle

**Avoid:** User → LLM clicks randomly → Result

**Use:** User → LLM → Structured Knowledge → Approved Automation → Deterministic Execution → Evidence → LLM Analysis

---

## 48. Final Concept

```text
APPLICATION → DISCOVERY → KNOWLEDGE MODEL → LLM (Generate · Reason · Maintain)
    → HUMAN APPROVAL → AUTOMATION REPO → ORCHESTRATOR → EXECUTION → UAT
    → PASS / FAIL → Self-Heal · Root Cause → REPORT
```

---

## 49. Proposed Operating Model

| Stage | Flow |
|---|---|
| **Discover** | UAT → Browser + APEX metadata → Application Model |
| **Generate** | Business Flow → LLM → Scenario/Case/Script/Suite → Human Approval |
| **Execute** | User Request → Orchestrator → Suite Selection → Automation → Evidence |
| **Adapt** | App Change → Discovery → Impact → LLM Recommendation → Human Approval → Updated Automation |

---

## 50. Final Recommendation

Flow-centric platform where:

- KB describes application and business flows  
- LLM understands intent and generates testing artifacts  
- Humans approve before assets become official  
- Orchestrator selects **existing approved automation** whenever possible  
- Automation engine executes deterministically  
- Self-healing handles runtime locator failures  
- Discovery and maintenance handle application changes  
- Knowledge Graph connects capabilities, flows, pages, components, tests, and automation  

Full lifecycle:

```text
DISCOVER → UNDERSTAND → MODEL → GENERATE → APPROVE → EXECUTE → ANALYZE → SELF-HEAL → MAINTAIN → LEARN / UPDATE
```

---

## 51. Architecture Lock Statement

**This proposal is the locked architecture baseline for the Apex QA Agent platform.**

All future development must align with:

1. **Flow-centric KB** — business flows are the primary QA unit  
2. **Approved automation repository** — execution runs approved suites, not ad-hoc LLM browsing  
3. **Orchestrator classification** — every NL prompt maps to intent, capability, flow scope, and suite set  
4. **Deterministic execution** — Playwright/API/DB tools execute; LLM does not click UI in production runs  
5. **Human approval gates** — generated tests, self-heal permanence, GT facts  
6. **Evidence-based reporting** — PASS/FAIL requires execution artifacts  
7. **Morning sanity without LLM** — scheduled run of all sanity suites, merged report  

See also: [ARCHITECTURE_LOCKED.md](./ARCHITECTURE_LOCKED.md)

---

## 52. Current Platform Inventory & KB Readiness Assessment

*Assessment date: September 2026 · Application: Endless Aisle UAT*

### 52.1 What we already have (built)

| Asset | Location | Status |
|---|---|---|
| Enterprise QA console | `qa-console/` | **Built** — command center, schedule, alerts, model picker, live traces, report routing |
| Shared agent kernel | `src/base_agent/` | **Built** — budgets, decision engine, LLM gateway, GT/KB protocols, LangGraph |
| QA orchestrator (thin) | `src/qa_orchestrator/` | **Partial** — planner, validator, reporter; needs intent classifier + suite runner |
| QA APEX plugin | `plugins/qa_apex/` | **Built** — Playwright crawler, skills, flow replay, sanity probes |
| Application discovery | `plugins/qa_apex/crawler/` + recordings | **Built** — automated crawl + 2 merged browser recordings |
| Local runtime server | `scripts/local_agent_server.py` | **Built** |
| Morning patrol script | `scripts/morning_patrol.py` | **Partial** — needs suite-runner integration |
| GT/KB specifications | `docs/APEX_GT_KB_COLLECTION_SPEC.md` | **Built** |
| CI/CD skeleton | `azure-pipelines.yml`, `deploy/Dockerfile` | **Built** |
| Unit tests | `tests/unit/` (26 tests) | **Passing** |
| Team meeting brief | `docs/meeting/TEAM_MEETING_ARCHITECTURE.pdf` | **Published** |

### 52.2 Application Knowledge Base — inventory

| KB asset | Count | Status | Notes |
|---|---:|---|---|
| Total KB documents | **64** | Candidate | Not yet promoted to approved GT |
| Business overview | 1 | Candidate | App ID 1002, workspace tjdcom, UAT URLs |
| Business flows | **12** | Candidate | From recordings + discovery |
| Page maps | **44** | Candidate | URLs, headings, buttons, fields |
| Components (field-level) | **6** | Candidate | P6_SKU, P31_ITEM, P47_SKU, etc. |
| APEX UI patterns | **5** | Candidate | auth_home, modal, grid, LOV, list/detail |
| Home navigation modules | **20** | Observed | All Products, Item Search, Rivaah, Find Price, … |
| Normalized KB catalog | **64** | Built | `kb_normalized/` by pages/flows/components |
| Browser recordings | **2** | Merged | ~5 min + ~35 min sessions |
| GT candidates | **22** | **Proposed** | Awaiting SME approval today |
| Approved GT facts | **0** | **Gap** | `discovery/uat_ea/gt/` pending SME session |

#### Flows captured (12)

| Flow | Source |
|---|---|
| login_to_home | Recording + discovery |
| find_price_lookup | Recording |
| item_sku_or_qr_search | Recording |
| item_code_or_qr_search | Recording |
| stock_visibility_search | Recording |
| standard_product_browse | Discovery |
| browse_all_products | Discovery |
| best_deal_product_detail | Recording |
| category_earrings_browse | Discovery |
| rivaah_wedding_browse | Discovery |
| rivaah_wedding_trousseau | Recording |
| reports_submenu_browse | Recording |

#### Pages with strong coverage

Login, home, find-price, standard-product-search, product-detail, stock visibility, estimation slip, rivaah, wedding trousseau, customer wishlist, administration, and 30+ ea/ea1 module pages from crawl + recordings.

#### Known gaps in KB (vs proposal model)

| Gap | Impact |
|---|---|
| **Business capability layer** not explicit | Orchestrator cannot yet map "payment" → multi-flow graph |
| **Checkout / payment multi-page flow** incomplete | Customer Order / payment chain under-documented |
| **Knowledge graph edges** not stored | No `Capability → Flow → Suite` relationships in DB |
| **Business rules per flow** shallow | Flow JSON has steps, not full rule/precondition model |
| **API layer** not in KB | No REST endpoint mapping for multi-layer QA |
| **Scenario/case/script hierarchy** absent | No linked test artifacts in KB yet |

### 52.3 Readiness vs proposal layers

| Proposal layer | Readiness | Score | Notes |
|---|---|---:|---|
| Application discovery | Strong | **75%** | Crawler + recordings + page maps |
| Flow-centric KB | Medium | **55%** | 12 flows; need richer flow metadata + capabilities |
| Page/component KB | Good | **70%** | 44 pages, 6 components, 5 APEX patterns |
| Knowledge graph | Missing | **15%** | Needs explicit relationship store |
| Automation repository | Missing | **5%** | No `automation/` approved suites yet |
| LLM test generation | Not built | **10%** | Spec + planner stub only |
| Orchestrator intent classification | Partial | **35%** | Basic planner; needs intent taxonomy |
| Deterministic suite execution | Partial | **40%** | Skills exist; not unified suite runner |
| Morning sanity (no LLM) | Partial | **30%** | Script exists; needs all-suite merge |
| Self-healing | Not built | **5%** | Documented only |
| Maintenance / change detection | Not built | **10%** | Discovery diff not implemented |
| Human approval workflow | Partial | **45%** | APPROVAL_CHECKLIST + console; no gen-test UI |
| GT / expected behavior | Partial | **40%** | 22 candidates; 0 approved |
| Evidence collection | Partial | **50%** | Screenshots in crawler; no full bundle standard |
| Failure analysis | Partial | **25%** | Structured conclusions; no root-cause engine |
| Enterprise console | Strong | **80%** | Dark UI, channels, schedule, traces |

### 52.4 Overall KB richness for this approach

```text
┌────────────────────────────────────────────────────────────┐
│  OVERALL READINESS: ~45% toward finalized proposal model   │
├────────────────────────────────────────────────────────────┤
│  STRONG:  page discovery, flow seeds, console, runtime   │
│  MEDIUM:  flow metadata, GT candidates, plugin skills      │
│  WEAK:    capability graph, automation repo, self-heal     │
│  MISSING: approved suites, graph DB, API/DB test layer     │
└────────────────────────────────────────────────────────────┘
```

**Interpretation:** Our KB is a **solid discovery and flow-seed foundation** — richer than a raw page scrape, with real UAT flows from SME recordings. It is **not yet** the full flow-centric knowledge graph + automation repository the proposal requires. The gap is structural (capabilities, graph edges, approved scripts), not absence of UAT knowledge.

### 52.5 Recommended next steps (priority order)

1. **SME session today** — approve GT candidates → enable deterministic validation  
2. **Define capability map** — map 20 home modules to capabilities and flows  
3. **Create `automation/` repository** — Phase 1 manual golden suites (Login, Find Price, Item Search, Home Sanity)  
4. **Build orchestrator intent taxonomy** — `SANITY | ADHOC_EXISTING | ADHOC_PARAM | INCIDENT | NEW_FEATURE`  
5. **Wire morning patrol** — run all sanity suites, zero LLM, merged report  
6. **Knowledge graph schema** — Capability→Flow→Page→Suite edges in relational model  
7. **LLM test generation pipeline** — flow KB → draft cases → console approval UI  
8. **Self-healing MVP** — locator retry with confidence + audit log  

### 52.6 What the client can see today

- Working local demo console with NL command interface  
- 64-document KB pack from real UAT exploration  
- 12 recorded business flows and 44 page maps  
- 22 GT candidates ready for SME sign-off  
- Architecture proposal (this document) locked and aligned to discussed requirements  

---

*End of finalized proposal.*
