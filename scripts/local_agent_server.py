#!/usr/bin/env python3
"""Local warm QA Orchestrator HTTP server — LLM planner + OpenClaw execution.

  PYTHONPATH=src:. python3 scripts/local_agent_server.py --port 43124

POST /run  {"goal":"sanity check endless aisle","run_type":"sanity","model":"groq/llama-3.1-8b-instant"}
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

from qa_orchestrator.orchestrator import QaOrchestrator, RunRequest  # noqa: E402


class LocalOrchestratorService:
    def __init__(self, kb_dir: str, *, default_model: str | None = None) -> None:
        self.kb_dir = kb_dir
        self.default_model = default_model
        t0 = time.perf_counter()
        self.orchestrator = QaOrchestrator(kb_dir=kb_dir, model=default_model)
        self.boot_ms = int((time.perf_counter() - t0) * 1000)
        self.runs = 0

    def run(
        self,
        goal: str,
        *,
        run_type: str = "adhoc",
        model: str | None = None,
        context_packets: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        result = self.orchestrator.run(
            RunRequest(
                goal=goal,
                run_type=run_type,
                model=model or self.default_model,
                context_packets=context_packets or [],
            )
        )
        self.runs += 1
        payload = self.orchestrator.to_agent_payload(result)
        payload["local"]["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        payload["local"]["boot_ms"] = self.boot_ms
        payload["local"]["runs_served"] = self.runs
        payload["local"]["llm_enabled"] = result.metadata.get("llm_enabled", False)
        payload["local"]["model_mode"] = "groq" if result.metadata.get("llm_enabled") else "deterministic_fallback"
        return payload


SERVICE: LocalOrchestratorService | None = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[qa-orchestrator] " + (fmt % args) + "\n")

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
                    "service": "qa-orchestrator",
                    "boot_ms": SERVICE.boot_ms,
                    "runs_served": SERVICE.runs,
                    "llm_enabled": SERVICE.orchestrator.llm.enabled,
                    "kb_dir": SERVICE.kb_dir,
                    "openclaw_mode": SERVICE.orchestrator.executor.mode,
                    "note": "LLM planner ON when GROQ_API_KEY set; OpenClaw mock until OPENCLAW_MODE=http",
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
        run_type = str(body.get("run_type") or body.get("type") or "adhoc")
        model = body.get("model")
        context_packets = body.get("context_packets") if isinstance(body.get("context_packets"), list) else []
        try:
            result = SERVICE.run(goal, run_type=run_type, model=model, context_packets=context_packets)
            self._json(200, {"ok": True, "result": result})
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"ok": False, "error": f"{type(exc).__name__}:{exc}"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=43124)
    parser.add_argument("--kb-dir", default=str(ROOT / "discovery/uat_ea/kb"))
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL_REASONING"))
    args = parser.parse_args()
    os.environ.setdefault("LLM_ENABLED", "true")
    global SERVICE
    SERVICE = LocalOrchestratorService(args.kb_dir, default_model=args.model)
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        json.dumps(
            {
                "listening": f"http://{args.host}:{args.port}",
                "boot_ms": SERVICE.boot_ms,
                "llm_enabled": SERVICE.orchestrator.llm.enabled,
                "openclaw_mode": SERVICE.orchestrator.executor.mode,
                "kb_dir": args.kb_dir,
            }
        ),
        flush=True,
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
