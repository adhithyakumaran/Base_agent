# Oracle APEX Inventory — Ground Truth & Knowledge Collection Spec

**Document type:** Planning specification (no implementation)  
**Date:** 1 September 2026  
**Depends on:** [BASE_AGENT_TECHNICAL_PROPOSAL.md](./BASE_AGENT_TECHNICAL_PROPOSAL.md)  
**Target use case:** QA Agent (then Security Agent) for an Oracle APEX inventory / endless-aisle style application  
**Principle:** Evidence-driven validation — deterministic-first, LLM-when-required

---

## 1. Purpose

This document defines **exactly** how Knowledge Base (KB) and Ground Truth (GT) are collected, stored, approved, versioned, and used for an Oracle APEX inventory application — without requiring the client to supply detailed test cases, wireframes, or continuous SME support.

It answers:

1. What is KB vs GT vs rules vs observations?
2. What records do we store (schemas)?
3. How does discovery populate KB?
4. How does something become approved GT?
5. What does the APEX playground contain, and which GT fixtures ship with it?
6. How do we stay efficient (fewer LLM calls over time)?

**Out of scope here:** implementing the Base Agent, Playwright crawler, or client production access.

---

## 2. Evidence hierarchy (non-negotiable)

| Rank | Layer | Authority | Can decide PASS/FAIL alone? |
|---:|---|---|---|
| 1 | **Ground Truth** | Authoritative expected behaviour | Yes |
| 2 | **Deterministic rules / schemas** | Objective checks (HTTP, required fields, DB constraints, UI error page) | Yes, for that check |
| 3 | **Knowledge Base** | Advisory application understanding | No — supports planning/routing only |
| 4 | **LLM interpretation** | Bounded reasoning on unfamiliar observations | No — must not invent expected behaviour |

**Golden rule:** The LLM may help explain *what happened*. It must never silently decide *what should have happened*.

Valid terminals when evidence is weak: `UNKNOWN`, `INSUFFICIENT_EVIDENCE`.

---

## 3. Core distinction: Observation ≠ Truth

```text
Observation / crawl result
        ↓
Candidate Knowledge          (advisory, auto-writable)
        ↓
Candidate Expectation        (proposed expected behaviour — NOT yet GT)
        ↓
Approval gate                (human / domain rule / playground author / golden baseline)
        ↓
Approved Ground Truth        (authoritative, versioned)
        ↓
Deterministic validation on future runs  →  PASS / FAIL  (typically 0 LLM calls)
```

**Forbidden:** auto-promoting “seen N times” into GT. A persistent bug would become “correct.”

---

## 4. Record schemas

All IDs are stable strings. Timestamps are ISO-8601. Every record is **versioned** (immutable versions; updates create `n+1`).

### 4.1 Common metadata

```yaml
meta:
  id: string                 # e.g. kb.page.products
  version: string            # semver or monotonic "3"
  env: playground|uat|prod
  app_id: string|null        # APEX application id when known
  source: discovery|apex_metadata|api|db|feature_doc|human|golden_run|playground_seed
  created_at: datetime
  updated_at: datetime
  created_by: agent|human|<user_id>
  confidence: 0.0-1.0        # for candidates only; GT ignores this for authority
  tags: [inventory, cart, ...]
  content_hash: string       # hash of body for change detection
```

### 4.2 Knowledge Base records

KB is **advisory**. Runtime may use it for routing, exploration planning, and context packets. It must **not** alone produce PASS/FAIL.

#### `KnowledgeDocument` (envelope)

```yaml
kind: knowledge
status: candidate|active|stale|superseded|rejected
meta: <common>
body:
  type: page_map|component|flow|message|api_endpoint|data_entity|business_note|session_note
  title: string
  summary: string
  details: object            # type-specific payload
  related_ids: [string]      # other kb/gt ids
  stale_after: datetime|null
  conflict_group: string|null  # same group + contradicting details → conflict
```

#### Type-specific `details` (inventory / APEX)

**`page_map`**

```yaml
details:
  apex_page_id: 10
  page_alias: PRODUCTS
  title: Products
  url_path: /ords/r/<workspace>/<app>/products
  auth_required: true
  regions: [{name: Products IG, type: interactive_grid}]
  primary_items: [P10_SEARCH, P10_SKU]
  primary_buttons: [ADD_TO_CART, SEARCH]
```

**`component`**

