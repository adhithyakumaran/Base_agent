# P9 — Oracle APEX End-to-End Validation

- **Environment:** UAT
- **Timestamp:** 2026-09-14T07:51:30.968710+00:00
- **Preflight:** ENVIRONMENT_BLOCKED

## Flow inventory

- Total flows: 31
- SME-ready: 19
- Approved: 19
- Executable: 19
- Awaiting approval: 0
- Stale: 0
- Blocked (non-executable): 12

## Selected validation subset

- `BF-LOGIN-001` (authentication) — gate `gate.executable` executable=True
- `BF-PRODUCT-003` (parameterized_search) — gate `gate.executable` executable=True
- `BF-LOGOUT-002` (logout) — gate `gate.executable` executable=True
- `BF-HOME-010` (navigation) — gate `gate.executable` executable=True
- `BF-PRODUCT-004` (product_view) — gate `gate.executable` executable=True
- `BF-HOME-010-01` (item_search) — gate `gate.executable` executable=True
- `BF-PRODUCT-STOCK-VISIBILITY-009` (stock_visibility) — gate `gate.executable` executable=True
- `BF-BEST-DEAL-008` (promotions) — gate `gate.executable` executable=True

## Execution matrix

| Request | Expected Flow | Gate | Agent State | Final Result |
|---|---|---|---|---|
| Check login | BF-LOGIN-001 | approval.pending | WAITING_FOR_APPROVAL | WAITING_FOR_APPROVAL |
| Search SKU ABC123 | BF-PRODUCT-003 | approval.stale | WAITING_FOR_APPROVAL | WAITING_FOR_APPROVAL |
| Search for the product using item code ABC123 | BF-PRODUCT-003 | approval.stale | WAITING_FOR_APPROVAL | WAITING_FOR_APPROVAL |
| BF-PRODUCT-003 | BF-PRODUCT-003 | approval.stale | WAITING_FOR_APPROVAL | WAITING_FOR_APPROVAL |
| Test invalid login | BF-LOGIN-001 | approval.pending | WAITING_FOR_APPROVAL | WAITING_FOR_APPROVAL |
| Log out of the application | BF-LOGOUT-002 | approval.stale | WAITING_FOR_APPROVAL | WAITING_FOR_APPROVAL |
| Check login | BF-LOGIN-001 | approval.pending | WAITING_FOR_APPROVAL | WAITING_FOR_APPROVAL |
| Search SKU ABC123 | BF-PRODUCT-003 | approval.stale | WAITING_FOR_APPROVAL | WAITING_FOR_APPROVAL |
| Check login | BF-LOGIN-001 | gate.executable | FAILED | FAIL |

## Metrics

- **approval_routing_accuracy:** 0.8571
- **average_run_duration_ms:** 11.78
- **blocked_live_scenarios:** 2
- **decision_trace_completeness:** 1.0
- **environment_status:** ENVIRONMENT_BLOCKED
- **evidence_completeness:** 0.0
- **false_fail_rate:** 0.0
- **false_pass_rate:** 0.0
- **human_intervention_rate:** 0.8889
- **live_execution_success_rate:** 0.0
- **live_flow_execution_rate:** 0.0
- **p95_run_duration_ms:** 17
- **parameter_traceability_applicable_cases:** 3
- **parameter_traceability_pass_cases:** 3
- **parameter_traceability_rate:** 1.0
- **recovery_success_rate:** 0.0
- **resume_success_rate:** 0.3333
- **verification_success_rate:** 0.0

## Limitations

- Live Oracle APEX execution blocked: login_probe_skipped
- Evidence completeness not measured — live browser execution unavailable
- Live recovery retry against real APEX not exercised in blocked environment
- Live browser evidence and Ground Truth validation against real APEX not completed

## Runs

### p9_nl_check_login
- Request: Check login
- Expected flow: BF-LOGIN-001
- Final result: WAITING_FOR_APPROVAL
- Gate: approval.pending
- Evidence count: 0
- Parameter trace: {'validated_parameters': {}, 'expected': {}, 'parameter_ok': True, 'env_params': {}, 'env_map': {}, 'playwright_parameter_path': []}

