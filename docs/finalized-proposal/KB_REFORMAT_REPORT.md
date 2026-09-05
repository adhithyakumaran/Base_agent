# KB Reformat Report — Flow-Centric Canonical Model

**Date:** 5 September 2026  
**Architecture lock:** [AI_POWERED_QA_AUTOMATION_PROPOSAL.md](./AI_POWERED_QA_AUTOMATION_PROPOSAL.md)  
**Action taken:** Reformat KB only — no orchestrator/automation build

---

## 1. Executive summary

Your **3 manually formatted flow KBs** are exactly what the finalized architecture requires. They were imported as the **canonical READY standard**. The old 64-document JSON pack is **archived** (still useful as discovery reference) but is no longer the primary KB shape.

| Metric | Before | After |
|---|---|---|
| Canonical format | Clumsy JSON (page/flow seeds) | **Flow-centric YAML** |
| SME-ready flows | 0 | **3 (READY)** |
| Draft migrated flows | — | **12** |
| Legacy JSON archive | Primary | **Archived** (`kb/README.md`) |

---

## 2. Do your 3 manual KBs help?

**Yes — significantly.** They are the template the whole platform needs.

| Your file | Imported as | Why it helps |
|---|---|---|
| BF-LOGIN-001 (Login) | `discovery/uat_ea/flows/BF-LOGIN-001.yaml` | Full business rules, locators (primary+3 fallbacks), self-healing policy, unknown-rule honesty |
| F002 (Logout) | `BF-LOGOUT-002.yaml` | Session termination rules, back-navigation security checks |
| F003 (Search Product) | `BF-PRODUCT-003.yaml` | Parameterized search (14-digit SKU), stock states, test scenarios list |

Compared to old JSON (example `flow.login_home.json`):

```json
"steps": [{"page": "login", "action": "enter_username_password"}, {"page": "home", "action": "land"}]
```

Your YAML adds: **purpose, preconditions, components, locators, business rules, automation block, security, evidence, status** — everything the proposal §7–§14 requires.

**QA Agent KB Information Collection PDF** aligns with your format:

- Category A/B → `components`, `technical_metadata`, `automation`
- Category C → `business_rules`, `expected_success`, `unknown_business_rules`
- Ownership → human approval before automation promotion

---

## 3. What we changed (KB only)

### 3.1 New canonical structure

```text
discovery/uat_ea/
├── KB_FORMAT.md              ← Format spec (locked)
├── capabilities.yaml         ← Capability → flow map (draft)
├── flows/
│   ├── index.yaml            ← Catalog of all flows + status
│   ├── BF-LOGIN-001.yaml     ← READY (your manual KB)
│   ├── BF-LOGOUT-002.yaml    ← READY (your manual KB)
│   ├── BF-PRODUCT-003.yaml   ← READY (your manual KB)
│   └── BF-*.yaml             ← 12 DRAFT flows migrated from legacy JSON
├── kb/                       ← LEGACY JSON archive (64 docs)
│   └── README.md
├── kb_normalized/            ← unchanged normalized catalog
├── candidate_gt/             ← unchanged GT candidates
└── recordings/               ← unchanged browser recordings
```

### 3.2 Flow inventory

| Flow ID | Name | Status | Source |
|---|---|---|---|
| **BF-LOGIN-001** | User Login | **READY** | SME manual KB |
| **BF-LOGOUT-002** | User Logout | **READY** | SME manual KB |
| **BF-PRODUCT-003** | Search Product | **READY** | SME manual KB |
| BF-FINDPRICE-004 | Find Price Lookup | DRAFT | Legacy migration |
| BF-LOGIN-HOME-005 | Login To Home | DRAFT | Superseded by BF-LOGIN-001 |
| BF-STOCKVIS-006 | Stock Visibility | DRAFT | Legacy migration |
| BF-ITEMSEARCH-007 | Item SKU (legacy path) | SUPERSEDED | → BF-PRODUCT-003 |
| BF-BESTDEAL-008 | Best Deal Detail | DRAFT | Legacy migration |
| BF-BROWSE-009 | Browse All Products | DRAFT | Legacy migration |
| BF-CAT-EAR-010 | Category Earrings | DRAFT | Legacy migration |
| BF-ITEMCODE-011 | Item Code Search | DRAFT | Legacy migration |
| BF-REPORTS-012 | Reports Menu | DRAFT | Legacy migration |
| BF-RIVAAH-013 | Rivaah Browse | DRAFT | Legacy migration |
| BF-RIVAAH-TRO-014 | Rivaah Trousseau | DRAFT | Legacy migration |
| BF-STD-BROWSE-015 | Standard Product Browse | DRAFT | Legacy migration |

