"""Run-scoped exploration evidence — no global mtime scanning."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qa_orchestrator.models import ExplorationEvidenceItem


def sanitize_segment(value: str, *, max_len: int = 72) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_")[:max_len] or "step"


def evidence_dir(
    automation_dir: Path,
    *,
    exploration_id: str,
    page_id: str,
    action_id: str,
) -> Path:
    path = (
        automation_dir
        / "reports"
        / "evidence"
        / sanitize_segment(exploration_id, max_len=96)
        / sanitize_segment(page_id, max_len=72)
        / sanitize_segment(action_id, max_len=72)
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def capture_evidence(
    page: Any,
    *,
    automation_dir: Path,
    exploration_id: str,
    page_id: str,
    action_id: str,
    label: str,
    console_events: list[dict[str, Any]] | None = None,
    network_events: list[dict[str, Any]] | None = None,
) -> ExplorationEvidenceItem:
    directory = evidence_dir(
        automation_dir,
        exploration_id=exploration_id,
        page_id=page_id,
        action_id=action_id,
    )
    screenshot_path = directory / "capture.png"
    dom_path = directory / "capture.html"
    meta_path = directory / "capture.json"

    page.screenshot(path=str(screenshot_path), full_page=True)
    dom_path.write_text(page.content(), encoding="utf-8")
    url = page.url
    timestamp = datetime.now(timezone.utc).isoformat()
    meta = {
        "explorationId": exploration_id,
        "pageId": page_id,
        "actionId": action_id,
        "label": label,
        "url": url,
        "capturedAt": timestamp,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return ExplorationEvidenceItem(
        exploration_id=exploration_id,
        page_id=page_id,
        action_id=action_id,
        timestamp=timestamp,
        label=label,
        screenshot_path=str(screenshot_path),
        dom_path=str(dom_path),
        url=url,
        console_events=list(console_events or []),
        network_events=list(network_events or []),
        meta=meta,
    )


def list_exploration_evidence(automation_dir: Path, exploration_id: str) -> list[dict[str, Any]]:
    root = automation_dir / "reports" / "evidence" / sanitize_segment(exploration_id, max_len=96)
    if not root.exists():
        return []
    items: list[dict[str, Any]] = []
    for meta_path in sorted(root.glob("*/*/capture.json")):
        try:
            items.append(json.loads(meta_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return items
