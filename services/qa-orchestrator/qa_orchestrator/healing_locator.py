"""Generate and rank healing locator candidates from DOM evidence."""

from __future__ import annotations

import re

from qa_orchestrator.healing_dom import load_dom_from_path
from qa_orchestrator.locator_ranking import rank_locators
from qa_orchestrator.locator_verification import verify_locator_against_elements
from qa_orchestrator.models import (
    DiscoveredElement,
    FailureClassification,
    GeneratedLocator,
    HealingLocatorCandidate,
)


KNOWN_CHAINS: dict[str, list[str]] = {
    "search button": ["#btn_search", 'button[title="Search"]', 'button[aria-label="Search"]'],
    "P6_SKU": ["#P6_SKU", "input[name='P6_SKU']"],
    "sku": ["#P6_SKU", "input[name='P6_SKU']"],
}


def generate_candidates(
    failure: FailureClassification,
    *,
    dom_elements: list[DiscoveredElement] | None = None,
    dom_path=None,
) -> list[HealingLocatorCandidate]:
    elements = list(dom_elements or [])
    if dom_path is not None:
        elements.extend(load_dom_from_path(dom_path))

    intent = _infer_intent(failure)
    ranked_elements = _match_elements(elements, intent, failure.locator_label)
    candidates: list[HealingLocatorCandidate] = []

    for element in ranked_elements:
        loc = _locator_from_element(element)
        css = _to_css_chain(loc)
        verified, evidence = verify_locator_against_elements(loc, [element])
        confidence = _score_candidate(failure, element, loc, verified)
        candidates.append(
            HealingLocatorCandidate(
                primary=loc.primary,
                fallbacks=loc.fallbacks[:3],
                confidence=confidence,
                evidence=evidence,
                reason=_reason(failure, element, verified),
                css_selectors=css,
                validated=verified and confidence >= 0.70,
            )
        )

    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return _dedupe_candidates(candidates)


def validate_candidate(
    candidate: HealingLocatorCandidate,
    elements: list[DiscoveredElement],
) -> HealingLocatorCandidate:
    if not elements:
        candidate.validated = False
        return candidate
    if not candidate.css_selectors and candidate.primary:
        css = _playwright_code_to_css(candidate.primary)
        if css:
            candidate.css_selectors = [css]
    if not candidate.css_selectors:
        candidate.validated = False
        return candidate
    loc = GeneratedLocator(primary=candidate.primary, fallbacks=candidate.fallbacks, source="OBSERVED")
    verified, evidence = verify_locator_against_elements(loc, elements)
    candidate.validated = verified
    if evidence:
        candidate.evidence = evidence
    return candidate


def _locator_from_element(element: DiscoveredElement) -> GeneratedLocator:
    ranked = rank_locators(
        {
            "tag": element.tag,
            "role": element.role,
            "name": element.name,
            "text": element.text,
            "attributes": element.attributes,
        }
    )
    primary = ranked[0] if ranked else None
    if not primary:
        return GeneratedLocator(primary=f"page.locator('{element.tag}')", source="FALLBACK", confidence=0.3)
    return GeneratedLocator(
        primary=primary.playwright_code,
        fallbacks=[c.playwright_code for c in ranked[1:4]],
        source="OBSERVED",
        confidence=0.8,
        playwright_code=primary.playwright_code,
    )


def _to_css_chain(loc: GeneratedLocator) -> list[str]:
    selectors: list[str] = []
    for code in [loc.primary, *loc.fallbacks]:
        css = _playwright_code_to_css(code)
        if css:
            selectors.append(css)
    return selectors


def _playwright_code_to_css(code: str) -> str | None:
    test_id = re.search(r"getByTestId\('([^']+)'\)", code)
    if test_id:
        return f'[data-testid="{test_id.group(1)}"]'
    role = re.search(r"getByRole\('([^']+)',\s*\{\s*name:\s*'([^']+)'", code)
    if role:
        safe = role.group(2).replace('"', '\\"')
        if role.group(1) == "button":
            return f'button[aria-label="{safe}"]'
        return f'{role.group(1)}[aria-label="{safe}"]'
    placeholder = re.search(r"getByPlaceholder\('([^']+)'\)", code)
    if placeholder:
        return f'[placeholder="{placeholder.group(1)}"]'
    loc = re.search(r"locator\('([^']+)'\)", code)
    if loc:
        return loc.group(1)
    return None


def _infer_intent(failure: FailureClassification) -> str:
    label = (failure.locator_label or "").lower()
    msg = failure.error_message.lower()
    if "search" in label or "search" in msg:
        return "search"
    if "sku" in label or "sku" in msg or "item" in label:
        return "sku"
    return label or "element"


def _match_elements(
    elements: list[DiscoveredElement],
    intent: str,
    label: str | None,
) -> list[DiscoveredElement]:
    if not elements:
        return []
    scored: list[tuple[float, DiscoveredElement]] = []
    label_l = (label or "").lower()
    for el in elements:
        hay = f"{el.role} {el.name} {el.text} {' '.join(el.attributes.values())}".lower()
        score = 0.0
        if intent == "search" and ("search" in hay or el.tag == "button"):
            score += 0.5
        if intent == "sku" and ("sku" in hay or "item" in hay or el.tag == "input"):
            score += 0.5
        if label_l and label_l in hay:
            score += 0.3
        if el.attributes.get("data-testid") == "search-button" and intent == "search":
            score += 0.2
        if score > 0:
            scored.append((score, el))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [el for _, el in scored] or elements[:3]


def _score_candidate(
    failure: FailureClassification,
    element: DiscoveredElement,
    loc: GeneratedLocator,
    verified: bool,
) -> float:
    score = 0.55 if verified else 0.45
    if failure.original_locator and failure.original_locator in loc.primary:
        score += 0.05
    if element.role == "button" and "search" in (element.name or element.text).lower():
        score += 0.25
    if element.attributes.get("aria-label"):
        score += 0.1
    if "Search Products" in (element.name or element.text):
        score += 0.15
    old_chain = KNOWN_CHAINS.get((failure.locator_label or "").lower(), [])
    css = _playwright_code_to_css(loc.primary) or ""
    if old_chain and css not in old_chain:
        score += 0.08
    return min(0.98, round(score, 2))


def _reason(failure: FailureClassification, element: DiscoveredElement, verified: bool) -> str:
    base = failure.original_locator or "original selector"
    target = element.name or element.text or element.attributes.get("aria-label") or element.tag
    if verified:
        return f"{base} no longer matches; role/name evidence still matches '{target}'"
    return f"Candidate derived from DOM for '{target}' — requires review"


def _dedupe_candidates(candidates: list[HealingLocatorCandidate]) -> list[HealingLocatorCandidate]:
    seen: set[str] = set()
    out: list[HealingLocatorCandidate] = []
    for candidate in candidates:
        if candidate.primary in seen:
            continue
        seen.add(candidate.primary)
        out.append(candidate)
    return out
