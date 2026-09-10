from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from base_agent.budget.guard import BudgetGuard, canonical_signature, state_digest
from base_agent.contracts.enums import AgentStatus, Conclusion, DecisionAction
from base_agent.contracts.models import Decision, DecisionRecord, Goal, RunCounters, ToolCallRecord
from base_agent.contracts.result import AgentResult, EvidenceRef
from base_agent.decision.engine import DecisionEngine
from base_agent.observation.pipeline import ObservationPipeline
from base_agent.routing.hybrid import GoalHandler, HybridRouter
from base_agent.state.schema import AgentState
from base_agent.tools.registry import ExecutionContext, ToolExecutor, ToolRegistry


def build_graph(
    *,
    registry: ToolRegistry,
    executor: ToolExecutor,
    router: HybridRouter,
    decision_engine: DecisionEngine,
    observation_pipeline: ObservationPipeline,
    permissions: list[str],
) -> Any:
    goal_handler = GoalHandler()
    budget_guard = BudgetGuard()

    def node_goal(state: AgentState) -> dict[str, Any]:
        goal = state.get("goal")
        if isinstance(goal, dict):
            goal = Goal.model_validate(goal)
        if goal is None:
            raw = (state.get("metadata") or {}).get("raw_goal", "")
            goal = goal_handler.parse(raw)
        return {"goal": goal, "status": AgentStatus.RUNNING.value}

    def node_budget(state: AgentState) -> dict[str, Any]:
        counters = state.get("counters") or RunCounters()
        if state.get("budget"):
            budget_guard.budget = state["budget"]
        trip = budget_guard.check(
            counters,
            recent_signatures=state.get("recent_signatures"),
            recent_state_hashes=state.get("recent_state_hashes"),
            signature=(state.get("recent_signatures") or [None])[-1] if state.get("recent_signatures") else None,
            state_hash=(state.get("recent_state_hashes") or [None])[-1] if state.get("recent_state_hashes") else None,
        )
        meta = dict(state.get("metadata") or {})
        if trip:
            meta["budget_trip"] = {"reason": trip.reason_code, "message": trip.message}
        return {"metadata": meta, "current_step": int(state.get("current_step") or 0) + 1,
                "counters": counters.model_copy(update={"steps": counters.steps + 1})}

    def node_route(state: AgentState) -> dict[str, Any]:
        goal = state["goal"]
        if isinstance(goal, dict):
            goal = Goal.model_validate(goal)
        decision = router.route(goal)
        return {"routing": decision.model_dump(), "current_capability": decision.capability}

    def node_decide(state: AgentState) -> dict[str, Any]:
        # inject budget object for engine
        st = dict(state)
        d = decision_engine.decide(st)
        rec = DecisionRecord(action=d.action, reason_code=d.reason_code, llm_used=d.llm_used, confidence=d.confidence)
        return {"pending_decision": d, "decisions": [rec]}

    def node_execute(state: AgentState) -> dict[str, Any]:
        d: Decision = state["pending_decision"]
        if isinstance(d, dict):
            d = Decision.model_validate(d)
        counters = state.get("counters") or RunCounters()
        attempt = 1
        if d.action == DecisionAction.RETRY.value:
            prev = (state.get("tool_calls") or [])
            if prev and prev[-1].name == d.tool_name:
                attempt = prev[-1].attempt + 1
        ctx = ExecutionContext(run_id=state.get("run_id") or "run", permissions=permissions)
        raw = executor.execute(d.tool_name or "", d.tool_input, ctx)
        sig = canonical_signature(d.tool_name or "", d.tool_input)
        record = ToolCallRecord(
            name=d.tool_name or "",
            capability=d.capability,
            input=d.tool_input,
            output=raw.data if raw.ok else {"error": raw.error_message},
            ok=raw.ok,
            error_class=raw.error_class,
            latency_ms=raw.latency_ms,
            attempt=attempt,
        )
        updates = {
            "tool_calls": [record],
            "last_raw_result": raw.model_dump(),
            "counters": counters.model_copy(
                update={
                    "tool_calls": counters.tool_calls + 1,
                    "retries": counters.retries + (1 if attempt > 1 else 0),
                    "pages_visited": counters.pages_visited + int(bool(raw.data.get("pages"))),
                }
            ),
            "recent_signatures": [sig],
        }
        return updates

    def node_observe(state: AgentState) -> dict[str, Any]:
        raw = state.get("last_raw_result") or {}
        d: Decision = state["pending_decision"]
        if isinstance(d, dict):
            d = Decision.model_validate(d)
        gt_subject = None
        context = {}
        # Banner special-case for mock tool
        if (d.tool_name or "").endswith("banner_observe"):
            gt_subject = "promo.banner.visibility"
            context = {"local_time": (d.tool_input or {}).get("local_time") or (state.get("metadata") or {}).get("local_time")}
        obs = observation_pipeline.process(
            tool_name=d.tool_name or "",
            plugin_id=None,
            raw=raw.get("data") or {},
            ok=bool(raw.get("ok", False)),
            error_class=raw.get("error_class"),
            gt_subject=gt_subject,
            context=context,
            allow_llm=False,
        )
        digest = state_digest(d.capability, obs.reason_code)
        return {
            "last_observation": obs,
            "observations": [obs],
            "evidence_refs": [obs.id],
            "recent_state_hashes": [digest],
        }

    def node_assemble(state: AgentState) -> dict[str, Any]:
        d: Decision = state.get("pending_decision")  # type: ignore[assignment]
        if isinstance(d, dict):
            d = Decision.model_validate(d)
        counters = state.get("counters") or RunCounters()
        goal = state["goal"]
        if isinstance(goal, dict):
            goal = Goal.model_validate(goal)
        conclusion = d.conclusion or Conclusion.UNKNOWN.value
        # Map COMPLETE without conclusion
        if d.action in {DecisionAction.UNKNOWN.value} and not d.conclusion:
            conclusion = Conclusion.UNKNOWN.value
        result = AgentResult(
            conclusion=Conclusion(conclusion),
            reason_code=d.reason_code,
            summary=d.summary or d.reason_code,
            goal=goal.raw_text,
            evidence_refs=[EvidenceRef(id=e) for e in (state.get("evidence_refs") or [])],
            kb_refs=list(state.get("kb_refs") or []),
            gt_refs=list(state.get("gt_refs") or []),
            tool_calls=counters.tool_calls,
            llm_calls=counters.llm_calls,
            steps=counters.steps,
            metadata={"decision_action": d.action, "plugins": state.get("plugins_loaded") or []},
        )
        status = AgentStatus.COMPLETED.value
        if result.conclusion == Conclusion.BLOCKED:
            status = AgentStatus.BLOCKED.value
        elif d.action == DecisionAction.FAIL.value:
            status = AgentStatus.FAILED.value
        return {"result": result.model_dump(), "status": status}

    def route_after_decide(state: AgentState) -> Literal["execute", "assemble"]:
        d = state.get("pending_decision")
        if isinstance(d, dict):
            d = Decision.model_validate(d)
        if d and d.action in {DecisionAction.CALL_TOOL.value, DecisionAction.RETRY.value}:
            return "execute"
        return "assemble"

    def route_after_budget(state: AgentState) -> Literal["route", "decide"]:
        # Always route then decide; budget trips handled inside decide using counters
        if state.get("routing"):
            return "decide"
        return "route"

    g: StateGraph = StateGraph(AgentState)
    g.add_node("goal_handler", node_goal)
    g.add_node("budget_guard", node_budget)
    g.add_node("hybrid_router", node_route)
    g.add_node("decision_engine", node_decide)
    g.add_node("tool_executor", node_execute)
    g.add_node("observation_pipeline", node_observe)
    g.add_node("result_assembler", node_assemble)

    g.add_edge(START, "goal_handler")
    g.add_edge("goal_handler", "budget_guard")
    g.add_conditional_edges("budget_guard", route_after_budget, {"route": "hybrid_router", "decide": "decision_engine"})
    g.add_edge("hybrid_router", "decision_engine")
    g.add_conditional_edges("decision_engine", route_after_decide, {"execute": "tool_executor", "assemble": "result_assembler"})
    g.add_edge("tool_executor", "observation_pipeline")
    g.add_edge("observation_pipeline", "budget_guard")
    g.add_edge("result_assembler", END)
    return g.compile()