```yaml
details:
  page_id: 10
  component_type: interactive_grid|button|item|region|dynamic_action|list
  name: Products IG
  apex_static_id: products_ig
  locators_hint:                 # advisory only; self-healing later
    - css: "#products_ig"
    - aria: "Products"
  observable_behaviours: ["filterable", "row_select"]
```

**`flow`** (inferred journey — still KB until approved as GT workflow)

```yaml
details:
  name: add_to_cart_basic
  steps:
    - {page: LOGIN, action: authenticate}
    - {page: PRODUCTS, action: search_sku}
    - {page: PRODUCTS, action: add_to_cart}
    - {page: CART, action: assert_line_visible}
  evidence_of_inference: discovery_run_id
```

**`message`**

```yaml
details:
  text: "Added successfully"
  context: after_add_to_cart
  severity: info|warning|error
```

**`api_endpoint`**

```yaml
details:
  method: POST
  path: /ords/.../cart/items
  request_fields: [sku, qty]
  observed_status: [200, 400]
```

**`data_entity`**

```yaml
details:
  name: CART_ITEM
  keys: [cart_id, sku]
  observed_fields: [qty, unit_price, line_total]
```

### 4.3 Candidate Expectation

Proposed expected behaviour. **Not authoritative.**

```yaml
kind: candidate_expectation
status: proposed|approved|rejected|expired
meta: <common>
body:
  subject: promo.banner.visibility     # stable subject key
  predicate: visible_between
  expected:
    start: "09:00"
    end: "18:00"
    tz: Asia/Kolkata
  applies_when:
    page: HOME
  rationale: "Observed consistently during discovery; needs approval"
  supporting_kb_ids: [kb.message.banner, kb.page.home]
  supporting_run_ids: [run_123]
  risk_if_wrong: "Would hide a real banner defect outside hours"
```

### 4.4 Ground Truth records

```yaml
kind: ground_truth
status: active|retired|superseded
authority: approved
meta: <common>                         # source must be approval path, not raw discovery
body:
  subject: string
  predicate: string
  expected: object|scalar|list
  applies_when: object                 # context predicates (time, role, page, env, stock>0, ...)
  compare:
    mode: equals|range|regex|exists|not_exists|expr|set_contains
    expr: string|null                  # e.g. "actual.qty == 1 and actual.db_row_exists == true"
  severity_on_fail: blocker|major|minor
  evidence_required: [ui, db, api]     # which observation channels needed
  related_kb_ids: [string]
  approved_by: string
  approved_at: datetime
  approval_ticket: string|null
```

### 4.5 Deterministic Rule (not GT, but first-class)

Rules fire without approval of business intent — they check objective properties.

```yaml
kind: rule
status: active
meta: <common>
body:
  id: rule.apex.no_internal_error
  scope: every_page_load
  check:
    type: ui_not_contains
    patterns: ["ORA-", "Unexpected error", "APEX error"]
  on_fail: FAIL
  llm: never
```

### 4.6 Evidence & Validation report

```yaml
kind: evidence
meta: <common>
body:
  run_id: string
  observation_ids: [string]
  artifact_refs: [screenshot_hash, har_hash, sql_result_hash]
  redaction: applied|none

kind: validation_report
body:
  outcome: pass|fail|not_applicable|insufficient
  gt_id: string|null
  rule_id: string|null
  expected: any
  actual: any
  reason_code: string          # expected_absence | stock_not_decremented | ...
  evidence_ids: [string]
```

### 4.7 Agent result (reminder)

Conclusions allowed: `PASS` | `FAIL` | `BLOCKED` | `UNKNOWN` | `INSUFFICIENT_EVIDENCE`.

---

## 5. How Knowledge is collected (Oracle APEX)

### 5.1 Collection channels

| Channel | What we get | Client dependency | Determinism |
|---|---|---|---|
| **A. URL + credentials crawl** | Pages, nav, regions, items, buttons, messages, rough flows | Minimum (client already promised) | Medium (DOM varies) |
| **B. APEX metadata SQL** (UAT read-only) | Exact page/region/item/button/DA/process catalog | Ask once for UAT | **High — prefer this** |
| **C. ORDS / REST** | Endpoints, methods, schemas | If exposed | High |
| **D. DB dictionary / constraints** | Tables, FKs, check constraints | UAT read | High |
| **E. Feature document** | Intent of a change | Client provides on change | High for that feature |
| **F. High-level business overview** | Domain language | Optional supplementary | Low volume |
| **G. Playground seed** | Full controlled map | None (we own it) | Highest for R&D |

