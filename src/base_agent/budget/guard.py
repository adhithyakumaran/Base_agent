from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from base_agent.contracts.enums import ErrorClass
from base_agent.contracts.models import RunBudget, RunCounters


@dataclass
class BudgetTrip:
    error_class: ErrorClass
    reason_code: str
    message: str


class BudgetGuard:
    """Deterministic execution limits. Never loop until success."""

    def __init__(self, budget: RunBudget | None = None) -> None:
        self.budget = budget or RunBudget()

    def check(self, counters: RunCounters, *, signature: str | None = None,
              recent_signatures: list[str] | None = None,
              state_hash: str | None = None,
              recent_state_hashes: list[str] | None = None) -> BudgetTrip | None:
        b = self.budget
        if counters.steps >= b.max_steps:
            return BudgetTrip(ErrorClass.BUDGET_EXCEEDED, "budget.steps", f"max_steps={b.max_steps}")
        if counters.tool_calls >= b.max_tool_calls:
            return BudgetTrip(ErrorClass.BUDGET_EXCEEDED, "budget.tools", f"max_tool_calls={b.max_tool_calls}")
        if counters.llm_calls >= b.max_llm_calls:
            return BudgetTrip(ErrorClass.BUDGET_EXCEEDED, "budget.llm", f"max_llm_calls={b.max_llm_calls}")
        if counters.tokens_in + counters.tokens_out >= b.max_tokens:
            return BudgetTrip(ErrorClass.BUDGET_EXCEEDED, "budget.tokens", f"max_tokens={b.max_tokens}")
        if counters.pages_visited >= b.max_pages:
            return BudgetTrip(ErrorClass.BUDGET_EXCEEDED, "budget.pages", f"max_pages={b.max_pages}")

        if signature and recent_signatures:
            if recent_signatures.count(signature) >= b.max_same_tool_signature:
                return BudgetTrip(ErrorClass.CYCLE_DETECTED, "cycle.tool_signature", signature)

        if state_hash and recent_state_hashes:
            if recent_state_hashes.count(state_hash) >= b.max_same_state_hash:
                return BudgetTrip(ErrorClass.STUCK, "cycle.state_hash", state_hash)

        return None


def canonical_signature(tool_name: str, payload: dict) -> str:
    body = json.dumps({"tool": tool_name, "input": payload}, sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def state_digest(capability: str | None, last_obs_reason: str | None, pending_slots: list[str] | None = None) -> str:
    body = json.dumps(
        {"capability": capability, "obs": last_obs_reason, "slots": pending_slots or []},
        sort_keys=True,
    )
    return hashlib.sha256(body.encode()).hexdigest()[:16]