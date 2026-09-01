from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from qa_orchestrator.models import ExecutionPlan, ExecutionResult, PlanStep, StepObservation


class OpenClawAdapter:
    """Execute browser plans via OpenClaw (http/cli) or mock for local dev/tests."""

    def __init__(
        self,
        *,
        mode: str | None = None,
        base_url: str | None = None,
        evidence_dir: str | Path | None = None,
        timeout_s: float = 120.0,
    ) -> None:
        self.mode = (mode or os.environ.get("OPENCLAW_MODE", "mock")).lower()
        self.base_url = (base_url or os.environ.get("OPENCLAW_URL", "http://127.0.0.1:18789")).rstrip("/")
        self.cli = os.environ.get("OPENCLAW_CLI", "openclaw")
        self.evidence_dir = Path(evidence_dir or os.environ.get("QA_EVIDENCE_DIR", "artifacts/qa-evidence"))
        self.timeout_s = timeout_s

    def run_plan(self, plan: ExecutionPlan) -> ExecutionResult:
        t0 = time.perf_counter()
        if self.mode == "http":
            result = self._run_http(plan)
        elif self.mode == "cli":
            result = self._run_cli(plan)
        else:
            result = self._run_mock(plan)
        result.elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return result

    def _run_http(self, plan: ExecutionPlan) -> ExecutionResult:
        payload = {
            "goal": plan.goal,
            "summary": plan.summary,
            "steps": [s.model_dump() for s in plan.steps],
        }
        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                res = client.post(f"{self.base_url}/execute", json=payload)
                res.raise_for_status()
                data = res.json()
            observations = [_obs_from_dict(i, o) for i, o in enumerate(data.get("observations", []))]
            return ExecutionResult(
                ok=bool(data.get("ok", True)),
                mode="http",
                observations=observations,
                error=data.get("error"),
            )
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(ok=False, mode="http", error=f"openclaw.http:{type(exc).__name__}:{exc}")

    def _run_cli(self, plan: ExecutionPlan) -> ExecutionResult:
        import subprocess

        payload = json.dumps({"goal": plan.goal, "steps": [s.model_dump() for s in plan.steps]})
        try:
            proc = subprocess.run(
                [self.cli, "execute", "--json", payload],
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
            if proc.returncode != 0:
                return ExecutionResult(
                    ok=False,
                    mode="cli",
                    error=proc.stderr.strip() or f"openclaw.cli exit {proc.returncode}",
                )
            data = json.loads(proc.stdout)
            observations = [_obs_from_dict(i, o) for i, o in enumerate(data.get("observations", []))]
            return ExecutionResult(ok=bool(data.get("ok", True)), mode="cli", observations=observations)
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(ok=False, mode="cli", error=f"openclaw.cli:{type(exc).__name__}:{exc}")

    def _run_mock(self, plan: ExecutionPlan) -> ExecutionResult:
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        observations: list[StepObservation] = []
        has_creds = bool(os.environ.get("APEX_USERNAME") and os.environ.get("APEX_PASSWORD"))
        for i, step in enumerate(plan.steps):
            shot = self.evidence_dir / f"mock_{int(time.time())}_{i}_{step.action}.png"
            shot.write_bytes(b"")
            ok = True
            message = f"Mock executed {step.action}"
            if step.action in {"type"} and "${APEX_" in step.value and not has_creds:
                ok = True
                message = "Mock credential step (set APEX_USERNAME/APEX_PASSWORD for live OpenClaw runs)"
            observations.append(
                StepObservation(
                    step_index=i,
                    action=step.action,
                    ok=ok,
                    message=message,
                    screenshot_path=str(shot),
                    url=step.target if step.action == "navigate" else None,
                    meta={"mock": True, "note": step.note},
                )
            )
        all_ok = all(o.ok for o in observations)
        return ExecutionResult(ok=all_ok, mode="mock", observations=observations)


def _obs_from_dict(index: int, raw: Any) -> StepObservation:
    if not isinstance(raw, dict):
        return StepObservation(step_index=index, action="custom", ok=False, message=str(raw))
    return StepObservation(
        step_index=int(raw.get("step_index", index)),
        action=str(raw.get("action", "custom")),
        ok=bool(raw.get("ok", False)),
        message=str(raw.get("message", "")),
        screenshot_path=raw.get("screenshot_path"),
        url=raw.get("url"),
        meta=dict(raw.get("meta") or {}),
    )
