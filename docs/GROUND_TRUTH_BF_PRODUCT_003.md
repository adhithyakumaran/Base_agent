# Ground Truth — BF-PRODUCT-003 (Search SKU)

## Authoritative implementation (as built in this repo)

| Concern | Location |
|--------|-----------|
| GT storage | `data/discovery-kb/gt/*.json` |
| Loader | `Validator._load_approved_gt()` — only files with `"status": "approved"` |
| Goal match | `gt_eval.goal_matches_gt()` — substring match on `subject`, `id`, `flow_id`, `tags` vs goal text |
| Phase A | `Validator._validate_phase_a()` — technical checks; honest `NEEDS_REVIEW` when no matching **approved** GT |
| Phase B | `Validator._validate_phase_b()` — `evaluate_gt_expectations()` on Playwright observation meta |
| Diagnostics | `decision_diagnostics.build_validation_phase_a/b_diagnostic()` |
| `approved_available` / `matched_for_goal` | True only when an **approved** GT matches the goal (Phase B), or when such GT exists but Phase A still applies pre-GT policy |

Planning spec (YAML schemas) lives in `docs/APEX_GT_KB_COLLECTION_SPEC.md`; **runtime** uses the simpler JSON format above (see `gt-login-positive.json`).

## Draft GT created

- **File:** `data/discovery-kb/gt/gt-bf-product-003-positive.json`
- **ID:** `gt-bf-product-003-positive`
- **Status:** `pending_sme_approval` (not loaded for Phase B)

### Expectations (Phase B when approved)

```json
{
  "execution_ok": true,
  "min_passed_tests": 1,
  "require_product_search_verified": true
}
```

`require_product_search_verified` checks orchestrator `param_trace.product_search_result_verified == "true"` (from Playwright `PRODUCT_SEARCH_TRACE:result_verified`).

**Limitation (honest):** Phase B does **not** yet compare full observed business fields (P6_ITEM value vs parameterized SKU) in Python. That evidence is produced in Playwright and surfaced via the product-search trace marker. A future extension can add explicit SKU equality checks against `param_trace.request_sku`.

## SME approval (existing governance pattern)

There is no separate GT API in the console. Approval is **governance on the GT JSON file**, same as login GT:

```bash
# From repo root (Windows: same commands in PowerShell)
python scripts/approve-ground-truth.py gt-bf-product-003-positive --approver "SME Reviewer"
```

Dry run:

```bash
python scripts/approve-ground-truth.py gt-bf-product-003-positive --dry-run
```

After approval, `"status": "approved"` and Phase B can run for goals that match tags/subject (e.g. `Search SKU …`).

**Actor:** SME Reviewer (human). **Does not** change ExecutionGate or flow artifact approvals.

## Windows demo steps

1. Confirm draft GT: open `data/discovery-kb/gt/gt-bf-product-003-positive.json` — status must remain `pending_sme_approval` until you approve.
2. Run LIVE_DEMO without approval → expect **NEEDS_REVIEW** / `validator.pre_gt_honest`.
3. Approve GT: `python scripts/approve-ground-truth.py gt-bf-product-003-positive --approver "Your Name"`.
4. Rerun from ScoutAI: **Search SKU 552811DUDABA00** (runtime param — not stored in GT file).
5. Expect: Playwright PASS → Phase B → **PASS** only if `execution_ok`, `min_passed_tests`, and `product_search_result_verified` trace are present.

## Test case metadata

`selected_test_case_ids` is populated from Playwright `reports/results.json` titles, with fallback `TC-BF-PRODUCT-003-P01` for flow `BF-PRODUCT-003`.
