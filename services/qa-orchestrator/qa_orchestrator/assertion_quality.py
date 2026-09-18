"""Classify generated assertion quality and enforce traceability."""

from __future__ import annotations

import re
from typing import Literal

from qa_orchestrator.models import GeneratedAction, GeneratedTestCase, TestScenario

AssertionQuality = Literal["STRONG", "MODERATE", "WEAK", "MISSING"]
AssertionSource = Literal["USER_REQUIREMENT", "GROUND_TRUTH", "EXISTING_TEST", "EXPLORATION"]

_VISIBILITY_PATTERNS = (
    r"toBeVisible\s*\(",
    r"\.isVisible\s*\(",
    r"button is visible",
    r"element is visible",
    r"is shown$",
    r"is visible",
)
_WEAK_TARGET_PATTERNS = ("button", "input", "textbox", "field", "search button")
_STRONG_PATTERNS = (
    r"product result",
    r"matching\s+sku",
    r"matching\s+qa_param",
    r"expectResultRegion",
    r"correct product",
    r"filtered product",
    r"result for sku",
)
_MODERATE_PATTERNS = (
    r"results region",
    r"result region",
    r"region is populated",
    r"results populated",
    r"filtered results",
)


def classify_assertion_action(
    action: GeneratedAction,
    *,
    scenario: TestScenario | None = None,
    test_case: GeneratedTestCase | None = None,
    user_goal: str = "",
) -> tuple[AssertionQuality, AssertionSource | None, str]:
    """Return quality, traceable source, and assertion text for one action."""
    if action.type not in {"assert", "page_object"}:
        return "MISSING", None, ""

    text = (action.expectation or action.assertion_text or "").strip()
    method = action.page_object_method or ""

    if action.type == "page_object" and method == "expectResultRegion":
        source = _resolve_source(action, scenario=scenario, user_goal=user_goal)
        quality: AssertionQuality = "STRONG" if _mentions_specific_outcome(text, user_goal) else "MODERATE"
        assertion_text = text or "Product results region reflects applied filter or search"
        return quality, source, assertion_text

    if action.type == "page_object" and method in {"searchItemCode", "expectLoaded", "openItemSearch"}:
        return "MISSING", None, text

    if not text and action.type == "assert":
        if action.locator:
            return "WEAK", _resolve_source(action, scenario=scenario, user_goal=user_goal), "Element visibility check"
        return "MISSING", None, ""

    hay = f"{text} {method} {action.locator.primary if action.locator else ''}".lower()

    if any(re.search(p, hay) for p in _STRONG_PATTERNS):
        return "STRONG", _resolve_source(action, scenario=scenario, user_goal=user_goal), text

    if any(re.search(p, hay) for p in _MODERATE_PATTERNS):
        return "MODERATE", _resolve_source(action, scenario=scenario, user_goal=user_goal), text

    if any(re.search(p, hay) for p in _VISIBILITY_PATTERNS) or any(t in hay for t in _WEAK_TARGET_PATTERNS):
        return "WEAK", _resolve_source(action, scenario=scenario, user_goal=user_goal), text or "Visibility assertion"

    if text:
        return "MODERATE", _resolve_source(action, scenario=scenario, user_goal=user_goal), text

    return "MISSING", None, ""


def classify_actions(
    actions: list[GeneratedAction],
    *,
    scenario: TestScenario | None = None,
    test_case: GeneratedTestCase | None = None,
    user_goal: str = "",
) -> AssertionQuality:
    """Overall assertion quality — worst meaningful assert wins."""
    qualities: list[AssertionQuality] = []
    for action in actions:
        quality, source, text = classify_assertion_action(
            action,
            scenario=scenario,
            test_case=test_case,
            user_goal=user_goal,
        )
        action.assertion_quality = quality  # type: ignore[attr-defined]
        if source:
            action.assertion_source = source  # type: ignore[attr-defined]
        if text:
            action.assertion_text = text  # type: ignore[attr-defined]
        if action.type in {"assert", "page_object"} and method_is_assertion(action):
            qualities.append(quality)

    if not qualities:
        return "MISSING"
    order = {"MISSING": 0, "WEAK": 1, "MODERATE": 2, "STRONG": 3}
    return min(qualities, key=lambda q: order[q])


def method_is_assertion(action: GeneratedAction) -> bool:
    if action.type == "assert":
        return True
    return action.type == "page_object" and action.page_object_method in {"expectResultRegion"}


def status_for_assertion_quality(quality: AssertionQuality) -> str | None:
    if quality == "MISSING":
        return "INVALID"
    if quality == "WEAK":
        return "NEEDS_REVIEW"
    return None


def _mentions_specific_outcome(text: str, user_goal: str) -> bool:
    hay = f"{text} {user_goal}".lower()
    return any(k in hay for k in ("matching", "sku", "abc123", "filter", "specific", "correct product"))


def _resolve_source(
    action: GeneratedAction,
    *,
    scenario: TestScenario | None,
    user_goal: str,
) -> AssertionSource:
    if action.evidence_source:
        mapped = {
            "exploration": "EXPLORATION",
            "user_request": "USER_REQUIREMENT",
            "ground_truth": "GROUND_TRUTH",
            "existing_test": "EXISTING_TEST",
        }
        key = action.evidence_source.lower()
        for prefix, source in mapped.items():
            if key.startswith(prefix):
                return source  # type: ignore[return-value]

    if scenario and scenario.source == "EXISTING_FLOW":
        return "EXISTING_TEST"
    if scenario and scenario.source == "DISCOVERY":
        return "EXPLORATION"
    if user_goal.strip():
        return "USER_REQUIREMENT"
    if scenario and scenario.expected_outcomes:
        return "USER_REQUIREMENT"
    return "EXPLORATION"
