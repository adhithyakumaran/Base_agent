"""API-level ground truth approval audit expectations."""

from __future__ import annotations

import json
from pathlib import Path


def test_gt_audit_file_format_documented(tmp_path: Path) -> None:
    audit = tmp_path / "approval-audit.jsonl"
    entry = {
        "action": "ground_truth.approve",
        "gt_id": "gt-bf-product-003-positive",
        "run_id": "run_h20o9k6tvbao",
        "approver": "SME Reviewer",
        "approved_at": "2026-01-01T00:00:00+00:00",
    }
    audit.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    line = audit.read_text(encoding="utf-8").strip()
    parsed = json.loads(line)
    assert parsed["action"] == "ground_truth.approve"
    assert parsed["gt_id"].startswith("gt-")
