"""Parameter trace parsing and BF-PRODUCT-003 SKU path."""

from __future__ import annotations

from pathlib import Path

from qa_orchestrator.param_validator import params_to_env, validate_run_params
from qa_orchestrator.playwright_runner import parse_param_trace_output, seed_param_trace_from_params

REPO = Path(__file__).resolve().parents[2]
FLOWS_SPEC = REPO / "apps" / "automation" / "tests" / "product" / "BF-PRODUCT-FLOWS.spec.ts"


def test_params_to_env_sku():
    validated = validate_run_params({"sku": "552811DUDABA00"})
    env = params_to_env(validated)
    assert env["QA_PARAM_SKU"] == "552811DUDABA00"


def test_seed_param_trace_from_suite_params():
    seed = seed_param_trace_from_params({"sku": "552811DUDABA00"})
    assert seed["request_sku"] == "552811DUDABA00"
    assert seed["validated_sku"] == "552811DUDABA00"
    assert seed["suite_parameter"] == "552811DUDABA00"


def test_parse_param_trace_from_playwright_stderr():
    stderr = """
PARAM_TRACE:request_sku=552811DUDABA00
PARAM_TRACE:input_value=552811DUDABA00
PARAM_TRACE:search_action=click_search_button
"""
    trace = parse_param_trace_output("", stderr)
    assert trace["request_sku"] == "552811DUDABA00"
    assert trace["input_value"] == "552811DUDABA00"
    assert trace["search_action"] == "click_search_button"


def test_bf_product_003_positive_test_executes_sku_search():
    text = FLOWS_SPEC.read_text(encoding="utf-8")
    assert "searchItemCode" in text
    assert "getSkuParam" in text
    assert "toHaveValue" in text
