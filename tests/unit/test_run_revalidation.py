"""Revalidation after SME Ground Truth approval (no Playwright)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qa_orchestrator.run_revalidation import revalidate_local_snapshot


def _product_execution_local() -> dict:
    return {
        "intent": {
            "goal": "Search SKU 552811DUDABA00",
            "run_type": "adhoc",
            "execution_mode": "adhoc_parameterized",
            "flow_ids": ["BF-PRODUCT-003"],
            "tags": [],
            "params": {"sku": "552811DUDABA00"},
            "confidence": 0.9,
            "reasoning": "product search",
            "classifier": "deterministic",
        },
        "execution": {
            "ok": True,
            "mode": "playwright",
            "observations": [
                {
                    "step_index": 0,
                    "action": "suite",
                    "ok": True,
                    "message": "ok",
                    "meta": {
                        "param_trace": {"product_search_result_verified": "true"},
                        "playwright_report": {"stats": {"expected": 1}},
                    },
                }
            ],
        },
        "state": {"metadata": {"executed_test_case_ids": ["TC-BF-PRODUCT-003-P01"]}},
    }


def test_revalidation_passes_with_approved_gt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gt_dir = tmp_path / "gt"
    gt_dir.mkdir()
    gt_doc = {
        "id": "gt-test-positive",
        "status": "approved",
        "flow_id": "BF-PRODUCT-003",
        "tags": ["BF-PRODUCT-003", "search sku", "product search"],
        "expectations": {
            "execution_ok": True,
            "min_passed_tests": 1,
            "require_product_search_verified": True,
        },
    }
    (gt_dir / "gt-test-positive.json").write_text(json.dumps(gt_doc), encoding="utf-8")

    discovery = tmp_path
    local = _product_execution_local()
    local["discovery_root"] = str(discovery)

    result = revalidate_local_snapshot(
        goal="Search SKU 552811DUDABA00",
        run_type="adhoc",
        run_id="run_test",
        local=local,
    )
    assert result["conclusion"] == "PASS"
    assert result["reason_code"] == "validator.gt_match"


def test_revalidation_needs_review_without_approved_gt(tmp_path: Path) -> None:
    gt_dir = tmp_path / "gt"
    gt_dir.mkdir()
    pending = {
        "id": "gt-test-pending",
        "status": "pending_sme_approval",
        "flow_id": "BF-PRODUCT-003",
        "tags": ["BF-PRODUCT-003", "search sku"],
        "expectations": {"execution_ok": True, "min_passed_tests": 1},
    }
    (gt_dir / "gt-test-pending.json").write_text(json.dumps(pending), encoding="utf-8")

    local = _product_execution_local()
    local["discovery_root"] = str(tmp_path)

    result = revalidate_local_snapshot(
        goal="Search SKU 552811DUDABA00",
        run_type="adhoc",
        run_id="run_test",
        local=local,
    )
    assert result["conclusion"] == "NEEDS_REVIEW"
    assert result["reason_code"] == "validator.pre_gt_honest"


def test_execution_failure_cannot_pass_via_revalidation(tmp_path: Path) -> None:
    gt_dir = tmp_path / "gt"
    gt_dir.mkdir()
    gt_doc = {
        "id": "gt-test-positive",
        "status": "approved",
        "flow_id": "BF-PRODUCT-003",
        "tags": ["BF-PRODUCT-003", "search sku"],
        "expectations": {"execution_ok": True, "min_passed_tests": 1},
    }
    (gt_dir / "gt-test-positive.json").write_text(json.dumps(gt_doc), encoding="utf-8")

    local = _product_execution_local()
    local["discovery_root"] = str(tmp_path)
    local["execution"]["ok"] = False

    result = revalidate_local_snapshot(
        goal="Search SKU 552811DUDABA00",
        run_type="adhoc",
        run_id="run_test",
        local=local,
    )
    assert result["conclusion"] in {"FAIL", "NEEDS_REVIEW"}
    assert result["conclusion"] != "PASS"
