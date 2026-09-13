"""P6 — bounded agent decision engine (proposal only, never executes)."""

from __future__ import annotations

from qa_orchestrator.agent_config import AgentConfig
from qa_orchestrator.agent_models import (
    AgentAction,
    AgentActionType,
    AgentDecisionEntry,
    AgentDecisionSource,
    AgentRunState,
    AgentStatus,
)
from qa_orchestrator.models import PlanningStrategy


class AgentDecisionEngine:
    """Deterministic decision hub — selects the next bounded action from run state."""

    PRIORITY = ("REUSE_EXISTING", "EXPLORE", "RECOVER", "GENERATE", "HUMAN_REVIEW")

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or AgentConfig.from_env()

    def decide(self, state: AgentRunState) -> tuple[AgentAction, AgentDecisionEntry]:
        action_type, reason, source, confidence = self._choose_action(state)
        action = AgentAction(
            type=action_type,
            target=state.current_flow or (state.selected_flows[0] if state.selected_flows else ""),
            value=state.request,
            source=source,
            confidence=confidence,
            requires_approval=action_type == "WAIT_FOR_REVIEW",
            reason=reason,
        )
        entry = AgentDecisionEntry(
            iteration=state.iteration,
            state=state.status,
            decision=action_type,
            action_id=action.action_id,
            reason=reason,
            source=source,
            confidence=confidence,
            approved=True,
        )
        return action, entry

    def _choose_action(
        self,
        state: AgentRunState,
    ) -> tuple[AgentActionType, str, AgentDecisionSource, float]:
        plan = state.plan
        if state.status == "PLANNING":
            return "STOP", "planning phase handled by loop", "SYSTEM", 1.0

        if state.status in {"COMPLETED", "FAILED", "BLOCKED", "NEEDS_REVIEW", "WAITING_FOR_APPROVAL"}:
            return "STOP", f"terminal state {state.status}", "SYSTEM", 1.0

        if state.status == "VERIFYING":
            return "VERIFY", "deterministic ground-truth verification", "RULE", 1.0

        if state.status == "RECOVERING":
            return "RECOVER_LOCATOR", "attempt approved recovery after classified failure", "RULE", 0.9

        if state.status == "OBSERVING":
            return "CAPTURE_EVIDENCE", "capture run-scoped evidence before verification", "RULE", 1.0

        if plan is None:
            return "WAIT_FOR_REVIEW", "missing planning result", "RULE", 0.0

        if plan.strategy == "BLOCK":
            return "STOP", plan.reasoning_summary or "planner blocked request", "POLICY", 1.0

        if state.suite_plan and state.suite_plan.commands and state.execution is None:
            return "RUN_EXISTING_TEST", "reuse approved existing Playwright coverage", "RULE", plan.confidence

        if plan.requires_human_approval or (
            plan.confidence < self.config.safe_confidence_threshold and not plan.execution_allowed
        ):
            return "WAIT_FOR_REVIEW", "human approval required before execution", "POLICY", plan.confidence

        if not plan.execution_allowed:
            if plan.generation_required or plan.strategy == "GENERATE":
                return "WAIT_FOR_REVIEW", "generated artifacts require SME approval", "POLICY", plan.confidence
            if plan.exploration_required and plan.strategy == "EXPLORE":
                return "EXPLORE", "exploration required before execution", "RULE", plan.confidence
            return "WAIT_FOR_REVIEW", "execution gate blocked all candidate flows", "POLICY", plan.confidence

        if state.execution and not state.execution.ok:
            failure = state.failure
            if (
                failure
                and failure.recovery_eligible
                and state.recovery_count < self.config.max_recoveries
            ):
                return (
                    "RECOVER_LOCATOR",
                    f"eligible {failure.category} failure — bounded recovery",
                    "RULE",
                    0.85,
                )
            return "WAIT_FOR_REVIEW", "execution failed without eligible recovery", "RULE", 0.5

        if state.execution and state.execution.ok and state.validation is None:
            return "VERIFY", "execution completed — run ground-truth verification", "RULE", 1.0

        if state.validation and state.validation.conclusion in {"PASS", "FAIL"}:
            return "STOP", f"verification concluded: {state.validation.conclusion}", "RULE", 1.0

        if state.validation and state.validation.conclusion == "NEEDS_REVIEW":
            return "WAIT_FOR_REVIEW", "verification ambiguous or missing ground truth", "RULE", 0.6

        strategy = self._effective_strategy(plan.strategy, plan)
        if strategy == "EXPLORE" and plan.exploration_required and state.exploration is None:
            return "EXPLORE", "exploration required by planner", "RULE", plan.confidence

        if strategy == "GENERATE" and plan.generation_required and state.generation_result is None:
            return "WAIT_FOR_REVIEW", "generation requires SME approval before execution", "POLICY", plan.confidence

        if plan.exploration_required and state.exploration is None:
            return "EXPLORE", "exploration required and no approved test selected", "RULE", plan.confidence

        return "WAIT_FOR_REVIEW", "no safe executable action identified", "RULE", plan.confidence

    def _effective_strategy(self, strategy: PlanningStrategy, plan) -> PlanningStrategy:
        if strategy in {"REUSE_EXISTING", "EXPLORE", "GENERATE", "ASK_USER", "BLOCK"}:
            return strategy
        return "ASK_USER"
