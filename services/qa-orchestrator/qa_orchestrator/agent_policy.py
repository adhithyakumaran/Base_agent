"""P6 — allowlisted agent action policy validation."""

from __future__ import annotations

from dataclasses import dataclass

from qa_orchestrator.agent_models import AgentAction, AgentActionType, AgentRunState

ALLOWED_ACTION_TYPES: frozenset[AgentActionType] = frozenset(
    {
        "RUN_EXISTING_TEST",
        "EXPLORE",
        "CAPTURE_EVIDENCE",
        "VERIFY",
        "RECOVER_LOCATOR",
        "WAIT_FOR_REVIEW",
        "STOP",
    }
)

FORBIDDEN_ACTION_PATTERNS = (
    "shell",
    "javascript",
    "eval(",
    "exec(",
    "subprocess",
    "http://",
    "https://",
    "curl ",
    "wget ",
)


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""


class PolicyValidator:
    """Reject actions outside the explicit allowlist and safety boundary."""

    def validate(self, action: AgentAction, state: AgentRunState) -> PolicyDecision:
        if action.type not in ALLOWED_ACTION_TYPES:
            return PolicyDecision(False, f"action type not allowlisted: {action.type}")

        haystack = f"{action.target} {action.value} {action.reason}".lower()
        for pattern in FORBIDDEN_ACTION_PATTERNS:
            if pattern in haystack and action.type not in {"RUN_EXISTING_TEST", "EXPLORE"}:
                return PolicyDecision(False, f"forbidden pattern in action payload: {pattern}")

        if action.type == "RUN_EXISTING_TEST":
            if state.suite_plan and state.suite_plan.commands:
                return PolicyDecision(True, "allowed suite command")
            if state.plan and not state.plan.execution_allowed and not action.requires_approval:
                return PolicyDecision(False, "execution gate blocked")
            if state.suite_plan and not state.suite_plan.commands and not state.suite_plan.flow_ids:
                if state.plan and state.plan.strategy not in {"EXPLORE", "GENERATE", "ASK_USER"}:
                    return PolicyDecision(False, "no executable suite commands")

        if action.type == "RECOVER_LOCATOR":
            if state.recovery_count >= state.metadata.get("max_recoveries", 2):
                return PolicyDecision(False, "recovery limit reached")
            if state.plan and not state.plan.execution_allowed:
                return PolicyDecision(False, "recovery blocked by execution gate")

        if action.type == "EXPLORE" and state.plan and not state.plan.exploration_required:
            return PolicyDecision(False, "exploration not required by planner")

        return PolicyDecision(True, "allowed")
