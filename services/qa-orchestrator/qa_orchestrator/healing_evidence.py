"""Capture structured healing evidence under run-scoped directories."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def healing_evidence_root(automation_dir: Path, run_id: str, test_id: str) -> Path:
    safe_test = test_id.replace("/", "_").replace(" ", "_")
    path = automation_dir / "reports" / "evidence" / run_id / safe_test / "healing"
    path.mkdir(parents=True, exist_ok=True)
    return path


def capture_stage(
    root: Path,
    stage: str,
    *,
    screenshot_src: str | None = None,
    dom_src: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, str]:
    stage_dir = root / stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    refs: dict[str, str] = {"stage": stage, "dir": str(stage_dir)}
    if screenshot_src:
        src = Path(screenshot_src)
        if src.exists():
            dest = stage_dir / "capture.png"
            shutil.copy2(src, dest)
            refs["screenshot"] = str(dest)
    if dom_src:
        src = Path(dom_src)
        if src.exists():
            dest = stage_dir / "capture.html"
            shutil.copy2(src, dest)
            refs["dom"] = str(dest)
    payload = {
        "stage": stage,
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        **(meta or {}),
    }
    (stage_dir / "meta.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    refs["meta"] = str(stage_dir / "meta.json")
    return refs
