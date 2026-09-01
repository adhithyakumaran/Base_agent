from __future__ import annotations

import re
from typing import Any

from base_agent.contracts.enums import DecisionAction, RoutingMethod
from base_agent.contracts.models import Goal, RoutingDecision
from base_agent.tools.registry import ToolRegistry


ALIAS_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"^\s*echo\b[:\s]+(?P<text>.+)$", re.I), "demo.echo", "mock.demo.echo"),
    (re.compile(r"^\s*add\b[:\s]+(?P<a>-?\d+)\s*,\s*(?P<b>-?\d+)\s*$", re.I), "demo.add", "mock.demo.add"),
    (
        re.compile(r"\b(flow catalog|list flows|application flows|apex flows)\b", re.I),
        "qa.discover",
        "qa.apex.flow_catalog",
    ),
    (re.compile(r"\bdiscover\b|\bcrawl\b|\bexplore\b|\bmap (the )?app\b", re.I), "qa.discover", "qa.apex.discover"),
    (re.compile(r"\bsanity\b", re.I), "qa.sanity", "qa.apex.sanity_probe"),
]


class GoalHandler:
    def parse(self, text: str) -> Goal:
        raw = text.strip()
        hints: list[str] = []
        entities: dict[str, Any] = {}
        intent = "execute"
        for pattern, capability, _tool in ALIAS_RULES:
            m = pattern.search(raw)
            if m:
                hints.append(capability)
                entities.update({k: v for k, v in m.groupdict().items() if v is not None})
                if capability.startswith("qa.discover"):
                    intent = "discover"
                break
        ambiguous = len(hints) == 0 and len(raw.split()) > 8
        return Goal(
            raw_text=raw,
            intent_type=intent,
            entities=entities,
            capability_hints=hints,
            ambiguity_score=0.8 if ambiguous else (0.0 if hints else 0.4),
            needs_clarification=False,
            parse_method="deterministic",
        )


class HybridRouter:
    """Rules first → capability filter → optional LLM only on remaining ambiguity."""

    def __init__(self, registry: ToolRegistry, t_high: float = 0.78, t_low: float = 0.45) -> None:
        self.registry = registry
        self.t_high = t_high
        self.t_low = t_low

    def route(self, goal: Goal) -> RoutingDecision:
        # 1) deterministic alias / hints
        for pattern, capability, tool_name in ALIAS_RULES:
            m = pattern.search(goal.raw_text)
            if m:
                if any(t.name == tool_name for t in self.registry.list()):
                    return RoutingDecision(
                        capability=capability,
                        tool_name=tool_name,
                        candidates=[tool_name],
                        method=RoutingMethod.RULE.value,
                        confidence=1.0,
                        reason_code="route.alias",
                    )

        if goal.capability_hints:
            cap = goal.capability_hints[0]
            tools = self.registry.by_capability(cap)
            if len(tools) == 1:
                return RoutingDecision(
                    capability=cap,
                    tool_name=tools[0].definition.name,
                    candidates=[tools[0].definition.name],
                    method=RoutingMethod.RULE.value,
                    confidence=0.95,
                    reason_code="route.capability_hint",
                )
            if tools:
                return RoutingDecision(
                    capability=cap,
                    tool_name=None,
                    candidates=[t.definition.name for t in tools],
                    method=RoutingMethod.RULE.value,
                    confidence=0.5,
                    reason_code="route.ambiguous_tools",
                )

        # 2) lightweight lexical semantic stand-in (no embedding dependency in core)
        scored: list[tuple[float, str, str]] = []
        q = goal.raw_text.lower()
        for d in self.registry.list():
            blob = f"{d.name} {d.capability} {d.description}".lower()
            score = 0.0
            for tok in set(re.findall(r"[a-z0-9_]+", q)):
                if len(tok) < 3:
                    continue
                if tok in blob:
                    score += 0.15
            if d.capability.replace(".", " ") in q:
                score += 0.5
            if score:
                scored.append((score, d.capability, d.name))
        scored.sort(reverse=True)
        if not scored:
            return RoutingDecision(method=RoutingMethod.RULE.value, confidence=0.0, reason_code="route.no_match")

        best_score, best_cap, best_tool = scored[0]
        second = scored[1][0] if len(scored) > 1 else 0.0
        margin = best_score - second
        if best_score >= self.t_high and margin >= 0.12:
            return RoutingDecision(
                capability=best_cap,
                tool_name=best_tool,
                candidates=[best_tool],
                method=RoutingMethod.SEMANTIC.value,
                confidence=min(best_score, 1.0),
                reason_code="route.semantic_unique",
            )
        # Ambiguous — expose candidates only; Decision Engine may ASK_USER / UNKNOWN (no LLM required)
        cands = [t for _, _, t in scored[:3]]
        return RoutingDecision(
            capability=best_cap,
            tool_name=None,
            candidates=cands,
            method=RoutingMethod.HYBRID.value,
            confidence=best_score,
            reason_code="route.ambiguous",
        )