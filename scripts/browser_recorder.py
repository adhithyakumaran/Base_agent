#!/usr/bin/env python3
"""ScoutAI Browser Recorder — real interaction capture + live event stream."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from repo_paths import discovery_root
except ImportError:
    discovery_root = lambda: ROOT / "data" / "discovery-kb"  # type: ignore[misc,assignment]


INTERACTION_INIT_SCRIPT = """
(() => {
  if (window.__scoutRecorderInstalled) return;
  window.__scoutRecorderInstalled = true;
  const describe = (el) => {
    if (!el) return 'unknown';
    const tag = el.tagName ? el.tagName.toLowerCase() : 'node';
    const id = el.id ? '#' + el.id : '';
    const name = el.getAttribute && el.getAttribute('name') ? '[name=' + el.getAttribute('name') + ']' : '';
    const role = el.getAttribute && el.getAttribute('role') ? '[role=' + el.getAttribute('role') + ']' : '';
    const testId = el.getAttribute && el.getAttribute('data-testid') ? '[data-testid=' + el.getAttribute('data-testid') + ']' : '';
    const text = (el.innerText || el.textContent || '').trim().slice(0, 40);
    return `${tag}${id}${name}${role}${testId}${text ? ':' + text : ''}`;
  };
  document.addEventListener('click', (e) => {
    const sel = describe(e.target);
    const fallbacks = [sel];
    if (e.target && e.target.id) fallbacks.push('#' + e.target.id);
    if (window._scoutRecordClick) window._scoutRecordClick({ action: 'click', selector: sel, fallbacks });
  }, true);
  document.addEventListener('input', (e) => {
    const sel = describe(e.target);
    if (window._scoutRecordInput) window._scoutRecordInput({ action: 'input', selector: sel, valueLength: (e.target.value || '').length });
  }, true);
  document.addEventListener('change', (e) => {
    const sel = describe(e.target);
    if (window._scoutRecordInput) window._scoutRecordInput({ action: 'change', selector: sel });
  }, true);
})();
"""


def _session_dir(session_id: str) -> Path:
    base = discovery_root() / "recordings" / "sessions"
    d = base / session_id
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


def _append_event(session_id: str, event: dict[str, Any]) -> None:
    path = _session_dir(session_id) / "events.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


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


def cmd_events(session_id: str, *, offset: int = 0) -> dict[str, Any]:
    path = _session_dir(session_id) / "events.jsonl"
    if not path.exists():
        return {"events": [], "offset": offset, "total": 0}
    lines = path.read_text(encoding="utf-8").splitlines()
    slice_lines = lines[offset:]
    events = [json.loads(line) for line in slice_lines if line.strip()]
    return {"events": events, "offset": offset + len(events), "total": len(lines)}


def cmd_record(session_id: str, *, url: str | None = None, max_seconds: int = 120) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return {"ok": False, "error": f"playwright not installed: {exc}"}

    cfg = _load_config(session_id)
    sdir = _session_dir(session_id)
    base = os.environ.get("EA_BASE_URL", "https://dev-ea.titanrts.com/ords/r/tjdcom/ea")
    target = url or f"{base.rstrip('/')}/login"

    events: list[dict[str, Any]] = []
    dom_index = 0
    events_path = sdir / "events.jsonl"
    if events_path.exists():
        events_path.unlink()

    def log_event(kind: str, payload: dict[str, Any]) -> None:
        event = {"at": datetime.now(timezone.utc).isoformat(), "kind": kind, **payload}
        events.append(event)
        _append_event(session_id, event)

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
        context = browser.new_context(record_video_dir=str(sdir / "video") if cfg.get("video") else None)
        page = context.new_page()

        if cfg.get("interactions"):
            page.add_init_script(INTERACTION_INIT_SCRIPT)

            def on_click(_src, payload):
                log_event("interaction", payload if isinstance(payload, dict) else {"selector": str(payload)})

            def on_input(_src, payload):
                log_event("interaction", payload if isinstance(payload, dict) else {"selector": str(payload)})

            page.expose_binding("_scoutRecordClick", on_click)
            page.expose_binding("_scoutRecordInput", on_input)

        if cfg.get("console"):
            page.on("console", lambda msg: log_event("console", {"level": msg.type, "text": msg.text[:500]}))

        if cfg.get("network"):
            page.on("request", lambda req: log_event("network", {"phase": "request", "url": req.url[:200], "method": req.method}))
            page.on("response", lambda res: log_event("network", {"phase": "response", "url": res.url[:200], "status": res.status}))

        if cfg.get("session_replay"):
            context.tracing.start(screenshots=True, snapshots=True, sources=True)

        page.goto(target, wait_until="domcontentloaded", timeout=60_000)
        log_event("navigation", {"url": page.url, "title": page.title()})

        if cfg.get("dom_snapshots"):
            dom_index += 1
            dom_path = sdir / f"dom_{dom_index:03d}_initial.html"
            dom_path.write_text(page.content(), encoding="utf-8")
            shot_path = sdir / f"shot_{dom_index:03d}_initial.png"
            page.screenshot(path=str(shot_path), fullPage=True)
            log_event("dom_snapshot", {"index": dom_index, "dom": dom_path.name, "screenshot": shot_path.name, "url": page.url})

        deadline = time.time() + max_seconds
        last_snap = time.time()
        while time.time() < deadline:
            time.sleep(0.5)
            status["events"] = len(events)
            (sdir / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
            if cfg.get("dom_snapshots") and time.time() - last_snap >= 8:
                dom_index += 1
                dom_path = sdir / f"dom_{dom_index:03d}_auto.html"
                dom_path.write_text(page.content(), encoding="utf-8")
                shot_path = sdir / f"shot_{dom_index:03d}_auto.png"
                page.screenshot(path=str(shot_path), fullPage=True)
                log_event("dom_snapshot", {"index": dom_index, "dom": dom_path.name, "screenshot": shot_path.name, "url": page.url})
                last_snap = time.time()

        if cfg.get("session_replay"):
            trace_path = sdir / "trace.zip"
            context.tracing.stop(path=str(trace_path))
            log_event("trace", {"path": trace_path.name})

        context.close()
        browser.close()

    status.update(
        {
            "status": "completed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "events": len(events),
            "events_file": str(events_path.relative_to(ROOT)),
        }
    )
    (sdir / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return {"ok": True, "session_id": session_id, "events": len(events), "dir": str(sdir.relative_to(ROOT))}


def main() -> None:
    parser = argparse.ArgumentParser(description="ScoutAI Browser Recorder")
    parser.add_argument("command", choices=["status", "configure", "record", "events"])
    parser.add_argument("--session-id", default="scout-default")
    parser.add_argument("--url", default=None)
    parser.add_argument("--max-seconds", type=int, default=30)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--config-json", default="{}")
    args = parser.parse_args()

    if args.command == "status":
        result = cmd_status(args.session_id)
    elif args.command == "configure":
        cfg = json.loads(args.config_json or "{}")
        result = cmd_configure(args.session_id, cfg)
    elif args.command == "events":
        result = cmd_events(args.session_id, offset=args.offset)
    else:
        result = cmd_record(args.session_id, url=args.url, max_seconds=args.max_seconds)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
