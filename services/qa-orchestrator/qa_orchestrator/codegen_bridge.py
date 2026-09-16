"""Probe and invoke the Node Playwright codegen bridge."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


GENERATOR_VERSION = "p2.1"


def probe_codegen_bridge(automation_dir: Path) -> dict[str, Any]:
    script = automation_dir / "scripts" / "probe-playwright-codegen.mjs"
    if not script.exists():
        return {
            "bridgeAvailable": False,
            "playwrightVersion": "unknown",
            "reason": "probe-playwright-codegen.mjs not found",
        }
    proc = subprocess.run(
        ["node", str(script)],
        cwd=str(automation_dir),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        return {
            "bridgeAvailable": False,
            "playwrightVersion": "unknown",
            "reason": (proc.stderr or proc.stdout or "probe failed")[:500],
        }
    try:
        return json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return {"bridgeAvailable": False, "reason": "invalid probe JSON"}


def invoke_codegen_bridge(automation_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    script = automation_dir / "scripts" / "generate-spec-bridge.mjs"
    if not script.exists():
        return {"ok": False, "bridgeAvailable": False, "bridgeReason": "generate-spec-bridge.mjs not found"}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        json.dump(payload, tmp)
        tmp_path = tmp.name
    try:
        proc = subprocess.run(
            ["node", str(script), tmp_path],
            cwd=str(automation_dir),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    if proc.returncode != 0:
        return {
            "ok": False,
            "bridgeAvailable": False,
            "bridgeReason": (proc.stderr or proc.stdout or "bridge failed")[:500],
        }
    try:
        return json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return {"ok": False, "bridgeAvailable": False, "bridgeReason": "invalid bridge JSON"}
