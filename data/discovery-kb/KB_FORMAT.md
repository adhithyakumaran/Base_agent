# Flow Knowledge Base — Canonical Format (v1)

**Locked with:** [AI_POWERED_QA_AUTOMATION_PROPOSAL.md](../finalized-proposal/AI_POWERED_QA_AUTOMATION_PROPOSAL.md)

## Canonical location

```text
discovery/uat_ea/flows/          ← USE THIS (flow-centric YAML)
discovery/uat_ea/flows/index.yaml
discovery/uat_ea/capabilities.yaml
discovery/uat_ea/kb/             ← LEGACY archive (JSON page/flow seeds)
```

## One file = one business flow

Filename: `{flow_id}.yaml` (example: `BF-LOGIN-001.yaml`)

## Required sections (READY flows)

| Section | Purpose |
|---|---|
| `flow_id` / `flow_name` | Stable identity for orchestrator + graph |
| `application` | App name, env, APEX app id |
| `purpose` | Business intent (not technical steps only) |
| `entry_point` | Page + route |
| `actors` / `preconditions` | Who can run; starting state |
| `pages` | All pages in flow |
| `components` | UI controls with **primary + 3 fallbacks** locators |
| `business_flow` | Ordered business steps |
| `expected_success` / `observed_*` | Pass criteria and known failure modes |
| `business_rules` | Numbered rules with status (Confirmed/Observed/Unknown) |
| `unknown_business_rules` | Explicit gaps — agent must not invent |
| `technical_metadata` | APEX items, DOM, operations |
| `automation` | Playwright actions, locator strategy, self-healing policy |
| `test_data` | Logical references only — **never real credentials** |
| `security` | Sensitive data policy |
| `evidence` | Sources and sanitization |
| `status` | READY / DRAFT / SUPERSEDED + confidence |

## Status values

| Status | Meaning |
|---|---|
| **READY** | SME-reviewed; locators, rules, automation block complete |
| **DRAFT** | Migrated from legacy JSON — needs enrichment |
| **SUPERSEDED** | Replaced by another flow id |

## Information ownership (from QA collection spec)

| Category | Owner | In KB? |
|---|---|---|
| A — Technical (pages, DOM, locators, URLs) | Tool discovery | Yes — auto |
| B — APEX metadata (items, buttons, processes) | APEX + DOM | Yes — when available |
| C — Business rules, expected outcomes | Client/SME | Yes — manual confirm |

## Locator policy (self-healing ready)

```yaml
locator_strategy:
  resolution_order: [primary, fallback_1, fallback_2, fallback_3]
  validation:
    zero_matches: Try next locator
    multiple_matches: Reject as ambiguous
    single_match: Accept
self_healing:
  enabled: true
  permanent_update:
    requires_validation_or_approval: true
```

## Reference examples (READY)

- `BF-LOGIN-001.yaml` — User Login  
- `BF-LOGOUT-002.yaml` — User Logout  
- `BF-PRODUCT-003.yaml` — Search Product  

## Legacy JSON

The old `kb/*.json` pack remains as discovery archive. Do not add new knowledge there. Migrate flows into YAML before automation generation.
