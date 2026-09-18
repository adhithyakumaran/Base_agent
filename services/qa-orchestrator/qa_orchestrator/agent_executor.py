"""P6 — trusted agent executor using existing deterministic components."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from qa_orchestrator.agent_models import AgentAction, AgentRunState
from qa_orchestrator.execution_gate import ExecutionGate
from qa_orchestrator.models import (
    DiscoveryResult,
    ExecutionPlan,
    ExecutionResult,
    ExplorationResult,
    GenerationResult,
    HealingResult,
    PlanningResult,
    SuiteSelectionPlan,
    ValidationResult,
)
from qa_orchestrator.run_request import RunRequest


class OrchestratorDeps(Protocol):
    discovery_root: Path
    discovery: Any
    exploration: Any
    generation: Any
    healing: Any
    executor: Any
    validator: Any
    llm: Any


class AgentExecutor:
    """Perform allowlisted actions through existing trusted services only."""

    def __init__(self, deps: OrchestratorDeps) -> None:
        self.deps = deps

    def run_existing_test(
        self,
        *,
        suite_plan: SuiteSelectionPlan,
        run_id: str | None,
        skip_execution: bool,
    ) -> ExecutionResult:
        if skip_execution:
            return ExecutionResult(ok=True, mode="skipped", observations=[])
        if hasattr(self.deps.executor, "run_selection"):
            if run_id and hasattr(self.deps.executor, "set_run_context"):
                self.deps.executor.set_run_context(run_id=run_id, flow_ids=suite_plan.flow_ids)  # type: ignore[attr-defined]
            return self.deps.executor.run_selection(suite_plan)  # type: ignore[attr-defined]
        plan = ExecutionPlan(goal=suite_plan.execution_mode, steps=[])
        return self.deps.executor.run_plan(plan)

    def explore(
        self,
        *,
        planning: PlanningResult,
        run_id: str | None,
        skip_discovery: bool,
    ) -> tuple[ExplorationResult | None, DiscoveryResult | None]:
        if skip_discovery or not planning.exploration_required or not planning.exploration:
            return None, None
        if planning.strategy == "BLOCK":
            return None, None
        exploration = self.deps.exploration.run_from_planning(
            planning,
            exploration_id=run_id or None,
        )
        return exploration, None

    def discover(
        self,
        *,
        intent,
        suite_plan: SuiteSelectionPlan,
        exploration: ExplorationResult | None,
        skip_discovery: bool,
    ) -> DiscoveryResult | None:
        if skip_discovery or exploration is not None:
            return None
        if intent.execution_mode not in {"new_feature", "discover"}:
            return None
        return self.deps.discovery.discover(intent, suite_plan)

    def generate(
        self,
        *,
        planning: PlanningResult,
        exploration: ExplorationResult | None,
        run_id: str | None,
    ) -> GenerationResult | None:
        if not planning.generation_required or not planning.generation or planning.strategy == "BLOCK":
            return None
        return self.deps.generation.generate_from_planning(
            planning,
            exploration=exploration,
            generation_id=run_id,
        )

    def recover(
        self,
        *,
        execution: ExecutionResult,
        run_id: str,
        flow_id: str,
        test_id: str,
    ) -> HealingResult:
        return self.deps.healing.attempt_healing(
            execution,
            run_id=run_id,
            flow_id=flow_id,
            test_id=test_id,
        )

    def verify(
        self,
        *,
        request: RunRequest,
        plan: ExecutionPlan,
        execution: ExecutionResult,
        intent,
        suite_plan: SuiteSelectionPlan,
        discovery: DiscoveryResult | None,
        llm_summary: str = "",
        diagnostic_context: dict[str, Any] | None = None,
    ) -> ValidationResult:
        return self.deps.validator.validate(
            goal=request.goal,
            run_type=request.run_type,
            plan=plan,
            execution=execution,
            llm_summary=llm_summary,
            intent=intent,
            suite_plan=suite_plan,
            discovery=discovery,
            diagnostic_context=diagnostic_context,
        )

    def capture_evidence(self, state: AgentRunState) -> list[str]:
        execution = state.execution
        if not execution:
            return []
        paths: list[str] = []
        for obs in execution.observations:
            if obs.screenshot_path:
                paths.append(obs.screenshot_path)
            meta = obs.meta or {}
            for key in ("evidence_dir", "dom_path", "screenshot_path"):
                value = meta.get(key)
                if isinstance(value, str) and value:
                    paths.append(value)
        return paths

    def execute_action(
        self,
        action: AgentAction,
        *,
        state: AgentRunState,
        request: RunRequest,
        planning: PlanningResult,
        suite_plan: SuiteSelectionPlan,
        execution_plan: ExecutionPlan,
    ) -> AgentRunState:
        if action.type == "RUN_EXISTING_TEST":
            state.execution = self.run_existing_test(
                suite_plan=suite_plan,
                run_id=state.run_id,
                skip_execution=request.skip_execution,
            )
            state.current_flow = suite_plan.flow_ids[0] if suite_plan.flow_ids else state.current_flow
            state.step_count += len(suite_plan.commands)
        elif action.type == "EXPLORE":
            exploration, _ = self.explore(
                planning=planning,
                run_id=state.run_id,
                skip_discovery=request.skip_discovery,
            )
            state.exploration = exploration
            if exploration:
                state.evidence_paths.extend(exploration.screenshots)
        elif action.type == "CAPTURE_EVIDENCE":
            state.evidence_paths.extend(self.capture_evidence(state))
        elif action.type == "VERIFY":
            llm_summary = ""
            if self.deps.llm.enabled:
                llm_summary, _ = self.deps.llm.summarize(
                    prompt=(
                        "Summarize QA verification context in 2 sentences. Plain text only.\n"
                        f"Goal: {request.goal}\n"
                        f"Execution ok: {state.execution.ok if state.execution else False}\n"
                        f"Evidence count: {len(state.evidence_paths)}"
                    )
                )
            state.validation = self.verify(
                request=request,
                plan=execution_plan,
                execution=state.execution or ExecutionResult(ok=False, mode="missing", observations=[]),
                intent=planning.intent,
                suite_plan=suite_plan,
                discovery=state.discovery,
                llm_summary=llm_summary,
                diagnostic_context={
                    "run_id": state.run_id,
                    "state": state,
                    "planning": planning,
                    "gate": ExecutionGate(self.deps.graph),
                    "skip_execution": request.skip_execution,
                },
            )
        elif action.type == "RECOVER_LOCATOR":
            execution = state.execution or ExecutionResult(ok=False, mode="missing", observations=[])
            flow_id = state.current_flow or (suite_plan.flow_ids[0] if suite_plan.flow_ids else "")
            test_id = flow_id
            state.healing_result = self.recover(
                execution=execution,
                run_id=state.run_id,
                flow_id=flow_id,
                test_id=test_id,
            )
            state.recovery_count += 1
        return state
