# P12 — Intelligent Flow Discovery & Selection

## Problem

Natural-language goals (e.g. **View product using SKU …**) can be understood at the intent layer while an **incorrect or stale executable flow** is still chosen when KB navigation metadata does not match verified UAT paths.

## Phase 1 — Canonical flow audit

Machine-readable audit: `data/discovery-kb/flows/p12-canonical-flow-audit.yaml`

Covers READY flows:

| Flow | Capability | Verified entry / path | Primary automation |
|------|------------|------------------------|-------------------|
| BF-PRODUCT-003 | Product Search | Home → Item Search → `product-detail-item-search` (P6) → search result | TC-BF-PRODUCT-003-P01 |
| BF-PRODUCT-004 | Product Management (view) | Same entry → search → **Product Detail** (`/ea/product-detail`) | TC-BF-PRODUCT-004-P01 |
| BF-HOME-010-01 | Product Search (entry) | Home → Item Search card | Supporting for view/search |
| BF-HOME-010 | Application Navigation | Login → Home | Navigation sanity |
| BF-PRODUCT-CATALOGUE-006 | Product Management | Home → Product Catalogue | Catalogue P01 |

**BF-PRODUCT-004 reconciliation:** KB lists Product Detail behavior but primary locators were pending DOM inspection. Verified UAT/automation path (2026-09-18) is **search on item-search page, open detail, assert detail state** — not search-only verification (that remains BF-PRODUCT-003).

## Phase 2–4 — Flow resolver

Module: `services/qa-orchestrator/qa_orchestrator/flow_resolver.py`

Pipeline:

```
user request
  → intent/capability (deterministic)
  → bounded candidate flows (graph + audit; never LLM-invented)
  → deterministic scoring + product intent constraints
  → optional LLM rerank (allowed list only)
  → confidence + primary/supporting flows
  → EXECUTE | FLOW_MISMATCH | DISCOVERY_REQUIRED
```

Integrated in `QaPlanner.plan()` **without** changing `IntentClassifier` or planner LLM system prompts.

- **FLOW_MISMATCH:** block automatic execution (`strategy=BLOCK`).
- **DISCOVERY_REQUIRED:** exploration + draft generation contracts; SME approval required (`strategy=EXPLORE`, `execution_allowed=false`).

Diagnostics surface on `PlanningResult.flow_resolution` and validation `decision_diagnostics.flow_selection`.

## Constraints preserved

- Ground Truth semantics unchanged
- ExecutionGate unchanged
- Browser lifecycle unchanged
- LLM cannot introduce executable flow IDs outside resolver candidates

## Tests

`tests/unit/test_p12_flow_resolver.py` plus existing routing/GT/P11 suites.