### p9_nl_search_sku
- Request: Search SKU ABC123
- Expected flow: BF-PRODUCT-003
- Final result: WAITING_FOR_APPROVAL
- Gate: approval.stale
- Evidence count: 0
- Parameter trace: {'validated_parameters': {'sku': 'ABC123'}, 'expected': {'sku': 'ABC123'}, 'parameter_ok': True, 'env_params': {'sku': 'ABC123'}, 'env_map': {'QA_PARAM_SKU': 'ABC123'}, 'playwright_parameter_path': ['validated_parameters.sku', 'QA_PARAM_SKU', 'apps/automation/src/core/run-params.ts', 'product-search.page.ts / QA-PARAM-SKU.spec.ts']}

### p9_nl_item_code_variant
- Request: Search for the product using item code ABC123
- Expected flow: BF-PRODUCT-003
- Final result: WAITING_FOR_APPROVAL
- Gate: approval.stale
- Evidence count: 0
- Parameter trace: {'validated_parameters': {'sku': 'ABC123'}, 'expected': {'sku': 'ABC123'}, 'parameter_ok': True, 'env_params': {'sku': 'ABC123'}, 'env_map': {'QA_PARAM_SKU': 'ABC123'}, 'playwright_parameter_path': ['validated_parameters.sku', 'QA_PARAM_SKU', 'apps/automation/src/core/run-params.ts', 'product-search.page.ts / QA-PARAM-SKU.spec.ts']}

### p9_exact_flow_id
- Request: BF-PRODUCT-003
- Expected flow: BF-PRODUCT-003
- Final result: WAITING_FOR_APPROVAL
- Gate: approval.stale
- Evidence count: 0
- Parameter trace: {'validated_parameters': {}, 'expected': {}, 'parameter_ok': True, 'env_params': {}, 'env_map': {}, 'playwright_parameter_path': []}

### p9_invalid_login
- Request: Test invalid login
- Expected flow: BF-LOGIN-001
- Final result: WAITING_FOR_APPROVAL
- Gate: approval.pending
- Evidence count: 0
- Parameter trace: {'validated_parameters': {}, 'expected': {}, 'parameter_ok': True, 'env_params': {}, 'env_map': {}, 'playwright_parameter_path': []}

### p9_logout
- Request: Log out of the application
- Expected flow: BF-LOGOUT-002
- Final result: WAITING_FOR_APPROVAL
- Gate: approval.stale
- Evidence count: 0
- Parameter trace: {'validated_parameters': {}, 'expected': {}, 'parameter_ok': True, 'env_params': {}, 'env_map': {}, 'playwright_parameter_path': []}

### p9_live_login
- Request: Check login
- Expected flow: BF-LOGIN-001
- Final result: WAITING_FOR_APPROVAL
- Gate: approval.pending
- Evidence count: 0
- Parameter trace: {'validated_parameters': {}, 'expected': {}, 'parameter_ok': True, 'env_params': {}, 'env_map': {}, 'playwright_parameter_path': []}

### p9_live_sku
- Request: Search SKU ABC123
- Expected flow: BF-PRODUCT-003
- Final result: WAITING_FOR_APPROVAL
- Gate: approval.stale
- Evidence count: 0
- Parameter trace: {'validated_parameters': {'sku': 'ABC123'}, 'expected': {'sku': 'ABC123'}, 'parameter_ok': True, 'env_params': {'sku': 'ABC123'}, 'env_map': {'QA_PARAM_SKU': 'ABC123'}, 'playwright_parameter_path': ['validated_parameters.sku', 'QA_PARAM_SKU', 'apps/automation/src/core/run-params.ts', 'product-search.page.ts / QA-PARAM-SKU.spec.ts']}

### p9_offline_approval_resume
- Request: Check login
- Expected flow: BF-LOGIN-001
- Final result: FAIL
- Gate: gate.executable
- Evidence count: 0
- Parameter trace: {'validated_parameters': {}, 'expected': {}, 'parameter_ok': True, 'env_params': {}, 'env_map': {}, 'playwright_parameter_path': []}
