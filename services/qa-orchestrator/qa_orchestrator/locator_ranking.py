"""Rank Playwright locator candidates for discovered elements."""

from __future__ import annotations

from qa_orchestrator.models import LocatorCandidate


def rank_locators(raw: dict[str, object]) -> list[LocatorCandidate]:
    """Prefer test id → role+name → label → placeholder → text → css."""
    candidates: list[LocatorCandidate] = []
    tag = str(raw.get("tag") or "node").lower()
    role = str(raw.get("role") or "").lower()
    name = str(raw.get("name") or raw.get("accessibleName") or "").strip()
    text = str(raw.get("text") or "").strip()
    attrs = raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {}
    attrs = {str(k): str(v) for k, v in (attrs or {}).items()}

    test_id = attrs.get("data-testid") or attrs.get("data-test-id")
    if test_id:
        expr = f"[data-testid=\"{test_id}\"]"
        candidates.append(
            LocatorCandidate(
                strategy="testid",
                expression=expr,
                rank=1,
                playwright_code=f"page.getByTestId('{test_id}')",
            )
        )

    if role and name:
        safe_name = name.replace("'", "\\'")
        candidates.append(
            LocatorCandidate(
                strategy="role",
                expression=f"role={role}[name={name}]",
                rank=2,
                playwright_code=f"page.getByRole('{role}', {{ name: '{safe_name}' }})",
            )
        )

    label = attrs.get("aria-label") or attrs.get("title")
    if label:
        safe = label.replace("'", "\\'")
        candidates.append(
            LocatorCandidate(
                strategy="label",
                expression=f"label={label}",
                rank=3,
                playwright_code=f"page.getByLabel('{safe}')",
            )
        )

    placeholder = attrs.get("placeholder")
    if placeholder:
        safe = placeholder.replace("'", "\\'")
        candidates.append(
            LocatorCandidate(
                strategy="placeholder",
                expression=f"placeholder={placeholder}",
                rank=4,
                playwright_code=f"page.getByPlaceholder('{safe}')",
            )
        )

    if text and len(text) <= 80:
        safe = text.replace("'", "\\'")
        candidates.append(
            LocatorCandidate(
                strategy="text",
                expression=f"text={text}",
                rank=5,
                playwright_code=f"page.getByText('{safe}')",
            )
        )

    element_id = attrs.get("id")
    if element_id:
        candidates.append(
            LocatorCandidate(
                strategy="css",
                expression=f"#{element_id}",
                rank=6,
                playwright_code=f"page.locator('#{element_id}')",
            )
        )
    elif attrs.get("name"):
        nm = attrs["name"]
        candidates.append(
            LocatorCandidate(
                strategy="css",
                expression=f"{tag}[name=\"{nm}\"]",
                rank=7,
                playwright_code=f"page.locator('{tag}[name=\"{nm}\"]')",
            )
        )
    else:
        candidates.append(
            LocatorCandidate(
                strategy="css",
                expression=tag,
                rank=8,
                playwright_code=f"page.locator('{tag}')",
            )
        )

    candidates.sort(key=lambda c: c.rank)
    return candidates


def best_locator(candidates: list[LocatorCandidate]) -> LocatorCandidate | None:
    return candidates[0] if candidates else None
