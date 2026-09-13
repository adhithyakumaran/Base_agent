"""P3.1 — approved healing locator overlay runtime consumption tests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from qa_orchestrator.healing_overlay import (
    OVERLAY_SCHEMA,
    apply_approved_proposal,
    finalize_store,
    load_overlay_store,
    resolve_overlay_selectors,
    validate_entry,
)
from qa_orchestrator.models import HealingProposal
from tests.unit.conftest_generation import _copy_automation_tree


@pytest.fixture
def automation_dir(tmp_path: Path) -> Path:
    root = tmp_path / "automation"
    _copy_automation_tree(root)
    (root / "healing" / "approved").mkdir(parents=True, exist_ok=True)
    return root


def _approved_proposal(**kwargs) -> HealingProposal:
    defaults = {
        "healing_id": "heal-overlay-1",
        "flow_id": "BF-PRODUCT-003",
        "test_id": "TC-BF-PRODUCT-003-P01",
        "step_id": "",
        "locator_label": "search button",
        "old_locator": "page.getByTestId('search-button')",
        "new_locator": "page.getByRole('button', { name: 'Search Products' })",
        "fallbacks": ['button[aria-label="Search"]'],
        "confidence": 0.95,
        "status": "APPROVED",
    }
    defaults.update(kwargs)
    return HealingProposal(**defaults)


def _write_store(automation_dir: Path, entries: list[dict]) -> None:
    store = finalize_store({"schema": OVERLAY_SCHEMA, "entries": entries})
    path = automation_dir / "healing" / "approved" / "locator-overlays.json"
    path.write_text(json.dumps(store, indent=2), encoding="utf-8")


def _resolve_node(
    automation_dir: Path,
    *,
    label: str = "search button",
    flow_id: str = "BF-PRODUCT-003",
    test_id: str = "TC-BF-PRODUCT-003-P01",
    enabled: str = "true",
) -> dict:
    script = automation_dir / "scripts" / "resolve-healing-chain.mjs"
    real_script = Path("apps/automation/scripts/resolve-healing-chain.mjs")
    if not script.exists() and real_script.exists():
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(real_script.read_text(encoding="utf-8"), encoding="utf-8")
    base_chain = json.dumps(["#btn_search", 'button[title="Search"]'])
    proc = subprocess.run(
        [
            "node",
            str(script),
            "--overlay",
            str(automation_dir / "healing" / "approved" / "locator-overlays.json"),
            "--label",
            label,
            "--flow",
            flow_id,
            "--test",
            test_id,
            "--chain",
            base_chain,
            "--enabled",
            enabled,
        ],
        cwd=str(automation_dir),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout.strip())


def test_approved_overlay_is_loaded(automation_dir: Path):
    apply_approved_proposal(automation_dir, _approved_proposal())
    store = load_overlay_store(automation_dir)
    assert store["entries"]
    ok, _ = validate_entry(store["entries"][0])
    assert ok is True


def test_pending_overlay_ignored(automation_dir: Path):
    _write_store(
        automation_dir,
        [
            {
                "healing_id": "heal-pending",
                "flow_id": "BF-PRODUCT-003",
                "locator_label": "search button",
                "status": "PENDING_SME_APPROVAL",
                "selectors": ['button[aria-label="Search Products"]'],
            }
        ],
    )
    resolved = resolve_overlay_selectors(
        load_overlay_store(automation_dir),
        flow_id="BF-PRODUCT-003",
        locator_label="search button",
    )
    assert resolved is None


def test_rejected_overlay_ignored(automation_dir: Path):
    _write_store(
        automation_dir,
        [
            {
                "healing_id": "heal-reject",
                "flow_id": "BF-PRODUCT-003",
                "locator_label": "search button",
                "status": "REJECTED",
                "selectors": ['button[aria-label="Search Products"]'],
            }
        ],
    )
    assert (
        resolve_overlay_selectors(
            load_overlay_store(automation_dir),
            flow_id="BF-PRODUCT-003",
            locator_label="search button",
        )
        is None
    )


def test_invalid_overlay_ignored(automation_dir: Path):
    path = automation_dir / "healing" / "approved" / "locator-overlays.json"
    path.write_text("{not valid json", encoding="utf-8")
    store = load_overlay_store(automation_dir)
    assert store["entries"] == []


def test_matching_flow_step_uses_overlay(automation_dir: Path):
    apply_approved_proposal(automation_dir, _approved_proposal())
    result = _resolve_node(automation_dir)
    assert result["meta"]["locator_source"] == "HEALING_OVERLAY"
    assert result["chain"][0] == 'button[aria-label="Search Products"]'


def test_unrelated_flow_does_not_use_overlay(automation_dir: Path):
    apply_approved_proposal(automation_dir, _approved_proposal())
    result = _resolve_node(automation_dir, flow_id="BF-LOGIN-001")
    assert result["meta"]["locator_source"] == "KB_CHAIN"
    assert result["chain"][0] == "#btn_search"


def test_overlay_disabled_by_environment(automation_dir: Path):
    apply_approved_proposal(automation_dir, _approved_proposal())
    result = _resolve_node(automation_dir, enabled="false")
    assert result["meta"]["locator_source"] == "KB_CHAIN"
    assert "Search Products" not in json.dumps(result["chain"])


def test_overlay_usage_traceable_in_resolution_meta(automation_dir: Path):
    apply_approved_proposal(automation_dir, _approved_proposal(healing_id="heal-trace-99"))
    result = _resolve_node(automation_dir)
    assert result["meta"]["healing_id"] == "heal-trace-99"
    assert result["meta"]["overlay_version"]
    assert result["meta"]["overlay_hash"]


def test_original_locator_when_no_overlay(automation_dir: Path):
    result = _resolve_node(automation_dir)
    assert result["chain"] == ["#btn_search", 'button[title="Search"]']
    assert result["meta"]["locator_source"] == "KB_CHAIN"


def test_multiple_overlay_versions_deterministic(automation_dir: Path):
    _write_store(
        automation_dir,
        [
            {
                "healing_id": "heal-old",
                "flow_id": "BF-PRODUCT-003",
                "locator_label": "search button",
                "status": "APPROVED",
                "revoked": False,
                "selectors": ['button[aria-label="Old Search"]'],
                "approved_at": "2026-01-01T00:00:00Z",
            },
            {
                "healing_id": "heal-new",
                "flow_id": "BF-PRODUCT-003",
                "locator_label": "search button",
                "status": "APPROVED",
                "revoked": False,
                "selectors": ['button[aria-label="Search Products"]'],
                "approved_at": "2026-09-13T16:00:00Z",
            },
        ],
    )
    resolved = resolve_overlay_selectors(
        load_overlay_store(automation_dir),
        flow_id="BF-PRODUCT-003",
        locator_label="search button",
    )
    assert resolved["healing_id"] == "heal-new"


def test_corrupted_overlay_does_not_break_execution(automation_dir: Path):
    path = automation_dir / "healing" / "approved" / "locator-overlays.json"
    path.write_text('{"schema":"healing_locator_overlay_v1","entries":[{"bad":true}]}', encoding="utf-8")
    result = _resolve_node(automation_dir)
    assert result["meta"]["locator_source"] == "KB_CHAIN"


def test_approved_overlay_survives_new_process(automation_dir: Path):
    apply_approved_proposal(automation_dir, _approved_proposal(healing_id="heal-survive"))
    first = _resolve_node(automation_dir)
    second = _resolve_node(automation_dir)
    assert first["meta"]["healing_id"] == second["meta"]["healing_id"] == "heal-survive"
