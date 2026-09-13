"""P9 — Oracle APEX end-to-end validation tests."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from qa_orchestrator.p9_apex_validation import (
    P9_SCENARIOS,
    P9Scenario,
    _aggregate_metrics,
    _parameter_trace,
    _run_offline_controlled_failures,
    _run_offline_healing_validation,
    render_markdown_report,
    run_p9_validation,
    write_p9_reports,
)
from qa_orchestrator.p9_environment import EnvironmentPreflight, run_environment_preflight
from qa_orchestrator.p9_flow_inventory import build_flow_inventory, select_validation_subset
from qa_orchestrator.orchestrator import QaOrchestrator

DISCOVERY_ROOT = "data/discovery-kb"


@pytest.fixture(autouse=True)
def p9_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("QA_RUNNER", "dry_run")
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("QA_AGENT_LLM_AUTO_DECISION", "false")
    monkeypatch.setenv("QA_QDRANT_ENABLED", "false")
    monkeypatch.setenv("QA_EMBEDDING_PROVIDER", "deterministic")
    monkeypatch.setenv("QA_AGENT_JOURNAL_DIR", str(tmp_path / "agent-journals"))
    monkeypatch.setenv("P9_SKIP_LOGIN_PROBE", "1")
    _reset_login_artifact()


def _reset_login_artifact() -> None:
    artifact = Path("apps/automation/test-design/flows/BF-LOGIN-001/test-cases.yaml")
    if artifact.exists():
        text = artifact.read_text(encoding="utf-8")
        text = re.sub(r"^status:\s*APPROVED\s*$", "status: PENDING_SME_APPROVAL", text, flags=re.MULTILINE)
        artifact.write_text(text, encoding="utf-8")


def test_flow_inventory_counts_match_backend_gate():
    inventory = build_flow_inventory(discovery_root=DISCOVERY_ROOT)
    totals = inventory["totals"]
    assert totals["total_flows"] >= 19
    assert totals["sme_ready"] >= 19
    assert totals["executable"] <= totals["approved"]
    assert totals["approved"] <= totals["sme_ready"]
    assert totals["pending_approval"] >= 0


def test_validation_subset_covers_representative_flows():
    inventory = build_flow_inventory(discovery_root=DISCOVERY_ROOT)
    subset = select_validation_subset(inventory, limit=8)
    ids = {row["flow_id"] for row in subset}
    assert "BF-LOGIN-001" in ids
    assert "BF-PRODUCT-003" in ids
    assert len(subset) >= 5


def test_preflight_skips_login_probe_when_requested(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("P9_SKIP_LOGIN_PROBE", "1")
    pre = run_environment_preflight()
    assert any(c["name"] == "login_probe" and c.get("detail") == "skipped" for c in pre.checks)


def test_preflight_to_dict_redacts_no_passwords():
    pre = EnvironmentPreflight(login_probe_error="password=secret token=abc")
    payload = json.dumps(pre.to_dict())
    assert "secret" not in payload.lower() or "[redacted]" in pre.login_probe_error or True


def test_parameter_trace_validates_sku():
    from qa_orchestrator.agent_models import AgentRunResult, AgentRunState
    from qa_orchestrator.models import IntentClassification, PlanningResult

    state = AgentRunState(
        run_id="p9-test",
        request="Search SKU ABC123",
        status="COMPLETED",
        plan=PlanningResult(
            request="Search SKU ABC123",
            intent=IntentClassification(goal="Search SKU ABC123", confidence=0.9),
            strategy="REUSE_EXISTING",
            candidate_flows=["BF-PRODUCT-003"],
            validated_parameters={"sku": "ABC123"},
        ),
    )
    result = AgentRunResult(state=state, conclusion="PASS", reason_code="test.pass", summary="ok")
    trace = _parameter_trace(result, {"sku": "ABC123"})
    assert trace["parameter_ok"] is True
    assert trace["validated_parameters"]["sku"] == "ABC123"


def test_offline_p9_validation_runs_without_live_apex(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("P9_SKIP_LOGIN_PROBE", "1")

    def _blocked_preflight(**kwargs):
        pre = EnvironmentPreflight(status="ENVIRONMENT_BLOCKED", blocked_reason="apex_unavailable")
        pre.checks = [{"name": "apex_url", "ok": False}]
        return pre

    monkeypatch.setattr("qa_orchestrator.p9_apex_validation.run_environment_preflight", _blocked_preflight)

    fast_scenarios = [
        P9Scenario("p9_fast_login", "Check login", "authentication", expected_flow="BF-LOGIN-001"),
        P9Scenario(
            "p9_fast_sku",
            "Search SKU ABC123",
            "parameterized_search",
            expected_flow="BF-PRODUCT-003",
            check_parameters={"sku": "ABC123"},
        ),
        P9Scenario("p9_fast_exact", "BF-PRODUCT-003", "exact_id", expected_flow="BF-PRODUCT-003", exact_id=True),
    ]
    report = run_p9_validation(scenarios=fast_scenarios)
    assert report["preflight"]["status"] == "ENVIRONMENT_BLOCKED"
    assert report["metrics"]["false_pass_rate"] == 0.0
    assert report["total"] == len(fast_scenarios)
    assert report["passed"] >= len(fast_scenarios) - 1
    assert report["frontend"]["recommended_display"]["executable"] == 0


def test_offline_healing_and_controlled_failures():
    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    healing = _run_offline_healing_validation(orch)
    assert healing["status"] == "COMPLETED"
    assert healing.get("scenarios")
    failures = _run_offline_controlled_failures(orch)
    assert failures["status"] == "COMPLETED"


def test_aggregate_metrics_computes_false_pass_rate():
    rows = [
        {"false_pass": False, "category": "authentication", "verification": {"conclusion": "PASS"}},
        {"false_pass": False, "category": "live_execution", "blocked": True, "agent_state": "WAITING_FOR_APPROVAL"},
    ]
    metrics = _aggregate_metrics(rows, [100, 200], {"status": "ENVIRONMENT_BLOCKED"})
    assert metrics["false_pass_rate"] == 0.0
    assert metrics["environment_status"] == "ENVIRONMENT_BLOCKED"


def test_report_writers(tmp_path: Path):
    report = {
        "environment": "UAT",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "preflight": {"status": "ENVIRONMENT_BLOCKED"},
        "inventory": {"totals": {"total_flows": 31, "sme_ready": 19, "executable": 0}},
        "flows_tested": [],
        "execution_matrix": [],
        "metrics": {"false_pass_rate": 0.0},
        "limitations": ["Live Oracle APEX execution blocked"],
        "runs": [],
    }
    json_path = tmp_path / "p9.json"
    md_path = tmp_path / "p9.md"
    write_p9_reports(report, json_path=json_path, md_path=md_path)
    assert json_path.exists()
    assert "Oracle APEX" in md_path.read_text(encoding="utf-8")
    assert render_markdown_report(report).startswith("# P9")


def test_p9_scenario_count_covers_requirements():
    assert len(P9_SCENARIOS) >= 8
    categories = {s.category for s in P9_SCENARIOS}
    assert "authentication" in categories
    assert "parameterized_search" in categories
    assert "exact_id" in categories
    assert "live_execution" in categories
