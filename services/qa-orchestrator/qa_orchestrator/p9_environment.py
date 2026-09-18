"""P9 — environment preflight for live Oracle APEX validation."""

from __future__ import annotations

import os
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EnvironmentPreflight:
    status: str = "UNKNOWN"
    environment: str = "UAT"
    apex_reachable: bool = False
    apex_http_status: int | None = None
    credentials_configured: bool = False
    playwright_installed: bool = False
    node_modules_present: bool = False
    evidence_dir_writable: bool = False
    ground_truth_dir_exists: bool = False
    login_probe_ok: bool = False
    login_probe_error: str = ""
    blocked_reason: str = ""
    checks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "environment": self.environment,
            "apex_reachable": self.apex_reachable,
            "apex_http_status": self.apex_http_status,
            "credentials_configured": self.credentials_configured,
            "playwright_installed": self.playwright_installed,
            "node_modules_present": self.node_modules_present,
            "evidence_dir_writable": self.evidence_dir_writable,
            "ground_truth_dir_exists": self.ground_truth_dir_exists,
            "login_probe_ok": self.login_probe_ok,
            "login_probe_error": self.login_probe_error,
            "blocked_reason": self.blocked_reason,
            "checks": self.checks,
        }


def _load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def run_environment_preflight(
    *,
    automation_dir: str | Path = "apps/automation",
    discovery_root: str | Path = "data/discovery-kb",
) -> EnvironmentPreflight:
    pre = EnvironmentPreflight()
    automation = Path(automation_dir)
    env_file = automation / "config" / ".env"
    env_vars = _load_env_file(env_file)
    pre.environment = os.environ.get("QA_ENV") or "UAT"

    base_url = env_vars.get("EA_BASE_URL") or os.environ.get("EA_BASE_URL") or ""
    username = env_vars.get("EA_USER_USERNAME") or os.environ.get("EA_USER_USERNAME") or ""
    password = env_vars.get("EA_USER_PASSWORD") or os.environ.get("EA_USER_PASSWORD") or ""
    pre.credentials_configured = bool(base_url and username and password)

    if base_url:
        try:
            req = urllib.request.Request(base_url, method="GET")
            with urllib.request.urlopen(req, timeout=12) as resp:
                pre.apex_http_status = resp.status
                pre.apex_reachable = resp.status < 500
        except urllib.error.HTTPError as exc:
            pre.apex_http_status = exc.code
            pre.apex_reachable = exc.code < 500
        except Exception:
            pre.apex_reachable = False

    pre.checks.append(
        {
            "name": "apex_url",
            "ok": pre.apex_reachable,
            "detail": f"HTTP {pre.apex_http_status}" if pre.apex_http_status else "unreachable",
        }
    )

    pre.node_modules_present = (automation / "node_modules").exists()
    pre.checks.append({"name": "node_modules", "ok": pre.node_modules_present})

    try:
        proc = subprocess.run(
            ["npx", "playwright", "--version"],
            cwd=str(automation),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        pre.playwright_installed = proc.returncode == 0
    except Exception:
        pre.playwright_installed = False
    pre.checks.append({"name": "playwright_cli", "ok": pre.playwright_installed})

    evidence_root = automation / "reports" / "evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)
    probe = evidence_root / ".p9-write-probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        pre.evidence_dir_writable = True
    except OSError:
        pre.evidence_dir_writable = False
    pre.checks.append({"name": "evidence_writable", "ok": pre.evidence_dir_writable})

    gt_dir = Path(discovery_root) / "gt"
    pre.ground_truth_dir_exists = gt_dir.exists()
    pre.checks.append({"name": "ground_truth_dir", "ok": pre.ground_truth_dir_exists})

    pre.checks.append({"name": "credentials", "ok": pre.credentials_configured})

    skip_login_probe = os.environ.get("P9_SKIP_LOGIN_PROBE") == "1"
    if skip_login_probe:
        pre.checks.append({"name": "login_probe", "ok": False, "detail": "skipped"})
    elif pre.credentials_configured and pre.node_modules_present:
        login_url = base_url.rstrip("/")
        login_path = env_vars.get("EA_LOGIN_URL", "login")
        if not login_url.endswith(login_path):
            login_url = f"{login_url}/{login_path.lstrip('/')}"
        try:
            proc = subprocess.run(
                [
                    "npm",
                    "run",
                    "debug:login:headed",
                ],
                cwd=str(automation),
                env={
                    **os.environ,
                    "EA_HEADLESS": "true",
                    "EA_SKIP_GLOBAL_SETUP": "true",
                },
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            combined = (proc.stdout or "") + (proc.stderr or "")
            pre.login_probe_ok = proc.returncode == 0 and "502" not in combined and "Bad Gateway" not in combined
            if not pre.login_probe_ok:
                pre.login_probe_error = _sanitize(combined[-500:])
        except subprocess.TimeoutExpired:
            pre.login_probe_ok = False
            pre.login_probe_error = "login probe timed out"
        pre.checks.append({"name": "login_probe", "ok": pre.login_probe_ok})

    login_ok = pre.login_probe_ok
    live_ready = (
        pre.credentials_configured
        and pre.apex_reachable
        and pre.node_modules_present
        and pre.playwright_installed
        and pre.evidence_dir_writable
        and login_ok
    )
    if skip_login_probe:
        pre.status = "ENVIRONMENT_BLOCKED"
        pre.blocked_reason = "login_probe_skipped"
        return pre
    if live_ready:
        pre.status = "READY"
    elif not pre.credentials_configured:
        pre.status = "ENVIRONMENT_BLOCKED"
        pre.blocked_reason = "credentials_not_configured"
    elif not pre.apex_reachable or pre.apex_http_status and pre.apex_http_status >= 500:
        pre.status = "ENVIRONMENT_BLOCKED"
        pre.blocked_reason = "apex_unavailable"
    elif not pre.login_probe_ok:
        pre.status = "ENVIRONMENT_BLOCKED"
        pre.blocked_reason = pre.login_probe_error or "login_probe_failed"
    else:
        pre.status = "ENVIRONMENT_BLOCKED"
        pre.blocked_reason = "preflight_incomplete"

    return pre


def _sanitize(text: str) -> str:
    for token in ("password", "token", "cookie", "authorization", "EA_USER_PASSWORD"):
        text = text.replace(token, "[redacted]")
    return text.strip()


def restore_flow_approval(flow_id: str, *, automation_dir: str | Path = "apps/automation") -> None:
    import re

    artifact = Path(automation_dir) / "test-design" / "flows" / flow_id / "test-cases.yaml"
    if artifact.exists():
        text = artifact.read_text(encoding="utf-8")
        text = re.sub(r"^status:\s*APPROVED\s*$", "status: PENDING_SME_APPROVAL", text, flags=re.MULTILINE)
        artifact.write_text(text, encoding="utf-8")


def approve_flow_for_validation(flow_id: str, *, automation_dir: str | Path = "apps/automation") -> None:
    from qa_orchestrator.agent_eval import _approve_flow_for_eval
    from qa_orchestrator.orchestrator import QaOrchestrator

    orch = QaOrchestrator(discovery_root="data/discovery-kb")
    _approve_flow_for_eval(orch, flow_id)
