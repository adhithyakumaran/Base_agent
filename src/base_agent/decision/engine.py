from __future__ import annotations

from base_agent.contracts.enums import Conclusion, DecisionAction, ErrorClass
from base_agent.contracts.models import Decision, Goal, Observation, RoutingDecision, RunCounters
from base_agent.budget.guard import BudgetGuard
from base_agent.errors.taxonomy import is_retryable
from typing import Any


class DecisionEngine:
    """Deterministic-first hub. Never loops until success."""

    def __init__(self, budget_guard: BudgetGuard | None = None) -> None:
        self.budget_guard = budget_guard or BudgetGuard()

    def decide(self, state: dict[str, Any]) -> Decision:
        goal: Goal = state["goal"]
        if isinstance(goal, dict):
            goal = Goal.model_validate(goal)
        counters: RunCounters = state.get("counters") or RunCounters()
        budget = state.get("budget")
        if budget is not None:
            self.budget_guard.budget = budget

        last_obs: Observation | None = state.get("last_observation")
        if isinstance(last_obs, dict):
            last_obs = Observation.model_validate(last_obs)
        routing = state.get("routing")
        route = RoutingDecision.model_validate(routing) if routing else None

        trip = self.budget_guard.check(
            counters,
            signature=(state.get("recent_signatures") or [None])[-1] if state.get("recent_signatures") else None,
            recent_signatures=state.get("recent_signatures"),
            state_hash=(state.get("recent_state_hashes") or [None])[-1] if state.get("recent_state_hashes") else None,
            recent_state_hashes=state.get("recent_state_hashes"),
        )
        if trip:
            if trip.error_class in {ErrorClass.CYCLE_DETECTED, ErrorClass.STUCK}:
                return Decision(
                    action=DecisionAction.COMPLETE.value,
                    reason_code=trip.reason_code,
                    conclusion=Conclusion.UNKNOWN.value,
                    summary=f"Stopped to prevent infinite loop: {trip.message}",
                )
            return Decision(
                action=DecisionAction.COMPLETE.value,
                reason_code=trip.reason_code,
                conclusion=Conclusion.BLOCKED.value,
                summary=f"Budget/policy stop: {trip.message}",
            )

        if last_obs and last_obs.validation_outcome == "pass":
            return Decision(
                action=DecisionAction.COMPLETE.value,
                reason_code=last_obs.reason_code or "obs.pass",
                conclusion=Conclusion.PASS.value,
                summary="Validated observation satisfied expectation/rule.",
            )

        if last_obs and last_obs.validation_outcome == "fail":
            infra = {"timeout", "network_failure", "tool_failure", "tool_error"}
            if (last_obs.reason_code or "") not in infra:
                return Decision(
                    action=DecisionAction.COMPLETE.value,
                    reason_code=last_obs.reason_code or "obs.fail",
                    conclusion=Conclusion.FAIL.value,
                    summary="Validated observation violated expectation/rule.",
                )

        tool_calls = state.get("tool_calls") or []
        if tool_calls:
            last = tool_calls[-1]
            if hasattr(last, "model_dump"):
                pass
            else:
                from base_agent.contracts.models import ToolCallRecord

                last = ToolCallRecord.model_validate(last)
            if not last.ok and last.error_class:
                try:
                    ec = ErrorClass(last.error_class)
                except ValueError:
                    ec = ErrorClass.TOOL_FAILURE
                if is_retryable(ec, last.attempt):
                    return Decision(
                        action=DecisionAction.RETRY.value,
                        reason_code=f"retry.{ec.value}",
                        tool_name=last.name,
                        tool_input=last.input,
                        capability=last.capability,
                    )
                if ec in {
                    ErrorClass.AUTHENTICATION_FAILURE,
                    ErrorClass.AUTHORIZATION_FAILURE,
                    ErrorClass.INVALID_INPUT,
                }:
                    return Decision(
                        action=DecisionAction.COMPLETE.value,
                        reason_code=ec.value,
                        conclusion=Conclusion.BLOCKED.value,
                        summary=f"Non-retryable error: {ec.value}",
                    )
                return Decision(
                    action=DecisionAction.COMPLETE.value,
                    reason_code=ec.value,
                    conclusion=Conclusion.UNKNOWN.value,
                    summary=f"Tool error without safe retry: {ec.value}",
                )

        if route and route.tool_name and last_obs is None:
            tool_input = dict(goal.entities)
            if route.tool_name.endswith("echo") and "text" not in tool_input:
                import re

                m = re.search(r"echo\b[:\s]+(.+)$", goal.raw_text, re.I)
                if m:
                    tool_input["text"] = m.group(1).strip()
            if route.tool_name.endswith("add") and ("a" not in tool_input or "b" not in tool_input):
                import re

                m = re.search(r"add\b[:\s]+(-?\d+)\s*,\s*(-?\d+)", goal.raw_text, re.I)
                if m:
                    tool_input["a"], tool_input["b"] = m.group(1), m.group(2)
            if route.tool_name.endswith("page_probe") and not tool_input.get("page"):
                import re

                m = re.search(r"page(?:\s+probe)?[:\s]+([\w\-]+)", goal.raw_text, re.I)
                if m:
                    tool_input["page"] = m.group(1)
            if route.tool_name.endswith("component_probe") and not tool_input.get("item"):
                import re

                m = re.search(r"(?:component probe|probe (?:component|item))[:\s]+([\w\-]+)", goal.raw_text, re.I)
                if not m:
                    m = re.search(r"\b(P\d+_[A-Z0-9]+)\b", goal.raw_text, re.I)
                if m:
                    tool_input["item"] = m.group(1)
            if route.tool_name.endswith("flow_replay") and not tool_input.get("flow"):
                import re

                m = re.search(r"(?:replay flow|flow replay|run flow)[:\s]+([\w\-\s]+)$", goal.raw_text, re.I)
                if m:
                    tool_input["flow"] = m.group(1).strip()
            return Decision(
                action=DecisionAction.CALL_TOOL.value,
                reason_code=route.reason_code,
                tool_name=route.tool_name,
                tool_input=tool_input,
                capability=route.capability,
                confidence=route.confidence,
            )

        if last_obs and last_obs.validation_outcome in {"insufficient", "not_applicable"}:
            has_data = bool((last_obs.payload or {}).get("data"))
            return Decision(
                action=DecisionAction.COMPLETE.value,
                reason_code=last_obs.reason_code or "obs.insufficient",
                conclusion=Conclusion.UNKNOWN.value if has_data else Conclusion.INSUFFICIENT_EVIDENCE.value,
                summary="Observed behaviour but no approved Ground Truth to assert PASS/FAIL.",
            )

        if route and route.candidates and not route.tool_name:
            return Decision(
                action=DecisionAction.COMPLETE.value,
                reason_code="route.ambiguous",
                conclusion=Conclusion.UNKNOWN.value,
                summary=f"Ambiguous routing candidates: {route.candidates}. Not guessing.",
                details={"candidates": route.candidates},
            )

        if route and route.reason_code == "route.no_match":
            return Decision(
                action=DecisionAction.COMPLETE.value,
                reason_code="route.no_match",
                conclusion=Conclusion.INSUFFICIENT_EVIDENCE.value,
                summary="No matching capability/tool. Returning insufficient evidence instead of looping.",
            )

        if goal.needs_clarification:
            return Decision(
                action=DecisionAction.ASK_USER.value,
                reason_code="goal.ambiguous",
                summary="Goal requires clarification.",
            )

        return Decision(
            action=DecisionAction.COMPLETE.value,
            reason_code="decision.no_path",
            conclusion=Conclusion.INSUFFICIENT_EVIDENCE.value,
            summary="No actionable path without guessing.",
        )