### 5.2 Preferred APEX metadata objects (UAT)

When granted, discovery should prefer metadata over DOM guessing:

- `apex_applications`
- `apex_application_pages`
- `apex_application_page_regions`
- `apex_application_page_items`
- `apex_application_page_buttons`
- `apex_application_page_da` / `_da_actions` / `_da_events`
- `apex_application_processes` / page processes
- authentication schemes, lists, LOVs (as available)

DOM crawl remains required for **runtime behaviour** (what the user actually sees after Dynamic Actions).

### 5.3 Discovery run policy (efficiency)

1. One discovery pass builds/updates **KB candidates** only.
2. Cap pages/components per run (budget).
3. Diff against previous KB versions via `content_hash` → only changed nodes update.
4. Do **not** call LLM per component; LLM only for clustering ambiguous labels into flows when metadata is insufficient.
5. Emit a **Candidate Expectation queue** for behaviours that look rule-like (messages, time windows, required fields) — still not GT.

### 5.4 What goes into KB for inventory (minimum set)

- Page map (Home, Products, Product Detail, Cart, Checkout, Orders, Admin if visible)
- Search / filter components
- Add / update / remove cart actions
- Stock / availability indicators
- Checkout / payment result messages (observed text only)
- Roles visible to the test user (store associate vs admin)
- Key entities: PRODUCT, CART_ITEM, ORDER, STOCK

---

## 6. How Ground Truth is collected

### 6.1 Allowed GT origin paths

| Path | Who approves | When to use |
|---|---|---|
| **P1. Playground seed** | Engineering (we own the app) | Now — R&D, demos, benchmarks |
| **P2. Feature document → GT extract** | Tech lead + light client confirm if ambiguous | On every new/changed feature (QA-04) |
| **P3. Golden baseline approve** | Client/business user clicks “Approve run as expected” | After a good UAT sanity/regression run |
| **P4. Candidate expectation approve** | Review queue (client or internal domain owner) | Promote discovered behaviours without writing test cases |
| **P5. Authoritative system rule** | DB constraint / API contract imported as GT or Rule | When UAT schema/API access exists |

**Not allowed:** crawler alone, frequency counting, LLM-written expected values.

### 6.2 Approval workflow

```text
                    ┌──────────────────────┐
  Discovery ───────►│ Candidate Knowledge  │
                    └──────────┬───────────┘
                               │ optional
                               ▼
                    ┌──────────────────────┐
                    │ Candidate Expectation│
                    └──────────┬───────────┘
           reject              │ approve
              │                ▼
              ▼     ┌──────────────────────┐
           archive  │ Ground Truth vN      │──► GroundTruthProvider
                    └──────────────────────┘
                               │
                    retire / supersede on app change
```

**Approval UI (product requirement for later — not Week 1 core):**

- Show: subject, expected, applies_when, supporting screenshots/KB links
- Actions: Approve → GT, Reject, Edit then Approve, Defer
- Approver identity + timestamp mandatory
- Diff view when superseding GT after a feature change

**Golden run approve:**

1. Agent executes flow in UAT with evidence.
2. Human reviews evidence pack (not raw logs).
3. “Approve as sanity baseline” writes GT subjects for that flow’s checkpoints.
4. Daily sanity compares against that baseline (deterministic).

### 6.3 Contextual GT (banner pattern — required behaviour)

```yaml
subject: promo.banner.visibility
predicate: visible_between
expected: {start: "09:00", end: "18:00", tz: "Asia/Kolkata"}
applies_when: {page: HOME}
compare:
  mode: expr
  expr: |
    (env.local_time in range) == actual.banner_visible
```

At 21:00 + banner absent → **PASS** (`reason_code: expected_absence`), **0 LLM**.

### 6.4 Inventory GT subjects (starter catalogue)

Use these subject keys consistently across playground and UAT:

| Subject | Predicate | Expected (playground default) |
|---|---|---|
| `auth.login` | `succeeds_with_valid_creds` | `true` |
| `page.products.exists` | `reachable` | `true` |
| `cart.add_item` | `ui_and_db_consistent` | `{ui_success: true, db_row_exists: true, qty: 1}` |
| `cart.line_total` | `equals_qty_times_price` | `true` |
| `stock.decrement_on_order` | `qty_delta` | `{delta: -ordered_qty}` |
| `stock.block_when_zero` | `checkout_blocked` | `true` |
| `order.create` | `persists` | `{status: PLACED}` |
| `promo.banner.visibility` | `visible_between` | `09:00–18:00` |
| `role.associate.forbid_admin` | `page_not_accessible` | `true` |

