"""Helpers for unit tests that need a specific flow approval state in repo automation artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_AUTOMATION = Path("apps/automation")
CANONICAL_ARTIFACT = "test-cases.yaml"


def set_flow_test_case_status(flow_id: str, status: str, *, automation_dir: Path = REPO_AUTOMATION) -> None:
    artifact = automation_dir / "test-design" / "flows" / flow_id / CANONICAL_ARTIFACT
    raw = artifact.read_text(encoding="utf-8")
    updated = re.sub(
        r"^status:\s*(PENDING_SME_APPROVAL|APPROVED|REJECTED)\s*$",
        f"status: {status}",
        raw,
        count=1,
        flags=re.MULTILINE,
    )
    artifact.write_text(updated, encoding="utf-8")


def remove_flow_approval_records(flow_id: str, *, automation_dir: Path = REPO_AUTOMATION) -> None:
    log_path = automation_dir / "approval" / "approval-log.json"
    if not log_path.exists():
        return
    try:
        data = json.loads(log_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log_path.unlink(missing_ok=True)
        return
    records = [
        r
        for r in (data.get("records") or [])
        if not (r.get("flowId") == flow_id and r.get("artifact") == CANONICAL_ARTIFACT)
    ]
    if records:
        log_path.write_text(json.dumps({"records": records}, indent=2) + "\n", encoding="utf-8")
    else:
        log_path.unlink(missing_ok=True)


def patch_suite_selector_no_commands(monkeypatch, orchestrator) -> None:
    """Prevent suite commands from bypassing run-level approval pause in unit tests."""

    original = orchestrator.selector.select

    def _select(intent):
        plan = original(intent)
        return plan.model_copy(update={"commands": [], "flow_ids": []})

    monkeypatch.setattr(orchestrator.selector, "select", _select)
