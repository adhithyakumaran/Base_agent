"""Generate Playwright spec.ts from structured action models."""

from __future__ import annotations

from qa_orchestrator.codegen_bridge import invoke_codegen_bridge
from qa_orchestrator.models import GeneratedAction, GeneratedTestCase, TestPolarity, TestScenario
from qa_orchestrator.page_object_registry import resolve_domain, resolve_page_object


def generate_spec(
    *,
    scenario: TestScenario,
    test_case: GeneratedTestCase,
    actions: list[GeneratedAction],
    automation_dir=None,
) -> tuple[str, dict]:
    """Return (spec_content, bridge_metadata)."""
    bridge_meta: dict = {"bridgeAvailable": False, "serializer": "python-fallback"}
    body_lines: list[str] | None = None

    if automation_dir is not None:
        bridge = invoke_codegen_bridge(
            automation_dir,
            {
                "flow_id": test_case.flow_id,
                "test_case_id": test_case.test_case_id,
                "actions": [a.model_dump() for a in actions],
            },
        )
        bridge_meta = bridge
        if bridge.get("ok") and bridge.get("bodyLines"):
            body_lines = list(bridge["bodyLines"])

    domain = resolve_domain(test_case.flow_id)
    import_depth = "../../../"
    tags = _build_tags(test_case.flow_id, test_case.polarity, domain)
    describe_title = f"{test_case.flow_id} {scenario.title} {tags}"
    test_title = f"{test_case.test_case_id} {scenario.objective} @generated @draft"

    lines = [
        "/** GENERATED DRAFT — SME approval required before execution against UAT. */",
        f"import {{ test, expect }} from '{import_depth}src/fixtures/test-base';",
    ]

    uses_auth_fixture = any(a.page_object_method == "openItemSearch" for a in actions)
    uses_product = any(a.page_object == "ProductSearchPage" for a in actions)
    if uses_product and not uses_auth_fixture:
        lines.append(f"import {{ ProductSearchPage }} from '{import_depth}src/pages/product-search.page';")

    lines.extend(["", f"test.describe('{_escape(describe_title)}', () => {{"])

    if test_case.flow_id == "BF-LOGIN-001":
        lines.append("  test.use({ storageState: { cookies: [], origins: [] } });")
        lines.append("")

    fixture_args = _fixture_args(actions, uses_auth_fixture, uses_product)
    lines.append(f"  test('{_escape(test_title)}', async ({fixture_args}) => {{")

    if body_lines is None:
        body_lines = _render_body(actions, test_case)
    lines.extend([f"    {line}" for line in body_lines])
    lines.extend(["  });", "});", ""])
    return "\n".join(lines), bridge_meta


def _build_tags(flow_id: str, polarity: TestPolarity, domain: str) -> str:
    pol = "@parameterized" if polarity == "parameterized" else f"@{polarity}"
    return f"@{flow_id} {pol} @draft @generated @{domain.replace('_', '-')}"


def _fixture_args(actions: list[GeneratedAction], uses_auth: bool, uses_product: bool) -> str:
    args: list[str] = []
    if uses_auth:
        args.extend(["authenticatedPage", "productSearchPage"])
    elif uses_product:
        args.append("productSearchPage")
    needs_page = any(
        a.type == "assert" and a.locator
        for a in actions
    ) or not uses_auth
    if needs_page and "page" not in args:
        args.append("page")
    args.append("recordStep")
    return "{ " + ", ".join(args) + " }"


def _render_body(actions: list[GeneratedAction], test_case: GeneratedTestCase) -> list[str]:
    lines: list[str] = []
    for action in actions:
        if action.type == "page_object":
            method = action.page_object_method or "expectLoaded"
            if action.page_object == "ProductSearchPage" and method == "searchItemCode":
                if action.value_source == "QA_PARAM_SKU":
                    lines.append("const sku = process.env.QA_PARAM_SKU;")
                    lines.append("test.skip(!sku, 'QA_PARAM_SKU not set');")
                    if any(a.page_object_method == "openItemSearch" for a in actions):
                        lines.append("await authenticatedPage.openItemSearch();")
                    lines.append("await productSearchPage.searchItemCode(sku!);")
                else:
                    lines.append("await productSearchPage.searchItemCode();")
            elif method == "expectResultRegion":
                lines.append("await productSearchPage.expectResultRegion();")
                text = action.assertion_text or action.expectation or "expected business outcome"
                lines.append(f"// Business assertion [{action.assertion_source or 'EXPLORATION'}]: {text}")
            elif method == "openItemSearch":
                lines.append("await authenticatedPage.openItemSearch();")
            elif method == "expectLoaded":
                lines.append("await productSearchPage.expectLoaded();")
        elif action.type == "fill" and action.locator:
            src = action.value_source or "QA_PARAM_SKU"
            lines.append(f"const value = process.env.{src};")
            lines.append(f"test.skip(!value, '{src} not set');")
            lines.append(f"await {action.locator.primary}.fill(value!);")
        elif action.type == "click" and action.locator:
            lines.append(f"await {action.locator.primary}.click();")
        elif action.type == "assert":
            if action.page_object == "ProductSearchPage" and action.page_object_method == "expectResultRegion":
                lines.append("await productSearchPage.expectResultRegion();")
            elif action.expectation or action.assertion_text:
                text = action.assertion_text or action.expectation or ""
                source = action.assertion_source or "USER_REQUIREMENT"
                lines.append(f"// Business assertion [{source}]: {text}")
                if "result" in text.lower() or "filter" in text.lower():
                    lines.append("await productSearchPage.expectResultRegion();")
            else:
                lines.append("// MISSING business assertion — generation must not execute")
        elif action.type == "navigate":
            lines.append("// Navigate via existing fixtures/page objects during approved execution")
    if not any(
        a.type == "assert" or (a.type == "page_object" and a.page_object_method == "expectResultRegion")
        for a in actions
    ):
        text = test_case.expected or "business outcome not specified"
        lines.append(f"// Business assertion [USER_REQUIREMENT]: {text}")
        if "result" in text.lower() or test_case.flow_id.startswith("BF-PRODUCT"):
            lines.append("await productSearchPage.expectResultRegion();")
    lines.append("await recordStep('generated-draft-complete');")
    return lines


def _escape(text: str) -> str:
    return text.replace("'", "\\'")