Security Agent later extends subjects (`session.fixation`, `authz.idor`, …) on the **same** GT store shape.

---

## 7. Deterministic rules pack (Oracle APEX defaults)

Ship these as rules (always on), independent of business GT:

| Rule ID | Check | On fail |
|---|---|---|
| `rule.apex.no_ora_error` | Page source/text lacks ORA-/APEX unexpected error | FAIL |
| `rule.http.not_5xx` | Main document not 5xx | FAIL |
| `rule.session.alive` | Post-login session cookie/valid APEX session | FAIL/BLOCKED |
| `rule.form.required_fields` | Empty submit shows client/server validation when metadata marks required | FAIL if metadata says required |
| `rule.ui_db.success_implies_row` | If GT/skill asserts persistence, UI success requires DB row | FAIL |
| `rule.schema.json` | ORDS response matches registered schema | FAIL |

Rules keep early runs useful even when GT is sparse.

---

## 8. APEX QA Playground specification

### 8.1 Why

Client Endless Aisle / inventory production must not be the permanent sandbox. Playground gives curated GT, intentional defects, and repeatable benchmarks.

### 8.2 Scope of the playground app

Representative **inventory / endless-aisle** APEX app (inspired by requirements, **not** a proprietary clone):

| Module | Purpose |
|---|---|
| Login / roles | Associate vs Manager |
| Dashboard | Entry + promo banner (time-based) |
| Products | Search, filter, detail |
| Cart | Add/update/remove |
| Checkout | Place order, stock check |
| Orders | List / detail |
| Admin (manager only) | Simple stock adjust |
| REST (ORDS) | Cart/order JSON APIs |
| Intentional defects | See §8.4 |

### 8.3 Seeded Knowledge (auto-loaded)

On playground boot, load `status: active` KB for all pages/components/flows listed above so the agent does not need a cold discovery for demos (discovery still tested as a skill).

### 8.4 Intentional defects + expected GT outcomes

| Defect ID | What user sees | Truth | Expected agent result |
|---|---|---|---|
| `bug.cart.ui_ok_db_missing` | “Added successfully” | No `CART_ITEM` row | **FAIL** + evidence (ui vs db) |
| `bug.cart.wrong_total` | Line total wrong | `qty * price` mismatch | **FAIL** |
| `bug.stock.not_decremented` | Order placed | Stock unchanged | **FAIL** |
| `bug.banner.off_hours_logic` | — | Banner rule 09–18 | Off-hours absence = **PASS** |
| `bug.api.schema_drift` | UI ok | REST missing field | **FAIL** on API rule/GT |
| `bug.authz.associate_admin` | Associate opens admin URL | Forbidden | **FAIL** if accessible |

### 8.5 Playground GT fixture pack (must ship)

File set (planning names):

```text
playground/gt/
  auth.login.yaml
  cart.add_item.yaml
  cart.line_total.yaml
  stock.decrement_on_order.yaml
  stock.block_when_zero.yaml
  order.create.yaml
  promo.banner.visibility.yaml
  role.associate.forbid_admin.yaml
playground/rules/
  apex_defaults.yaml
playground/kb/
  page_map.yaml
  flows.yaml
```

Each GT fixture must include `applies_when`, `compare.mode`, and `evidence_required`.

### 8.6 Benchmark scenarios (efficiency gates)

| Scenario | Expected LLM calls | Expected conclusion |
|---|---|---|
| Login + open products (all GT present) | 0 | PASS |
| Add to cart happy path | 0 | PASS |
| Add to cart with `bug.cart.ui_ok_db_missing` | 0 | FAIL |
| Banner at 21:00 not visible | 0 | PASS (expected absence) |
| Ambiguous NL goal only | ≤1 | ASK_USER / UNKNOWN / route |
| Brand-new page, no GT | 0–1 interpret | UNKNOWN or INSUFFICIENT_EVIDENCE |

If benchmarks need multi-step ReAct LLM loops for GT-backed cases, the design has regressed.

---

## 9. Client UAT collection playbook

