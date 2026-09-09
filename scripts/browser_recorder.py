#!/usr/bin/env python3
"""ScoutAI Browser Recorder — capture interactions, DOM, console, network for KB discovery."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _session_dir(session_id: str) -> Path:
    d = ROOT / "discovery" / "uat_ea" / "recordings" / "sessions" / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_config(session_id: str) -> dict[str, Any]:
    cfg_path = _session_dir(session_id) / "config.json"
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    return {
        "console": True,
        "network": True,
        "interactions": True,
        "dom_snapshots": True,
        "video": False,
        "session_replay": False,
    }


def _save_config(session_id: str, cfg: dict[str, Any]) -> None:
    (_session_dir(session_id) / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def cmd_status(session_id: str) -> dict[str, Any]:
    sdir = _session_dir(session_id)
    status_path = sdir / "status.json"
    if status_path.exists():
        return json.loads(status_path.read_text(encoding="utf-8"))
    return {"session_id": session_id, "status": "idle", "events": 0}


def cmd_configure(session_id: str, cfg: dict[str, Any]) -> dict[str, Any]:
    merged = {**_load_config(session_id), **cfg}
    _save_config(session_id, merged)
    return merged


def cmd_record(session_id: str, *, url: str | None = None, max_seconds: int = 120) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return {"ok": False, "error": f"playwright not installed: {exc}"}

    cfg = _load_config(session_id)
    sdir = _session_dir(session_id)
    target = url or os.environ.get("EA_BASE_URL", "https://dev-ea.titanrts.com/ords/r/tjdcom/ea/login")
    if not target.endswith("login") and "/ea" in target:
        target = f"{target.rstrip('/')}/login"

    events: list[dict[str, Any]] = []
    dom_index = 0

    def log_event(kind: str, payload: dict[str, Any]) -> None:
        events.append({"at": datetime.now(timezone.utc).isoformat(), "kind": kind, **payload})

    status = {
        "session_id": session_id,
        "status": "recording",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "target_url": target,
        "config": cfg,
        "events": 0,
    }
    (sdir / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")

    with sync_playwright() as pw:
        channel = "chrome" if os.environ.get("EA_USE_SYSTEM_CHROME", "true").lower() != "false" else None
        headless = os.environ.get("EA_HEADLESS", "false").lower() == "true"
        browser = pw.chromium.launch(headless=headless, channel=channel)
        context = browser.new_context(
            record_video_dir=str(sdir / "video") if cfg.get("video") else None,
        )
        page = context.new_page()

        if cfg.get("console"):
            page.on("console", lambda msg: log_event("console", {"level": msg.type, "text": msg.text}))

        if cfg.get("network"):
            page.on("request", lambda req: log_event("network", {"phase": "request", "url": req.url, "method": req.method}))
            page.on("response", lambda res: log_event("network", {"phase": "response", "url": res.url, "status": res.status}))

        if cfg.get("interactions"):
            page.expose_binding("_scoutRecordClick", lambda _src, selector: log_event("interaction", {"action": "click", "selector": selector}))

        page.goto(target, wait_until="domcontentloaded", timeout=60_000)
        log_event("navigation", {"url": page.url(), "title": page.title()})

        if cfg.get("dom_snapshots"):
            dom_index += 1
            dom_path = sdir / f"dom_{dom_index:03d}_initial.html"
            dom_path.write_text(page.content(), encoding="utf-8")
            shot_path = sdir / f"shot_{dom_index:03d}_initial.png"
            page.screenshot(path=str(shot_path), fullPage=True)
            log_event("dom_snapshot", {"index": dom_index, "dom": dom_path.name, "screenshot": shot_path.name})

        deadline = time.time() + max_seconds
        while time.time() < deadline:
            time.sleep(1)
            if cfg.get("dom_snapshots") and len(events) % 5 == 0:
                dom_index += 1
                dom_path = sdir / f"dom_{dom_index:03d}_auto.html"
                dom_path.write_text(page.content(), encoding="utf-8")
                shot_path = sdir / f"shot_{dom_index:03d}_auto.png"
                page.screenshot(path=str(shot_path), fullPage=True)
                log_event("dom_snapshot", {"index": dom_index, "dom": dom_path.name, "screenshot": shot_path.name})

        if cfg.get("session_replay"):
            trace_path = sdir / "trace.zip"
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            context.tracing.stop(path=str(trace_path))
            log_event("trace", {"path": trace_path.name})

        context.close()
        browser.close()

    out = sdir / "events.json"
    out.write_text(json.dumps(events, indent=2), encoding="utf-8")
    status.update(
        {
            "status": "completed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "events": len(events),
            "events_file": str(out.relative_to(ROOT)),
        }
    )
    (sdir / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return {"ok": True, "session_id": session_id, "events": len(events), "dir": str(sdir.relative_to(ROOT))}


def main() -> None:
    parser = argparse.ArgumentParser(description="ScoutAI Browser Recorder")
    parser.add_argument("command", choices=["status", "configure", "record"])
    parser.add_argument("--session-id", default="scout-default")
    parser.add_argument("--url", default=None)
    parser.add_argument("--max-seconds", type=int, default=30)
    parser.add_argument("--config-json", default="{}")
    args = parser.parse_args()

    if args.command == "status":
        result = cmd_status(args.session_id)
    elif args.command == "configure":
        cfg = json.loads(args.config_json or "{}")
        result = cmd_configure(args.session_id, cfg)
    else:
        result = cmd_record(args.session_id, url=args.url, max_seconds=args.max_seconds)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
