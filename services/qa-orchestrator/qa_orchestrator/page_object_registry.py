"""Map flows to existing Playwright page objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PageObjectBinding:
    flow_id: str
    class_name: str
    import_path: str
    fixture_name: str | None
    methods: dict[str, str]


FLOW_PAGE_OBJECTS: dict[str, PageObjectBinding] = {
    "BF-LOGIN-001": PageObjectBinding(
        "BF-LOGIN-001",
        "LoginPage",
        "../../src/pages/login.page",
        "loginPage",
        {"goto": "goto", "login": "login"},
    ),
    "BF-LOGOUT-002": PageObjectBinding(
        "BF-LOGOUT-002",
        "HomePage",
        "../../src/pages/home.page",
        "authenticatedPage",
        {"signOut": "signOut"},
    ),
    "BF-PRODUCT-003": PageObjectBinding(
        "BF-PRODUCT-003",
        "ProductSearchPage",
        "../../src/pages/product-search.page",
        "productSearchPage",
        {
            "expectLoaded": "expectLoaded",
            "searchItemCode": "searchItemCode",
            "expectResultRegion": "expectResultRegion",
        },
    ),
    "BF-PRODUCT-004": PageObjectBinding(
        "BF-PRODUCT-004",
        "ProductSearchPage",
        "../../src/pages/product-search.page",
        "productSearchPage",
        {"searchItemCode": "searchItemCode", "expectResultRegion": "expectResultRegion"},
    ),
    "BF-HOME-010-01": PageObjectBinding(
        "BF-HOME-010-01",
        "HomePage",
        "../../src/pages/home.page",
        "authenticatedPage",
        {"openItemSearch": "openItemSearch"},
    ),
    "BF-PRODUCT-STOCK-VISIBILITY-009": PageObjectBinding(
        "BF-PRODUCT-STOCK-VISIBILITY-009",
        "StockVisibilityPage",
        "../../src/pages/stock-visibility.page",
        "stockVisibilityPage",
        {"open": "open"},
    ),
}

FLOW_DOMAIN: dict[str, str] = {
    "BF-LOGIN-001": "auth",
    "BF-LOGOUT-002": "auth",
    "BF-PRODUCT-003": "product",
    "BF-PRODUCT-004": "product",
    "BF-BEST-DEAL-008": "product",
    "BF-PRODUCT-CATALOGUE-006": "product",
    "BF-HOME-010": "home",
    "BF-HOME-010-01": "home",
    "BF-HOME-010-C01": "home",
    "BF-RIVAAH-005": "rivaah",
    "BF-ADMINISTRATION-009": "admin",
    "BF-MANUAL-INVOICE-009": "billing",
    "BF-REPORTS-007": "reports",
    "BF-PRODUCT-STOCK-VISIBILITY-009": "inventory",
}


def resolve_page_object(flow_id: str) -> PageObjectBinding | None:
    if flow_id in FLOW_PAGE_OBJECTS:
        return FLOW_PAGE_OBJECTS[flow_id]
    prefix = flow_id.rsplit("-", 1)[0]
    for key, binding in FLOW_PAGE_OBJECTS.items():
        if key.startswith(prefix):
            return binding
    return None


def resolve_domain(flow_id: str) -> str:
    return FLOW_DOMAIN.get(flow_id, "product")


def page_object_file_exists(automation_dir: Path, binding: PageObjectBinding) -> bool:
    rel = binding.import_path.replace("../../", "src/")
    path = automation_dir / rel.replace(".page", ".page.ts")
    return path.exists()
