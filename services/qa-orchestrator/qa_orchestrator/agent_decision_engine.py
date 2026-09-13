"""P6/P7 — bounded agent decision engine with optional LLM assistance."""

from __future__ import annotations

from dataclasses import dataclass

from qa_orchestrator.agent_config import AgentConfig
from qa_orchestrator.agent_decision_context import AgentDecisionContext, build_decision_context
from qa_orchestrator.agent_decision_proposal import AgentDecisionProposal
from qa_orchestrator.agent_models import (
    AgentAction,
    AgentActionType,
    AgentDecisionEntry,
    AgentDecisionSource,
    AgentRunState,
)
from qa_orchestrator.decision_model import DecisionModel, DecisionModelResult, create_decision_model
from qa_orchestrator.models import PlanningStrategy


@dataclass(frozen=True)
class DeterministicDecision:
    action: AgentActionType
    reason: str
    source: AgentDecisionSource
    confidence: float
    ambiguous: bool = False
    ambiguous_reason: str = ""


class AgentDecisionEngine:
    """Deterministic-first decision hub with optional bounded LLM proposals."""

    PRIORITY = ("REUSE_EXISTING", "EXPLORE", "RECOVER", "GENERATE", "HUMAN_REVIEW")

    def __init__(
        self,
        config: AgentConfig | None = None,
        *,
        decision_model: DecisionModel | None = None,
        llm_client=None,
    ) -> None:
        self.config = config or AgentConfig.from_env()
        self.decision_model = decision_model or create_decision_model(self.config, llm_client)
        self._proposal_cache: dict[str, DecisionModelResult] = {}
        self.llm_call_count = 0
        self.llm_latency_ms = 0

    def preview_deterministic(self, state: AgentRunState) -> AgentActionType:
        """Return the deterministic-only action without LLM consultation."""
        return self._deterministic_decision(state).action

    def decide(self, state: AgentRunState) -> tuple[AgentAction, AgentDecisionEntry]:
        deterministic = self._deterministic_decision(state)
        allowed = self._allowed_actions(state, deterministic)
        ambiguous = deterministic.ambiguous or len(allowed) >= 2

        llm_result: DecisionModelResult | None = None
        if self._should_consult_llm(state, deterministic, allowed):
            context = build_decision_context(
                state,
                allowed_actions=allowed,
                ambiguous=ambiguous,
                ambiguous_reason=deterministic.ambiguous_reason,
            )
            cache_key = context.cache_key()
            llm_result = self._proposal_cache.get(cache_key)
            if llm_result is None:
                llm_result = self.decision_model.propose(context, config=self.config)
                self._proposal_cache[cache_key] = llm_result
            self.llm_call_count += 1
            self.llm_latency_ms += llm_result.latency_ms

        final_action, final_reason, final_source, final_confidence = self._resolve_final(
            deterministic,
            allowed,
            llm_result,
        )

        action = AgentAction(
            type=final_action,
            target=state.current_flow or (state.selected_flows[0] if state.selected_flows else ""),
            value=state.request,
            source=final_source,
            confidence=final_confidence,
            requires_approval=final_action == "WAIT_FOR_REVIEW",
            reason=final_reason,
        )

        entry = AgentDecisionEntry(
            iteration=state.iteration,
            state=state.status,
            decision=final_action,
            action_id=action.action_id,
            reason=final_reason,
            source=final_source,
            confidence=final_confidence,
            approved=True,
            decision_source=final_source,
            final_action=final_action,
            llm_invoked=llm_result is not None,
            llm_accepted=bool(
                llm_result
                and llm_result.proposal
                and llm_result.validation
                and llm_result.validation.ok
                and llm_result.proposal.proposed_action == final_action
                and final_source == "LLM"
            ),
            model=llm_result.model if llm_result else None,
            model_version=llm_result.model_version if llm_result else None,
            proposal=llm_result.proposal.model_dump() if llm_result and llm_result.proposal else None,
            validation_result=llm_result.validation.reason if llm_result and llm_result.validation else None,
            evidence_refs=llm_result.proposal.evidence_refs if llm_result and llm_result.proposal else [],
        )
        if llm_result and llm_result.validation and not llm_result.validation.ok:
            entry.policy_result = llm_result.validation.reason
        return action, entry

    def _should_consult_llm(
        self,
        state: AgentRunState,
        deterministic: DeterministicDecision,
        allowed: list[AgentActionType],
    ) -> bool:
        if not self.config.llm_enabled:
            return False
        if deterministic.action in {"STOP"} and not deterministic.ambiguous:
            return False
        if state.status in {"PLANNING", "COMPLETED", "FAILED", "BLOCKED", "NEEDS_REVIEW", "WAITING_FOR_APPROVAL"}:
            return False
        if len(allowed) < 2 and not deterministic.ambiguous:
            return False
        if deterministic.source == "POLICY" and not deterministic.ambiguous:
            return False
        return True

    def _resolve_final(
        self,
        deterministic: DeterministicDecision,
        allowed: list[AgentActionType],
        llm_result: DecisionModelResult | None,
    ) -> tuple[AgentActionType, str, AgentDecisionSource, float]:
        if llm_result and llm_result.proposal and llm_result.validation:
            proposal = llm_result.proposal
            if (
                self.config.llm_auto_decision
                and llm_result.validation.ok
                and proposal.proposed_action in allowed
            ):
                return (
                    proposal.proposed_action,
                    proposal.reason or deterministic.reason,
                    "LLM",
                    proposal.confidence,
                )
            if not llm_result.validation.ok and proposal.proposed_action not in allowed:
                return (
                    "WAIT_FOR_REVIEW",
                    llm_result.validation.reason or "LLM proposal rejected",
                    "POLICY",
                    proposal.confidence,
                )
            if not llm_result.validation.ok and llm_result.validation.rejected_low_confidence:
                return (
                    "WAIT_FOR_REVIEW",
                    llm_result.validation.reason,
                    "POLICY",
                    proposal.confidence,
                )
            if not llm_result.validation.ok:
                return (
                    "WAIT_FOR_REVIEW",
                    llm_result.validation.reason or "unsafe LLM proposal rejected",
                    "POLICY",
                    proposal.confidence,
                )

        return deterministic.action, deterministic.reason, deterministic.source, deterministic.confidence

    def _allowed_actions(
        self,
        state: AgentRunState,
        deterministic: DeterministicDecision,
    ) -> list[AgentActionType]:
        actions: list[AgentActionType] = []
        plan = state.plan

        if state.status == "VERIFYING":
            return ["VERIFY"]
        if state.status == "OBSERVING":
            return ["CAPTURE_EVIDENCE"]
        if state.status == "RECOVERING":
            return ["RECOVER_LOCATOR"]

        if plan is None:
            return ["WAIT_FOR_REVIEW"]

        if state.suite_plan and state.suite_plan.commands and state.execution is None:
            actions.append("RUN_EXISTING_TEST")

        if plan.exploration_required and state.exploration is None:
            actions.append("EXPLORE")

        if state.execution and state.execution.ok and state.validation is None:
            actions.append("VERIFY")

        if state.execution and not state.execution.ok:
            failure = state.failure
            if failure and failure.recovery_eligible and state.recovery_count < self.config.max_recoveries:
                actions.append("RECOVER_LOCATOR")
            actions.extend(["WAIT_FOR_REVIEW", "STOP"])

        if state.validation and state.validation.conclusion == "NEEDS_REVIEW":
            actions.extend(["VERIFY", "WAIT_FOR_REVIEW"])

        if not actions:
            actions.append(deterministic.action)

        if deterministic.ambiguous:
            for candidate in ("EXPLORE", "VERIFY", "WAIT_FOR_REVIEW", "RUN_EXISTING_TEST", "RECOVER_LOCATOR"):
                if candidate not in actions and self._action_plausible(state, candidate):
                    actions.append(candidate)  # type: ignore[arg-type]

        deduped: list[AgentActionType] = []
        for action in actions:
            if action not in deduped:
                deduped.append(action)
        return deduped

    def _action_plausible(self, state: AgentRunState, action: str) -> bool:
        plan = state.plan
        if action == "EXPLORE":
            return bool(plan and plan.exploration_required and state.exploration is None)
        if action == "VERIFY":
            return bool(state.execution)
        if action == "RUN_EXISTING_TEST":
            return bool(state.suite_plan and state.suite_plan.commands and state.execution is None)
        if action == "RECOVER_LOCATOR":
            return bool(state.failure and state.failure.recovery_eligible)
        return action in {"WAIT_FOR_REVIEW", "STOP"}

    def _deterministic_decision(self, state: AgentRunState) -> DeterministicDecision:
        action, reason, source, confidence = self._choose_action(state)
        ambiguous, ambiguous_reason = self._detect_ambiguity(state, action)
        return DeterministicDecision(
            action=action,
            reason=reason,
            source=source,
            confidence=confidence,
            ambiguous=ambiguous,
            ambiguous_reason=ambiguous_reason,
        )

    def _detect_ambiguity(
        self,
        state: AgentRunState,
        primary: AgentActionType,
    ) -> tuple[bool, str]:
        plan = state.plan
        if plan and "AMBIGUOUS" in str(plan.reasoning_summary or "").upper():
            return True, "planner marked AMBIGUOUS"
        if plan and plan.strategy == "ASK_USER":
            return True, "planner ASK_USER strategy"
        if plan and len(plan.candidate_flows) >= 2 and not plan.execution_allowed and plan.exploration_required:
            return True, "multiple flow candidates with exploration required"
        if state.validation and state.validation.conclusion == "NEEDS_REVIEW":
            return True, "verification ambiguous"
        if state.execution and not state.execution.ok and state.failure and state.failure.recovery_eligible:
            if state.recovery_count < self.config.max_recoveries:
                return True, "multiple recovery options"
        if primary == "WAIT_FOR_REVIEW" and plan and plan.exploration_required and state.exploration is None:
            return True, "explore vs escalate"
        if plan and str(plan.reasoning_summary or "").upper().find("AMBIGUOUS") >= 0:
            return True, "planner marked AMBIGUOUS"
        return False, ""

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
