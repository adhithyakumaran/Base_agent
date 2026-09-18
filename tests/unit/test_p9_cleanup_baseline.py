"""P9 cleanup + baseline approval preparation tests."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from qa_orchestrator.bootstrap_approval import (
    BOOTSTRAP_REASON,
    BOOTSTRAP_SOURCE,
    bootstrap_approve_sme_ready_flows,
    bootstrap_approvals_enabled,
)
from qa_orchestrator.execution_gate import ExecutionGate
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.p9_apex_validation import render_markdown_report, write_p9_reports
from qa_orchestrator.p9_flow_inventory import (
    build_flow_inventory,
    canonical_inventory_summary,
    list_duplicate_flow_ids_in_index,
)
from qa_orchestrator.p9_metrics import compute_parameter_traceability_rate, parameter_traceability_applicable
from qa_orchestrator.param_validator import params_to_env

DISCOVERY_ROOT = "data/discovery-kb"


def _row(expected: dict | None, ok: bool) -> dict:
    return {"parameter_trace": {"expected": expected or {}, "parameter_ok": ok}}


def test_parameter_traceability_rate_bounds():
    assert compute_parameter_traceability_rate([]) is None
    assert compute_parameter_traceability_rate([_row({"sku": "A"}, True)]) == 1.0
    assert compute_parameter_traceability_rate([_row({"sku": "A"}, False)]) == 0.0
    assert compute_parameter_traceability_rate([_row({"sku": "A"}, True), _row({"sku": "B"}, False)]) == 0.5
    mixed = [
        _row(None, True),
        _row({"sku": "A"}, True),
        _row({"sku": "B"}, True),
        _row({"sku": "C"}, False),
    ]
    assert compute_parameter_traceability_rate(mixed) == pytest.approx(2 / 3, rel=1e-3)
    rate = compute_parameter_traceability_rate([_row({"sku": "A"}, True)] * 3)
    assert rate == 1.0
    assert (rate or 0) <= 1.0


def test_parameter_traceability_zero_applicable_returns_null():
    rows = [_row({}, True), _row({}, True)]
    assert compute_parameter_traceability_rate(rows) is None
    assert not parameter_traceability_applicable(rows[0])


def test_natural_language_sku_env_chain():
    validated = {"sku": "ABC123"}
    env = params_to_env(validated)
    assert env["QA_PARAM_SKU"] == "ABC123"


def test_index_has_no_duplicate_bf_home_010_c01():
    dupes = list_duplicate_flow_ids_in_index(discovery_root=DISCOVERY_ROOT)
    assert "BF-HOME-010-C01" not in dupes
    assert dupes == []


def test_duplicate_flow_detection_regression():
    index = Path(DISCOVERY_ROOT) / "flows" / "index.yaml"
    raw = index.read_text(encoding="utf-8")
    sme_hits = re.findall(r"^\s+-\s+(BF-[A-Z0-9-]+)\s*$", raw, flags=re.MULTILINE)
    assert sme_hits.count("BF-HOME-010-C01") == 1


def test_p9_json_and_markdown_inventory_match(tmp_path: Path):
    inventory = build_flow_inventory(discovery_root=DISCOVERY_ROOT)
    summary = inventory["inventory_summary"]
    report = {
        "environment": "UAT",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "preflight": {"status": "ENVIRONMENT_BLOCKED"},
        "inventory": inventory,
        "inventory_summary": summary,
        "flows_tested": [],
        "execution_matrix": [],
        "metrics": {"parameter_traceability_rate": None},
        "limitations": [],
        "runs": [],
    }
    json_path = tmp_path / "p9.json"
    md_path = tmp_path / "p9.md"
    write_p9_reports(report, json_path=json_path, md_path=md_path)
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    md = md_path.read_text(encoding="utf-8")
    for key, value in loaded["inventory_summary"].items():
        assert str(value) in md
    assert canonical_inventory_summary(loaded["inventory"]) == loaded["inventory_summary"]


def test_bootstrap_disabled_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("QA_BOOTSTRAP_APPROVALS", raising=False)
    assert bootstrap_approvals_enabled() is False
    with pytest.raises(RuntimeError, match="disabled"):
        bootstrap_approve_sme_ready_flows(enabled=False)


def _write_min_workspace(tmp_path: Path) -> tuple[Path, Path]:
    discovery = tmp_path / "discovery-kb"
    automation = tmp_path / "automation"
    flows_dir = discovery / "flows"
    flows_dir.mkdir(parents=True)
    (flows_dir / "index.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "flow_kb_index_v1",
                "sme_ready": ["BF-LOGIN-001", "BF-DRAFT-001", "BF-REJECT-001"],
                "flows": [
                    {"id": "BF-LOGIN-001", "file": "BF-LOGIN-001.yaml", "name": "Login", "status": "READY"},
                    {"id": "BF-DRAFT-001", "file": "BF-DRAFT-001.yaml", "name": "Draft", "status": "DRAFT"},
                    {"id": "BF-REJECT-001", "file": "BF-REJECT-001.yaml", "name": "Reject", "status": "READY"},
                ],
            }
        ),
        encoding="utf-8",
    )
    for fid in ("BF-LOGIN-001", "BF-DRAFT-001", "BF-REJECT-001"):
        (flows_dir / f"{fid}.yaml").write_text(
            yaml.safe_dump({"flow_id": fid, "flow_name": fid, "purpose": "test"}),
            encoding="utf-8",
        )
    catalog = automation / "catalog" / "index.yaml"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text(
        yaml.safe_dump(
            {
                "schema": "automation_catalog_v1",
                "flows": [
                    {"flow_id": "BF-LOGIN-001", "flow_name": "Login"},
                    {"flow_id": "BF-REJECT-001", "flow_name": "Reject"},
                ],
            }
        ),
        encoding="utf-8",
    )
    for fid, status in (
        ("BF-LOGIN-001", "PENDING_SME_APPROVAL"),
        ("BF-DRAFT-001", "PENDING_SME_APPROVAL"),
        ("BF-REJECT-001", "REJECTED"),
    ):
        design = automation / "test-design" / "flows" / fid
        design.mkdir(parents=True, exist_ok=True)
        (design / "test-cases.yaml").write_text(f"flow_id: {fid}\nstatus: {status}\n", encoding="utf-8")
    return discovery, automation


def test_bootstrap_approves_only_sme_ready_catalog_flows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    discovery, automation = _write_min_workspace(tmp_path)
    monkeypatch.setenv("QA_BOOTSTRAP_APPROVALS", "true")
    monkeypatch.setenv("QA_BOOTSTRAP_ACTOR", "bootstrap-system")
    summary = bootstrap_approve_sme_ready_flows(
        discovery_root=str(discovery),
        automation_dir=str(automation),
        enabled=True,
    )
    assert "BF-LOGIN-001" in summary.approved
    assert "BF-DRAFT-001" not in summary.approved
    assert "BF-REJECT-001" in summary.rejected
    assert any(b.flow_id == "BF-DRAFT-001" for b in summary.blocked)


def test_bootstrap_writes_audit_record_and_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    discovery, automation = _write_min_workspace(tmp_path)
    monkeypatch.setenv("QA_BOOTSTRAP_APPROVALS", "true")
    summary = bootstrap_approve_sme_ready_flows(
        discovery_root=str(discovery),
        automation_dir=str(automation),
        enabled=True,
    )
    log = json.loads((automation / "approval" / "approval-log.json").read_text(encoding="utf-8"))
    rec = [r for r in log["records"] if r["flowId"] == "BF-LOGIN-001"][-1]
    assert rec["source"] == BOOTSTRAP_SOURCE
    assert rec["reason"] == BOOTSTRAP_REASON
    assert rec["status"] == "APPROVED"
    yaml_text = (automation / "test-design" / "flows" / "BF-LOGIN-001" / "test-cases.yaml").read_text(
        encoding="utf-8"
    )
    assert "status: APPROVED" in yaml_text
    gate = ExecutionGate(FlowKnowledgeGraph(discovery_root=str(discovery), automation_dir=str(automation)))
    decision = gate.evaluate("BF-LOGIN-001")
    assert decision.executable
    assert decision.reason_code == "gate.executable"
    assert summary.to_dict()["counts"]["executable_after"] >= 1


def test_bootstrap_stale_not_produced_on_fresh_approval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    discovery, automation = _write_min_workspace(tmp_path)
    monkeypatch.setenv("QA_BOOTSTRAP_APPROVALS", "true")
    summary = bootstrap_approve_sme_ready_flows(
        discovery_root=str(discovery),
        automation_dir=str(automation),
        enabled=True,
    )
    assert summary.stale == []


def test_canonical_inventory_fields_present():
    inventory = build_flow_inventory(discovery_root=DISCOVERY_ROOT)
    summary = inventory["inventory_summary"]
    for key in (
        "total_flows",
        "sme_ready_flows",
        "approved_flows",
        "executable_flows",
        "pending_approval_flows",
        "stale_flows",
        "blocked_flows",
    ):
        assert key in summary
    assert summary["approved_flows"] >= summary["executable_flows"]


def test_controlled_dev_approved_sme_ready_catalog_flows_executable(monkeypatch: pytest.MonkeyPatch):
    """YAML APPROVED without a fresh approval-log row yields 0 executable in the console."""
    monkeypatch.setenv("QA_BOOTSTRAP_APPROVALS", "true")
    bootstrap_approve_sme_ready_flows(enabled=True)
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)
    gate = ExecutionGate(graph)
    sme_ready = list(dict.fromkeys(graph.flow_kb.index.get("sme_ready") or []))
    stale_approved: list[str] = []
    for flow_id in sme_ready:
        if not graph.is_automated(flow_id):
            continue
        artifact = gate.design_root / flow_id / "test-cases.yaml"
        if not artifact.exists():
            continue
        raw = artifact.read_text(encoding="utf-8")
        if not re.search(r"^status:\s*APPROVED\s*$", raw, re.MULTILINE):
            continue
        decision = gate.evaluate(flow_id)
        if not decision.executable and decision.reason_code == "approval.stale":
            stale_approved.append(flow_id)
    assert stale_approved == [], (
        "Approved SME-ready catalog flows have stale/missing approval audit — "
        "run: python3 scripts/approve-sme-ready-flows.py --enable"
    )
    summary = build_flow_inventory(discovery_root=DISCOVERY_ROOT)["inventory_summary"]
    assert summary["executable_flows"] == summary["approved_flows"]
