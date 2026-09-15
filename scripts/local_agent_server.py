#!/usr/bin/env python3
"""Local warm QA Orchestrator HTTP server — intent classify + Playwright execution.

  PYTHONPATH=services/agent-runtime:services/qa-orchestrator:. python3 scripts/local_agent_server.py --port 43124

POST /run   {"goal":"morning sanity check","run_type":"sanity"}
POST /chat  same body — chat-friendly alias with structured enterprise output
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
for entry in (
    ROOT / "services" / "agent-runtime",
    ROOT / "services" / "qa-orchestrator",
    ROOT,
):
    entry_str = str(entry)
    if entry_str not in sys.path:
        sys.path.insert(0, entry_str)
legacy_src = ROOT / "src"
if legacy_src.is_dir() and str(legacy_src) not in sys.path:
    sys.path.insert(0, str(legacy_src))


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()

from qa_orchestrator.legacy_guard import assert_canonical_agent_path, canonical_path_metadata  # noqa: E402
from qa_orchestrator.orchestrator import QaOrchestrator, RunRequest  # noqa: E402
from qa_orchestrator.server_auth import (  # noqa: E402
    acquire_concurrency,
    allowed_origin,
    auth_configuration_error,
    bind_host_default,
    cors_headers,
    is_authenticated,
    log_auth_rejection,
    release_concurrency,
    security_log,
    validate_body_size,
)


class LocalOrchestratorService:
    def __init__(
        self,
        discovery_root: str,
        *,
        default_model: str | None = None,
    ) -> None:
        self.discovery_root = discovery_root
        self.default_model = default_model
        t0 = time.perf_counter()
        self.orchestrator = QaOrchestrator(discovery_root=discovery_root, model=default_model)
        self.boot_ms = int((time.perf_counter() - t0) * 1000)
        self.runs = 0

    def run(
        self,
        goal: str,
        *,
        run_type: str = "adhoc",
        model: str | None = None,
        run_id: str | None = None,
        context_packets: list[dict[str, Any]] | None = None,
        skip_discovery: bool = False,
        skip_execution: bool = False,
    ) -> dict[str, Any]:
        assert_canonical_agent_path("local_agent_server")
        t0 = time.perf_counter()
        result = self.orchestrator.run(
            RunRequest(
                goal=goal,
                run_type=run_type,
                model=model or self.default_model,
                run_id=run_id,
                context_packets=context_packets or [],
                skip_discovery=skip_discovery,
                skip_execution=skip_execution,
            )
        )
        self.runs += 1
        payload = self.orchestrator.to_agent_payload(result)
        payload["local"]["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        payload["local"]["boot_ms"] = self.boot_ms
        payload["local"]["runs_served"] = self.runs
        payload["local"]["llm_enabled"] = result.metadata.get("llm_enabled", False)
        payload["local"]["llm_provider"] = result.metadata.get("llm_provider", "groq")
        payload["local"]["primary_flows"] = len(self.orchestrator.graph.ready_flow_ids())
        payload["local"]["draft_flows"] = len(self.orchestrator.graph.draft_flow_ids())
        payload["local"]["canonical"] = canonical_path_metadata()
        return payload

    def get_agent(self, run_id: str) -> dict[str, Any]:
        snapshot = self.orchestrator.get_agent_state(run_id)
        return {
            "ok": True,
            "run_id": run_id,
            "status": snapshot.state.status,
            "final_result": snapshot.state.final_result,
            "checkpoint": snapshot.checkpoint,
            "approval_pause_kind": snapshot.approval_pause_kind,
            "journal_summary": [entry.model_dump() for entry in snapshot.state.decision_journal[-10:]],
            "state_path": str(
                __import__("qa_orchestrator.agent_state_store", fromlist=["state_path"]).state_path(
                    self.orchestrator.agent_loop.config.journal_dir,
                    run_id,
                )
            ),
        }

    def resume_agent(self, run_id: str, *, resume_token: str | None = None, reason: str = "approval granted") -> dict[str, Any]:
        result = self.orchestrator.resume_agent(run_id, resume_token=resume_token, resume_reason=reason)
        orch_result = self.orchestrator.agent_loop.to_orchestrator_result(result)
        orch_result.metadata.update(result.orchestrator_metadata)
        payload = self.orchestrator.to_agent_payload(orch_result)
        payload["agent"]["decision_journal"] = [entry.model_dump() for entry in result.state.decision_journal]
        return payload


SERVICE: LocalOrchestratorService | None = None


class Handler(BaseHTTPRequestHandler):
    server_version = "ScoutQAOrchestrator/2.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[qa-orchestrator] " + (fmt % args) + "\n")

    def _origin(self) -> str | None:
        return self.headers.get("Origin") or self.headers.get("origin")

    def _send_cors(self) -> None:
        for key, value in cors_headers(self._origin()).items():
            self.send_header(key, value)

    def _json(self, code: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self._send_cors()
        self.end_headers()
        self.wfile.write(raw)

    def _require_auth(self, path: str) -> bool:
        config_err = auth_configuration_error()
        if config_err:
            self._json(503, {"ok": False, "error": "misconfigured", "detail": config_err})
            return False
        if is_authenticated(self.headers):
            return True
        log_auth_rejection(path, "invalid_or_missing_internal_token")
        self._json(401, {"ok": False, "error": "unauthorized", "detail": "Valid internal service token required"})
        return False

    def do_OPTIONS(self) -> None:  # noqa: N802
        origin = self._origin()
        headers = cors_headers(origin)
        if not headers and origin and origin != allowed_origin():
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(204)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path.startswith("/agent/") and path.count("/") == 2:
            if not self._require_auth(path):
                return
            run_id = path.split("/")[-1]
            assert SERVICE is not None
            try:
                self._json(200, SERVICE.get_agent(run_id))
            except Exception as exc:  # noqa: BLE001
                self._json(404, {"ok": False, "error": f"{type(exc).__name__}:{exc}"})
            return
        if path in {"/health", "/"}:
            assert SERVICE is not None
            orch = SERVICE.orchestrator
            self._json(
                200,
                {
                    "ok": True,
                    "service": "qa-orchestrator",
                    "version": "2.0",
                    "architecture": "classify → plan → agent_loop → playwright → report",
                    "boot_ms": SERVICE.boot_ms,
                    "runs_served": SERVICE.runs,
                    "llm_enabled": orch.llm.enabled,
                    "llm_provider": orch.llm.provider,
                    "executor": getattr(orch.executor, "mode", "playwright"),
                    "discovery_root": SERVICE.discovery_root,
                    "primary_ready_flows": len(orch.graph.ready_flow_ids()),
                    "supporting_draft_flows": len(orch.graph.draft_flow_ids()),
                    "canonical_runtime": "qa_orchestrator.ControlledAgentLoop",
                },
            )
            return
        self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if not acquire_concurrency():
            self._json(429, {"ok": False, "error": "too_many_requests"})
            return
        try:
            self._handle_post(path)
        finally:
            release_concurrency()

    def _handle_post(self, path: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if not validate_body_size(length):
            self._json(413, {"ok": False, "error": "payload_too_large"})
            return
        if path.startswith("/agent/") and path.endswith("/resume"):
            if not self._require_auth(path):
                return
            run_id = path.split("/")[2]
            assert SERVICE is not None
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._json(400, {"ok": False, "error": "invalid_json"})
                return
            try:
                payload = SERVICE.resume_agent(
                    run_id,
                    resume_token=body.get("resume_token"),
                    reason=str(body.get("reason") or "approval granted"),
                )
                self._json(200, {"ok": True, "result": payload})
            except Exception as exc:  # noqa: BLE001
                self._json(400, {"ok": False, "error": f"{type(exc).__name__}:{exc}"})
            return
        if path not in {"/run", "/chat"}:
            self._json(404, {"ok": False, "error": "not_found"})
            return
        if not self._require_auth(path):
            return
        assert SERVICE is not None
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "error": "invalid_json"})
            return
        goal = str(body.get("goal") or body.get("message") or "").strip()
        if not goal:
            self._json(400, {"ok": False, "error": "goal_required"})
            return
        run_type = str(body.get("run_type") or body.get("type") or "adhoc")
        model = body.get("model")
        run_id = body.get("run_id")
        execution_mode = body.get("execution_mode") or body.get("executionMode")
        if run_id:
            security_log("run_accepted", run_id=str(run_id), path=path)
        if execution_mode:
            from qa_orchestrator.live_browser_config import apply_run_mode_to_environ

            apply_run_mode_to_environ(str(execution_mode))
        context_packets = body.get("context_packets") if isinstance(body.get("context_packets"), list) else []
        skip_discovery = bool(body.get("skip_discovery"))
        skip_execution = bool(body.get("skip_execution"))
        try:
            result = SERVICE.run(
                goal,
                run_type=run_type,
                model=model,
                run_id=str(run_id) if run_id else None,
                context_packets=context_packets,
                skip_discovery=skip_discovery,
                skip_execution=skip_execution,
            )
            chat_response = {
                "message": result.get("summary", ""),
                "conclusion": result.get("conclusion"),
                "execution_mode": result.get("local", {}).get("execution_mode"),
                "report_markdown": result.get("local", {}).get("report_markdown"),
                "suite_plan": result.get("local", {}).get("suite_plan"),
            }
            self._json(
                200,
                {
                    "ok": True,
                    "result": result,
                    "chat": chat_response if path == "/chat" else None,
                },
            )
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"ok": False, "error": f"{type(exc).__name__}:{exc}"})


def main() -> None:
    parser = argparse.ArgumentParser()
    default_host = bind_host_default()
    parser.add_argument("--host", default=default_host)
    parser.add_argument("--port", type=int, default=43124)
    parser.add_argument("--discovery-root", default=str(ROOT / "data" / "discovery-kb"))
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL_REASONING"))
    args = parser.parse_args()
    assert_bind = __import__("qa_orchestrator.server_auth", fromlist=["assert_bind_host"]).assert_bind_host
    assert_bind(args.host)
    config_err = auth_configuration_error()
    if config_err:
        print(json.dumps({"fatal": config_err}), file=sys.stderr)
        raise SystemExit(1)
    os.environ.setdefault("LLM_ENABLED", "true")
    os.environ.setdefault("QA_RUNNER", "playwright")
    os.environ.setdefault("QA_AUTOMATION_DIR", str(ROOT / "apps" / "automation"))
    global SERVICE
    SERVICE = LocalOrchestratorService(args.discovery_root, default_model=args.model)
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        json.dumps(
            {
                "listening": f"http://{args.host}:{args.port}",
                "boot_ms": SERVICE.boot_ms,
                "llm_enabled": SERVICE.orchestrator.llm.enabled,
                "executor": getattr(SERVICE.orchestrator.executor, "mode", "playwright"),
                "discovery_root": args.discovery_root,
                "ready_flows": len(SERVICE.orchestrator.graph.ready_flow_ids()),
                "canonical_runtime": "qa_orchestrator.ControlledAgentLoop",
                "bind_host": args.host,
                "cors_origin": allowed_origin(),
            }
        ),
        flush=True,
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
