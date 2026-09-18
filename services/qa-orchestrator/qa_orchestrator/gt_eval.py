"""Ground Truth helpers for Phase B validation."""

from __future__ import annotations

import re
from typing import Any

_TC_ID_RE = re.compile(r"TC-BF-[A-Z0-9-]+(?:-[A-Z0-9]+)*")


def goal_matches_gt(goal: str, fact: dict[str, Any]) -> bool:
    g = goal.lower()
    candidates = [
        str(fact.get("subject", "")),
        str(fact.get("id", "")),
        str(fact.get("flow_id", "")),
    ]
    candidates.extend(str(t) for t in fact.get("tags", []))
    return any(c and c.lower() in g for c in candidates)


def evaluate_gt_expectations(
    fact: dict[str, Any],
    execution_ok: bool,
    observation_meta: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """Return (passed, failure_reasons) from structured GT expectations only."""
    expectations = fact.get("expectations") or {}
    failures: list[str] = []

    if expectations.get("execution_ok") is True and not execution_ok:
        failures.append("execution_ok expected true")

    min_passed = expectations.get("min_passed_tests")
    if isinstance(min_passed, int) and min_passed > 0:
        passed = _count_passed_tests(observation_meta)
        if passed < min_passed:
            failures.append(f"min_passed_tests expected >= {min_passed}, got {passed}")

    if expectations.get("require_product_search_verified") is True:
        if not _product_search_verified(observation_meta):
            failures.append("product_search result_verified trace missing (PRODUCT_SEARCH_TRACE / param_trace)")

    return (len(failures) == 0, failures)


def _product_search_verified(observation_meta: list[dict[str, Any]]) -> bool:
    for meta in observation_meta:
        trace = meta.get("param_trace") or {}
        if trace.get("product_search_result_verified") == "true":
            return True
    return False


def _count_passed_tests(observation_meta: list[dict[str, Any]]) -> int:
    total = 0
    for meta in observation_meta:
        report = meta.get("playwright_report") or {}
        stats = report.get("stats") or {}
        expected = stats.get("expected")
        if isinstance(expected, int):
            total += expected
    return total


def parse_executed_test_case_ids(report_data: dict[str, Any]) -> list[str]:
    """Extract TC-BF-* ids from Playwright JSON report suites."""
    found: list[str] = []

    def walk_suite(suite: dict[str, Any]) -> None:
        for spec in suite.get("specs") or []:
            for test in spec.get("tests") or []:
                title = " ".join(
                    str(x) for x in (test.get("title") or "", spec.get("title") or "") if x
                )
                for match in _TC_ID_RE.finditer(title):
                    found.append(match.group(0))
        for child in suite.get("suites") or []:
            if isinstance(child, dict):
                walk_suite(child)

    for suite in report_data.get("suites") or []:
        if isinstance(suite, dict):
            walk_suite(suite)
    return list(dict.fromkeys(found))


def infer_test_case_ids_for_flow(flow_id: str) -> list[str]:
    """Fallback when report JSON lacks titles — primary positive case only."""
    if flow_id == "BF-PRODUCT-003":
        return ["TC-BF-PRODUCT-003-P01"]
    return []