### 9.1 Minimum access request list

1. Non-production APEX URL + test users (associate + manager)
2. Read-only APEX metadata / app schema access (strongly preferred)
3. Read-only business tables for entities under test (stock, cart, orders) in UAT
4. ORDS module docs or OpenAPI if any
5. High-level business overview (optional)
6. Named approver for Candidate Expectation / Golden Run (not a full-time SME)

### 9.2 First 5 UAT days (recommended)

| Day | Activity | Output |
|---|---|---|
| 1 | Metadata + crawl discovery | KB candidates |
| 2 | Map top inventory flows; queue candidate expectations | Expectation queue |
| 3 | Approver reviews queue (30–60 min) | First GT pack |
| 4 | Execute GT-backed sanity; fix false assumptions | Sanity baseline |
| 5 | Golden approve sanity; schedule dry-run | Daily sanity ready (later plugin) |

### 9.3 When client provides a feature note

1. Parse feature text → draft Candidate Expectations (LLM allowed here once).
2. Link impacted KB flows (change impact — later skill).
3. Approver confirms or edits.
4. Write GT versions; run validation; report PASS/FAIL/UNKNOWN.

---

## 10. Runtime usage rules (Base Agent)

| Event | KB | Rules | GT | LLM |
|---|---|---|---|---|
| Route to capability | Optional snippets | — | — | Only if ambiguous |
| After tool observation | No | Always | Prefer | Only if no rule/GT match |
| Final conclusion | Never alone | Yes | Yes | Never overrides GT |
| Discovery skill | Write candidates | — | Never auto-write | Minimal clustering |

Context Manager must:

- Prefer GT facts over KB snippets in packets
- Cap KB tokens
- Label trust: `authority=gt|rule|kb|observation`

---

## 11. Security Agent reuse

Same schemas. Different subject namespaces and plugins, for example:

- `authz.*`, `session.*`, `input.*`, `exposure.*`
- GT from role matrices and playground authz defects
- Still: no LLM-invented “secure/insecure” without rule/GT

Do not fork the GT store — use `tags: [security]` and plugin ownership metadata.

---

## 12. Efficiency targets tied to GT maturity

| GT maturity | Sanity-style run LLM calls (p50) | Notes |
|---|---|---|
| None (cold UAT) | 1–2 | Mostly UNKNOWN + discovery |
| Rules only | ≤1 | Objective fails still caught |
| Core inventory GT approved | **0** | Banner/cart/stock/order |
| + golden baseline | **0** | Daily sanity path |

Token policy: never send full KB; never send raw HTML to LLM when GT already decides.

---

## 13. Acceptance criteria for this collection system

This spec is satisfied when the team can demonstrate (even with mocks / playground):

1. Discovery writes **KB candidates**, not GT.
2. GT is written only via an allowed origin path (§6.1).
3. Banner off-hours case returns PASS without LLM.
4. UI-success / DB-missing defect returns FAIL with evidence without LLM.
5. Missing expectation returns `UNKNOWN` or `INSUFFICIENT_EVIDENCE`, not a guessed FAIL.
6. Playground fixture pack loads into `GroundTruthProvider` / `KnowledgeProvider`.
7. Same record shapes work for future Security subjects.
8. Approver identity is stored on every GT version.

---

## 14. Deliverables checklist (planning → later build)

| Deliverable | Phase |
|---|---|
| Base Agent GT/KB provider interfaces | Week 1 runtime |
| In-memory + YAML fixture providers | Week 1 / playground |
| APEX playground app + intentional bugs | Before QA plugin hardening |
| GT/KB YAML packs (§8.5) | With playground |
| Candidate expectation approval UX | With QA learning loop |
| UAT metadata reader | QA discovery skill |
| Golden run approve action | Before daily sanity |

---

## 15. One-paragraph client framing

> We do not depend on detailed test cases or continuous SME support. From URL and credentials we discover the Oracle APEX application into a Knowledge Base. Objective rules catch technical failures immediately. When an expectation is approved — from a short feature note, a golden UAT run, or a light review of candidate behaviours — it becomes Ground Truth and future checks are deterministic. If we cannot establish expected behaviour, we return UNKNOWN or INSUFFICIENT_EVIDENCE instead of guessing. For development we use our own APEX inventory playground with curated Ground Truth so accuracy and efficiency are proven before pointing the same agent at your UAT environment.

---

*End of specification.*
