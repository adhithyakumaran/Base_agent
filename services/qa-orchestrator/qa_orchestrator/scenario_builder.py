"""Build TestScenario from exploration, discovery candidate, and generation request."""

from __future__ import annotations

import re

from qa_orchestrator.models import (
    DiscoveryCandidate,
    ExplorationResult,
    GenerationRequest,
    TestPolarity,
    TestScenario,
)


def build_scenario(
    *,
    flow_id: str,
    request: GenerationRequest,
    exploration: ExplorationResult | None = None,
    candidate: DiscoveryCandidate | None = None,
    goal: str = "",
    polarity: TestPolarity = "positive",
) -> TestScenario:
    objective = request.scenario_objective or goal or f"Validate {flow_id}"
    title = _title_from_objective(objective, flow_id)
    scenario_id = f"SC-{flow_id}-GEN-001"
    evidence_refs = []
    if exploration:
        evidence_refs.extend(e.path for e in exploration.evidence if e.screenshot_path)
    if candidate:
        evidence_refs.extend(e.path for e in candidate.evidence if e.screenshot_path)

    preconditions = list(request.preconditions)
    if "authenticated" not in " ".join(preconditions).lower():
        if _requires_auth(flow_id, objective):
            preconditions.insert(0, "Authenticated Endless Aisle user session")

    test_data = _normalize_test_data(request.test_data_requirements)
    actions = list(request.actions)
    expected = list(request.expected_outcomes)
    if exploration and exploration.business_signals:
        expected.extend(exploration.business_signals[:3])
    if candidate and candidate.possible_business_behavior:
        expected.extend(candidate.possible_business_behavior[:3])

    source = "DISCOVERY" if exploration or candidate else "USER_REQUEST"
    confidence = candidate.confidence if candidate else (0.7 if exploration else 0.5)

    return TestScenario(
        scenario_id=scenario_id,
        flow_id=flow_id,
        title=title,
        objective=objective,
        preconditions=preconditions,
        test_data=test_data,
        actions=actions or _actions_from_exploration(exploration, candidate),
        expected_outcomes=_dedupe(expected),
        polarity=polarity,
        source=source,
        evidence_refs=evidence_refs[:12],
        confidence=confidence,
        status="DRAFT",
    )


def _title_from_objective(objective: str, flow_id: str) -> str:
    cleaned = objective.strip().rstrip(".")
    if len(cleaned) <= 80:
        return cleaned
    return f"{flow_id} generated scenario"


def _requires_auth(flow_id: str, objective: str) -> bool:
    if flow_id == "BF-LOGIN-001":
        return False
    hay = objective.lower()
    return flow_id != "BF-LOGIN-001" and "login" not in hay


def _normalize_test_data(raw: dict[str, object]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in raw.items():
        name = str(key).lower()
        if name == "sku":
            out["sku"] = "QA_PARAM_SKU"
        else:
            out[name] = f"QA_PARAM_{name.upper()}"
    return out


def _actions_from_exploration(
    exploration: ExplorationResult | None,
    candidate: DiscoveryCandidate | None,
) -> list[str]:
    actions: list[str] = []
    if exploration:
        actions.extend(exploration.observations[:4])
    if candidate:
        for signal in candidate.possible_business_behavior[:4]:
            actions.append(signal)
    return actions or ["Inspect target page and validate business behavior"]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out
