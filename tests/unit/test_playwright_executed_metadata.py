"""Executed test-case metadata must come from Playwright report stats, not flow inference."""

from qa_orchestrator.gt_eval import executed_test_case_ids_from_playwright_report


def test_no_tests_found_yields_empty_executed_ids():
    report = {"stats": {"expected": 0, "unexpected": 0}, "suites": []}
    assert executed_test_case_ids_from_playwright_report(report) == []


def test_executed_ids_only_when_expected_positive():
    report = {
        "stats": {"expected": 1, "unexpected": 0},
        "suites": [
            {
                "specs": [
                    {
                        "title": "BF-PRODUCT-004 View Product @BF-PRODUCT-004",
                        "tests": [
                            {
                                "title": "TC-BF-PRODUCT-004-P01 product detail @sanity @positive",
                            }
                        ],
                    }
                ]
            }
        ],
    }
    assert executed_test_case_ids_from_playwright_report(report) == ["TC-BF-PRODUCT-004-P01"]


def test_missing_stats_does_not_infer_executed_ids():
    report = {
        "suites": [
            {
                "specs": [
                    {
                        "title": "@BF-PRODUCT-004",
                        "tests": [{"title": "TC-BF-PRODUCT-004-P01 @positive"}],
                    }
                ]
            }
        ]
    }
    assert executed_test_case_ids_from_playwright_report(report) == []
