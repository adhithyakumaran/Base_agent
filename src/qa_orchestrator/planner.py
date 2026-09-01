from __future__ import annotations

from typing import Any

from qa_orchestrator.kb_rag import KbRag
from qa_orchestrator.llm_client import PlannerLlmClient
from qa_orchestrator.models import ExecutionPlan, PlanStep


PLANNER_SYSTEM = """You are a QA planner for Oracle APEX Endless Aisle UAT.
Return ONLY valid JSON with keys: summary (string), steps (array).
Each step: action (navigate|click|type|wait|screenshot|assert_text), target, value, note, kb_ref.
Use KB context. No loop-until-success. Max 12 steps. Credentials come from env — never invent passwords."""


class Planner:
    def __init__(self, kb: KbRag, llm: PlannerLlmClient) -> None:
        self.kb = kb
        self.llm = llm

    def plan(
        self,
        goal: str,
        *,
        run_type: str = "adhoc",
        context_packets: list[dict[str, Any]] | None = None,
    ) -> ExecutionPlan:
        kb_context, kb_refs = self.kb.context_block(goal)
        packet_text = ""
        if context_packets:
            packet_text = "\n".join(str(p) for p in context_packets[:5])

        llm_data, llm_resp = self.llm.complete_json(
            purpose="qa_plan",
            system=PLANNER_SYSTEM,
            prompt=(
                f"Run type: {run_type}\nGoal: {goal}\n\n"
                f"KB context:\n{kb_context}\n\n"
                f"Attached context packets:\n{packet_text or '_none_'}\n\n"
                "Produce a browser execution plan for OpenClaw."
            ),
        )
        if llm_data and isinstance(llm_data.get("steps"), list):
            steps = [_step_from_dict(s) for s in llm_data["steps"][:12]]
            steps = [s for s in steps if s.action]
            if steps:
                return ExecutionPlan(
                    goal=goal,
                    run_type=run_type,
                    summary=str(llm_data.get("summary") or f"LLM plan for {goal}"),
                    steps=steps,
                    kb_refs=kb_refs,
                    planner="llm",
                )

        return self._deterministic_plan(goal, run_type=run_type, kb_refs=kb_refs, llm_error=llm_resp.error)

    def _deterministic_plan(
        self,
        goal: str,
        *,
        run_type: str,
        kb_refs: list[str],
        llm_error: str | None = None,
    ) -> ExecutionPlan:
        overview = self.kb.app_overview()
        login_url = overview.get("login_url", "https://dev-ea.titanrts.com/ords/r/tjdcom/ea/login")
        home_url = overview.get("home_url", "https://dev-ea.titanrts.com/ords/r/tjdcom/ea/home")
        g = goal.lower()

        if run_type == "sanity" or "sanity" in g or "health" in g or "morning" in g:
            steps = [
                PlanStep(action="navigate", target=login_url, note="Open login page"),
                PlanStep(action="screenshot", target="login", note="Capture login screen"),
                PlanStep(action="type", target="username", value="${APEX_USERNAME}", note="Enter username from env"),
                PlanStep(action="type", target="password", value="${APEX_PASSWORD}", note="Enter password from env"),
                PlanStep(action="click", target="login_button", note="Submit login"),
                PlanStep(action="wait", target="home", value="5", note="Wait for home"),
                PlanStep(action="navigate", target=home_url, note="Confirm home URL"),
                PlanStep(action="screenshot", target="home", note="Capture home dashboard"),
                PlanStep(action="assert_text", target="store_context", note="Verify store context visible"),
            ]
            summary = "Deterministic sanity: login + home spot-check"
        elif "find price" in g or "find_price" in g:
            steps = [
                PlanStep(action="navigate", target=login_url, note="Login first"),
                PlanStep(action="type", target="username", value="${APEX_USERNAME}"),
                PlanStep(action="type", target="password", value="${APEX_PASSWORD}"),
                PlanStep(action="click", target="login_button"),
                PlanStep(action="navigate", target=home_url.replace("/home", "/find-price"), note="Open Find Price"),
                PlanStep(action="screenshot", target="find_price"),
                PlanStep(action="assert_text", target="find_price_form", note="Find Price form visible"),
            ]
            summary = "Deterministic adhoc: Find Price module check"
        elif "sku" in g or "item search" in g or "p6" in g:
            steps = [
                PlanStep(action="navigate", target=login_url),
                PlanStep(action="type", target="username", value="${APEX_USERNAME}"),
                PlanStep(action="type", target="password", value="${APEX_PASSWORD}"),
                PlanStep(action="click", target="login_button"),
                PlanStep(action="navigate", target=home_url, note="Land on home"),
                PlanStep(action="click", target="item_search", note="Open item SKU search"),
                PlanStep(action="screenshot", target="item_search"),
            ]
            summary = "Deterministic adhoc: item SKU search"
        else:
            steps = [
                PlanStep(action="navigate", target=login_url),
                PlanStep(action="screenshot", target="login"),
                PlanStep(action="type", target="username", value="${APEX_USERNAME}"),
                PlanStep(action="type", target="password", value="${APEX_PASSWORD}"),
                PlanStep(action="click", target="login_button"),
                PlanStep(action="navigate", target=home_url),
                PlanStep(action="screenshot", target="home"),
            ]
            summary = f"Deterministic fallback plan for: {goal}"

        return ExecutionPlan(
            goal=goal,
            run_type=run_type,
            summary=summary,
            steps=steps,
            kb_refs=kb_refs,
            planner="deterministic" if not llm_error else f"deterministic_fallback({llm_error})",
        )


def _step_from_dict(raw: Any) -> PlanStep:
    if not isinstance(raw, dict):
        return PlanStep(action="custom", note=str(raw))
    action = str(raw.get("action") or "custom")
    if action not in {"navigate", "click", "type", "wait", "screenshot", "assert_text", "custom"}:
        action = "custom"
    return PlanStep(
        action=action,  # type: ignore[arg-type]
        target=str(raw.get("target") or ""),
        value=str(raw.get("value") or ""),
        note=str(raw.get("note") or ""),
        kb_ref=str(raw.get("kb_ref")) if raw.get("kb_ref") else None,
    )
