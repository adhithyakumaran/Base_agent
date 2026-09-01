#!/usr/bin/env python3
"""Local warm Base Agent HTTP server — keeps runtime in memory for fast console calls.

  PYTHONPATH=src:. python3 scripts/local_agent_server.py --port 43124

POST /run  {"goal":"health check endless aisle","kb_dir":"discovery/uat_ea/kb"}
GET  /health
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from base_agent.api import build_default_runtime  # noqa: E402


class LocalAgentService:
    def __init__(self, kb_dir: str) -> None:
        self.kb_dir = kb_dir
        t0 = time.perf_counter()
        self.runtime = build_default_runtime(kb_dir=kb_dir)
        self.boot_ms = int((time.perf_counter() - t0) * 1000)
        self.runs = 0

    def run(self, goal: str) -> dict[str, Any]:
        t0 = time.perf_counter()
        result = self.runtime.run(goal)
        self.runs += 1
        payload = result.model_dump()
        payload["local"] = {
            "boot_ms": self.boot_ms,
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            "runs_served": self.runs,
            "llm_enabled": self.runtime.llm_enabled,
            "model_mode": "deterministic_off" if not self.runtime.llm_enabled else "gateway",
        }
        return payload


SERVICE: LocalAgentService | None = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:  # quieter local logs
        sys.stderr.write("[local-agent] " + (fmt % args) + "\n")

    def _json(self, code: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/health", "/"}:
            assert SERVICE is not None
            self._json(
                200,
                {
                    "ok": True,
                    "service": "base-agent-local",
                    "boot_ms": SERVICE.boot_ms,
                    "runs_served": SERVICE.runs,
                    "llm_enabled": SERVICE.runtime.llm_enabled,
                    "kb_dir": SERVICE.kb_dir,
                    "note": "LLM default OFF — deterministic QA skills only",
                },
            )
            return
        self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/run":
            self._json(404, {"ok": False, "error": "not_found"})
            return
        assert SERVICE is not None
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "error": "invalid_json"})
            return
        goal = str(body.get("goal") or "").strip()
        if not goal:
            self._json(400, {"ok": False, "error": "goal_required"})
            return
        try:
            result = SERVICE.run(goal)
            self._json(200, {"ok": True, "result": result})
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"ok": False, "error": f"{type(exc).__name__}:{exc}"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=43124)
    parser.add_argument("--kb-dir", default=str(ROOT / "discovery/uat_ea/kb"))
    args = parser.parse_args()
    os.environ.setdefault("LLM_ENABLED", "false")
    global SERVICE
    SERVICE = LocalAgentService(args.kb_dir)
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        json.dumps(
            {
                "listening": f"http://{args.host}:{args.port}",
                "boot_ms": SERVICE.boot_ms,
                "llm_enabled": False,
                "kb_dir": args.kb_dir,
            }
        ),
        flush=True,
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
