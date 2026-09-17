"""P10.3 — warm server HTTP auth against real local_agent_server subprocess."""

from __future__ import annotations

import json
import socket
import subprocess
import time
import urllib.error
import urllib.request

import pytest

from tests.canonical_subprocess_env import REPO_ROOT, canonical_subprocess_env


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _http(method: str, url: str, *, headers: dict[str, str] | None = None, body: bytes | None = None) -> tuple[int, str]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


@pytest.fixture
def warm_server_auth():
    port = _free_port()
    env = canonical_subprocess_env(
        SCOUT_ENV="development",
        SCOUT_INTERNAL_API_TOKEN="p10-test-internal",
        SCOUT_ALLOW_INSECURE_LOCAL="false",
        QA_AGENT_JOURNAL_DIR=str(REPO_ROOT / "reports" / "agent"),
    )
    proc = subprocess.Popen(
        ["python3", str(REPO_ROOT / "scripts" / "local_agent_server.py"), "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 45
    while time.time() < deadline:
        if proc.poll() is not None:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"warm server exited early: {stderr}")
        try:
            code, _ = _http("GET", f"{base}/health")
            if code == 200:
                break
        except urllib.error.URLError:
            pass
        time.sleep(0.25)
    else:
        proc.kill()
        raise TimeoutError("warm server /health never became ready")

    yield base, env
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_health_unauthenticated(warm_server_auth):
    base, _ = warm_server_auth
    code, body = _http("GET", f"{base}/health")
    assert code == 200
    assert "ok" in body.lower() or "health" in body.lower()


def test_run_rejects_missing_auth(warm_server_auth):
    base, _ = warm_server_auth
    payload = json.dumps({"goal": "Check login", "run_type": "adhoc"}).encode("utf-8")
    code, body = _http(
        "POST",
        f"{base}/run",
        headers={"Content-Type": "application/json"},
        body=payload,
    )
    assert code in (401, 403)
    assert "p10-test-internal" not in body
    assert "secret-token" not in body.lower()


def test_run_accepts_valid_internal_token(warm_server_auth):
    base, _ = warm_server_auth
    payload = json.dumps({"goal": "Check login", "run_type": "adhoc", "skip_execution": True}).encode("utf-8")
    code, body = _http(
        "POST",
        f"{base}/run",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer p10-test-internal",
        },
        body=payload,
    )
    assert code == 200, body[:500]
    data = json.loads(body)
    canonical = data["result"]["local"]["canonical"]
    assert canonical["legacy_runtime_canonical"] == "false"
    assert "ControlledAgentLoop" in canonical["orchestrator_path"]
    assert "p10-test-internal" not in body


def test_run_rejects_wrong_token(warm_server_auth):
    base, _ = warm_server_auth
    payload = json.dumps({"goal": "x"}).encode("utf-8")
    code, _ = _http(
        "POST",
        f"{base}/run",
        headers={"Content-Type": "application/json", "Authorization": "Bearer wrong-token"},
        body=payload,
    )
    assert code in (401, 403)
