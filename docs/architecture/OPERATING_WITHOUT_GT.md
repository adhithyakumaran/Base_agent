# Operating without Ground Truth (enterprise mode)

## Client constraint

The client will not provide detailed flows/SME upfront. SME GT may arrive later. The agent must still be **useful and enterprise-grade** before GT exists.

## What KB alone can do

| Capability | Without GT? | How |
|---|---|---|
| Login + session handling | Yes | Deterministic browser skill |
| Discover pages/modules/components | Yes | Bounded crawler → KB candidates |
| Map flows from navigation + recordings | Yes | Candidate flows in KB |
| Catch technical failures | Yes | Rules: ORA errors, 5xx, session dead, stuck/modal timeout |
| Natural-language “explore / sanity / list flows” | Yes | Route → discover / sanity / flow_catalog |
| Business PASS/FAIL (“order total correct”) | **No** | Needs GT or explicit rule |
| Honest stop | Yes | `UNKNOWN` / `INSUFFICIENT_EVIDENCE` — **never loop until success** |

## Evidence hierarchy (unchanged)

1. Approved Ground Truth  
2. Deterministic rules/schemas  
3. Knowledge Base (advisory)  
4. Bounded LLM interpretation  

KB is for **planning and discovery**, not silent truth.

## No loop-until-success (client requirement)

Hard stops in runtime:

- `max_steps`, `max_tool_calls`, `max_llm_calls`, `max_pages`, wall timeout  
- repeated tool-signature detection  
- repeated state-hash / stuck detection  
- retries only for classified retryable infra errors (timeout/network), never for “not PASS yet”

When caps hit → `BLOCKED` or `UNKNOWN`, with reason codes — not another guess cycle.

## Performance expectations pre-GT

- Discovery / map goal: **0 LLM calls** on deterministic route  
- Sanity technical probes: **0 LLM**  
- Ambiguous NL only: ≤1 LLM (optional; default LLM disabled until gateway configured)  
- Crawler must not hang on modals/AJAX: dedicated timeouts + skip lists + same-URL once

## When SME GT arrives

`record_approved_result()` promotes candidates → future runs become deterministic PASS/FAIL on those subjects without changing the agent core.