**Total flows in catalog:** 15 (3 READY · 11 DRAFT · 1 SUPERSEDED)

---

## 4. KB richness — revised assessment

### 4.1 Old assessment (~45% ready)

Based on clumsy JSON only — flow metadata was shallow.

### 4.2 New assessment (with your 3 READY flows)

| Layer | Before | Now | Notes |
|---|---:|---:|---|
| Flow-centric KB (READY quality) | 5% | **35%** | 3 flows at full proposal depth |
| Locator + self-heal metadata | 10% | **40%** | Primary+3 fallbacks on READY flows |
| Business rules (numbered) | 15% | **45%** | 22+ rules across 3 flows |
| Capability map | 0% | **20%** | `capabilities.yaml` draft |
| Legacy page/flow seeds | 70% | **70%** | Still valid as enrichment source |
| Knowledge graph edges | 15% | **25%** | Capability→flow started |
| Automation repository | 5% | 5% | Not in scope this task |
| **Overall toward proposal** | **~45%** | **~55%** | +10 pts from format + SME flows |

### 4.3 What the 3 READY flows unlock immediately

| Proposal capability | Unlocked? |
|---|---|
| Orchestrator: "verify login" | Yes — BF-LOGIN-001 |
| Orchestrator: "check logout / session" | Yes — BF-LOGOUT-002 |
| Adhoc param: "product ID X in search" | Yes — BF-PRODUCT-003 + `test_data` refs |
| LLM test generation from flow knowledge | Yes — for these 3 flows |
| Self-healing locator policy | Yes — defined in YAML |
| Morning sanity (all suites) | Partial — need suites built from READY flows |
| Incident: "payment failing" | No — Payment capability empty |
| New feature crawl + suggest tests | Partial — discovery archive exists |

---

## 5. Gap analysis (what still needs SME work)

| Priority | Gap | Action |
|---|---|---|
| P0 | **Payment / Checkout / Customer Order** flows missing | SME session — no capability for incident orchestration |
| P1 | **11 DRAFT flows** need enrichment to READY | Use BF-LOGIN-001 as template; pull locators from legacy JSON + recordings |
| P1 | Find Price (BF-FINDPRICE-004) | High client value — enrich next after search |
| P2 | Home module sanity map | Link 20 home modules → capabilities in `capabilities.yaml` |
| P2 | GT approval | 22 candidates still proposed — link approved GT to flow `business_rules` |
| P3 | APEX metadata import | Page items from APEX dev env for DRAFT flows |

---

## 6. Architecture lock confirmation

No architecture change — this KB reformat **implements** the locked proposal:

- Flow-centric KB (§6–§8)  
- Scenario → case → script → suite path (§11) — READY flows have `automation.test_scenarios` seeds  
- Human approval before automation (§13) — `status: READY` = SME approved knowledge  
- Self-healing policy (§20–§21) — in every READY flow  
- Knowledge graph start (§25) — `capabilities.yaml`

**Canonical paths going forward:**

| Asset | Path |
|---|---|
| Architecture | `docs/finalized-proposal/` |
| Flow KB | `discovery/uat_ea/flows/` |
| KB format spec | `discovery/uat_ea/KB_FORMAT.md` |
| Legacy archive | `discovery/uat_ea/kb/` |

---

## 7. Recommended next steps (KB only — no build)

1. SME review BF-LOGIN-001, BF-LOGOUT-002, BF-PRODUCT-003 — mark **APPROVED** in git when signed off  
2. Enrich **BF-FINDPRICE-004** to READY using same template  
3. SME workshop: **Payment / Customer Order** flow KB (unblocks incident prompts)  
4. Convert 22 GT candidates → link as `business_rules` refs inside READY flows  
5. Deprecate references in code/docs from `discovery/uat_ea/kb/index.json` → `flows/index.yaml`

---

## 8. Bottom line

- **Your 3 manual KBs are the correct format** — imported and locked as canonical.  
- **Old KB was rich but clumsy** — now organized: READY SME flows + DRAFT migrations + legacy archive.  
- **Readiness improved ~45% → ~55%** toward the finalized proposal model.  
- **Biggest remaining gap:** Payment/Checkout flows and enriching 11 DRAFT flows to READY standard.

No orchestrator, automation suite, or console changes were made in this task — KB and documentation only.
