"""Generate Playwright spec.ts from structured action models."""

from __future__ import annotations

from qa_orchestrator.models import GeneratedAction, GeneratedTestCase, TestPolarity, TestScenario
from qa_orchestrator.page_object_registry import resolve_domain, resolve_page_object


def generate_spec(
    *,
    scenario: TestScenario,
    test_case: GeneratedTestCase,
    actions: list[GeneratedAction],
) -> str:
    domain = resolve_domain(test_case.flow_id)
    import_depth = "../../"
    tags = _build_tags(test_case.flow_id, test_case.polarity, domain)
    describe_title = f"{test_case.flow_id} {scenario.title} {tags}"
    test_title = f"{test_case.test_case_id} {scenario.objective} @generated @draft"

    lines = [
        "/** GENERATED DRAFT — SME approval required before execution against UAT. */",
        f"import {{ test, expect }} from '{import_depth}src/fixtures/test-base';",
    ]

    binding = resolve_page_object(test_case.flow_id)
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

    body = _render_body(actions, test_case)
    lines.extend([f"    {line}" for line in body])
    lines.extend(["  });", "});", ""])
    return "\n".join(lines)


def _build_tags(flow_id: str, polarity: TestPolarity, domain: str) -> str:
    pol = "@parameterized" if polarity == "parameterized" else f"@{polarity}"
    return f"@{flow_id} {pol} @draft @generated @{domain.replace('_', '-')}"


def _fixture_args(actions: list[GeneratedAction], uses_auth: bool, uses_product: bool) -> str:
    args: list[str] = []
    if uses_auth:
        args.extend(["authenticatedPage", "productSearchPage"])
    elif uses_product:
        args.append("productSearchPage")
    if not args:
        args.append("page")
    if "page" not in args:
        args.append("page")
    args.append("recordStep")
    return ", ".join(args)


def _render_body(actions: list[GeneratedAction], test_case: GeneratedTestCase) -> list[str]:
    lines: list[str] = []
    for action in actions:
        if action.type == "page_object":
            method = action.page_object_method or "expectLoaded"
            if action.page_object == "ProductSearchPage" and method == "searchItemCode":
                if action.value_source == "QA_PARAM_SKU":
                    lines.append("const sku = process.env.QA_PARAM_SKU;")
                    lines.append("test.skip(!sku, 'QA_PARAM_SKU not set');")
                    if "authenticatedPage" in _fixture_args(actions, True, True):
                        lines.append("await authenticatedPage.openItemSearch();")
                    lines.append("await productSearchPage.searchItemCode(sku!);")
                else:
                    lines.append("await productSearchPage.searchItemCode();")
            elif method == "expectResultRegion":
                lines.append(
                    "await productSearchPage.expectResultRegion();"
                )
                lines.append(
                    "// Business assertion: product result region visible for searched SKU"
                )
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
            if action.locator:
                lines.append(
                    f"await expect({action.locator.primary}).toBeVisible();"
                )
            if action.expectation and "product result" in action.expectation.lower():
                lines.append(
                    "await expect(page.locator('.t-Body-content, .t-Region, .a-IRR-table').first()).toBeVisible();"
                )
            elif action.expectation:
                lines.append(f"// Expected: {action.expectation}")
        elif action.type == "navigate":
            lines.append("// Navigate via existing fixtures/page objects during approved execution")
    if not lines:
        lines.append(f"// Draft assertion placeholder: {test_case.expected}")
        lines.append("await expect(page.locator('body')).toBeVisible();")
    lines.append("await recordStep('generated-draft-complete');")
    return lines


def _escape(text: str) -> str:
    return text.replace("'", "\\'")
