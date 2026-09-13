"""Verify generated locators against captured exploration DOM evidence."""

from __future__ import annotations

import re

from qa_orchestrator.models import DiscoveredElement, ExplorationResult, GeneratedAction, GeneratedLocator


def verify_locator_against_elements(
    locator: GeneratedLocator,
    elements: list[DiscoveredElement],
) -> tuple[bool, str]:
    """Return (verified, evidence) when exploration contains a matching element."""
    if not elements:
        return False, "no exploration elements available"

    primary = locator.primary
    for element in elements:
        if _locator_matches_element(primary, element):
            return True, f"matched element {element.element_id} ({element.role}/{element.name})"
        for candidate in element.locator_candidates:
            if candidate.playwright_code == primary or candidate.playwright_code in locator.fallbacks:
                return True, f"matched candidate rank {candidate.rank} on {element.element_id}"

    haystack = " ".join(
        f"{el.role} {el.name} {el.text} {' '.join(el.attributes.values())}" for el in elements
    ).lower()
    tokens = _extract_locator_tokens(primary)
    if tokens and all(t in haystack for t in tokens):
        return True, f"token match in exploration DOM: {', '.join(tokens)}"

    return False, "no observed element matches generated locator"


def verify_action_locators(
    actions: list[GeneratedAction],
    exploration: ExplorationResult | None,
) -> list[dict[str, object]]:
    elements = list(exploration.elements) if exploration else []
    results: list[dict[str, object]] = []
    for action in actions:
        if not action.locator:
            continue
        verified, evidence = verify_locator_against_elements(action.locator, elements)
        action.locator_verified = verified  # type: ignore[attr-defined]
        results.append(
            {
                "locator": action.locator.primary,
                "locator_verified": verified,
                "evidence": evidence,
                "source": action.locator.source,
            }
        )
    return results


def _locator_matches_element(primary: str, element: DiscoveredElement) -> bool:
    for candidate in element.locator_candidates:
        if candidate.playwright_code == primary:
            return True
    if element.attributes.get("data-testid") and f"getByTestId('{element.attributes['data-testid']}')" in primary:
        return True
    if element.role and element.name and f"getByRole('{element.role}', {{ name: '{element.name}'" in primary:
        return True
    if element.name and f"name: '{element.name}'" in primary:
        return True
    return False


def _extract_locator_tokens(primary: str) -> list[str]:
    tokens: list[str] = []
    for match in re.finditer(r"'([^']+)'", primary):
        value = match.group(1).strip().lower()
        if len(value) >= 2 and value not in {"textbox", "button", "input"}:
            tokens.append(value)
    return tokens
