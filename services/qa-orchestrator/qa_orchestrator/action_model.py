"""Convert exploration evidence into structured generated actions."""

from __future__ import annotations

from qa_orchestrator.locator_ranking import best_locator, rank_locators
from qa_orchestrator.models import (
    DiscoveredElement,
    DiscoveryCandidate,
    ExplorationResult,
    GeneratedAction,
    GeneratedLocator,
    GeneratedTestCase,
    LocatorCandidate,
)
from qa_orchestrator.page_object_registry import resolve_page_object


def locator_from_element(element: DiscoveredElement, *, source: str = "OBSERVED") -> GeneratedLocator:
    ranked = element.locator_candidates or rank_locators(
        {
            "tag": element.tag,
            "role": element.role,
            "name": element.name,
            "text": element.text,
            "attributes": element.attributes,
        }
    )
    primary = best_locator(ranked)
    if not primary:
        return GeneratedLocator(
            primary=f"page.locator('{element.tag}')",
            source="FALLBACK",  # type: ignore[arg-type]
            confidence=0.3,
            playwright_code=f"page.locator('{element.tag}')",
        )
    return GeneratedLocator(
        primary=primary.playwright_code,
        fallbacks=[c.playwright_code for c in ranked[1:4]],
        source=source,  # type: ignore[arg-type]
        confidence=max(0.4, 1.0 - (primary.rank - 1) * 0.1),
        playwright_code=primary.playwright_code,
    )


def _find_element(
    elements: list[DiscoveredElement],
    *,
    keywords: tuple[str, ...],
) -> DiscoveredElement | None:
    for el in elements:
        hay = f"{el.name} {el.text} {el.role} {el.tag} {' '.join(el.attributes.values())}".lower()
        if any(k in hay for k in keywords):
            return el
    return None


def build_action_model(
    test_case: GeneratedTestCase,
    *,
    exploration: ExplorationResult | None = None,
    candidate: DiscoveryCandidate | None = None,
) -> list[GeneratedAction]:
    elements: list[DiscoveredElement] = []
    if exploration:
        elements.extend(exploration.elements)
    if candidate:
        elements.extend(candidate.elements)

    binding = resolve_page_object(test_case.flow_id)
    actions: list[GeneratedAction] = []

    if binding and test_case.flow_id in {"BF-PRODUCT-003", "BF-PRODUCT-004", "BF-HOME-010-01"}:
        if any(s.action == "authenticate" for s in test_case.steps):
            actions.append(
                GeneratedAction(
                    type="page_object",
                    page_object=binding.class_name,
                    page_object_method="openItemSearch" if binding.class_name == "HomePage" else "expectLoaded",
                )
            )
        if "sku" in test_case.test_data or test_case.polarity == "parameterized":
            actions.extend(
                [
                    GeneratedAction(
                        type="page_object",
                        page_object="ProductSearchPage",
                        page_object_method="searchItemCode",
                        value_source="QA_PARAM_SKU",
                    ),
                    GeneratedAction(
                        type="page_object",
                        page_object="ProductSearchPage",
                        page_object_method="expectResultRegion",
                        expectation="Product result matching QA_PARAM_SKU is displayed",
                    ),
                ]
            )
            return actions

    sku_el = _find_element(elements, keywords=("sku", "item", "search"))
    search_el = _find_element(elements, keywords=("search",))
    result_el = _find_element(elements, keywords=("result", "product", "region"))
    filter_el = _find_element(elements, keywords=("filter",))

    for step in test_case.steps:
        if step.action == "fill" and sku_el:
            loc = locator_from_element(sku_el)
            actions.append(
                GeneratedAction(
                    type="fill",
                    locator=loc,
                    value_source=test_case.test_data.get("sku", "QA_PARAM_SKU"),
                )
            )
        elif step.action == "click" and search_el:
            actions.append(
                GeneratedAction(type="click", locator=locator_from_element(search_el))
            )
        elif step.action == "click" and filter_el:
            actions.append(
                GeneratedAction(type="click", locator=locator_from_element(filter_el))
            )
        elif step.action == "assert":
            target = result_el or filter_el or sku_el
            expectation = step.expected or test_case.expected
            if target:
                actions.append(
                    GeneratedAction(
                        type="assert",
                        locator=locator_from_element(target),
                        expectation=expectation,
                    )
                )
            else:
                actions.append(
                    GeneratedAction(
                        type="assert",
                        expectation=expectation,
                    )
                )
        elif step.action == "navigate":
            actions.append(GeneratedAction(type="navigate"))
        elif step.action == "authenticate":
            actions.append(
                GeneratedAction(
                    type="page_object",
                    page_object="HomePage",
                    page_object_method="openItemSearch",
                )
            )

    if not actions:
        actions.append(
            GeneratedAction(
                type="assert",
                expectation=test_case.expected,
            )
        )
    return actions
