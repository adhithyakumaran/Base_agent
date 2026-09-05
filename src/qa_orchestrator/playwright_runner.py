"""Execute approved Playwright suites from the orchestrator."""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qa_orchestrator.models import (
    ExecutionPlan,
    ExecutionResult,
    StepObservation,
    SuiteSelectionPlan,
)


@dataclass
class PlaywrightRunnerConfig:
    automation_dir: Path = field(default_factory=lambda: Path("automation"))
    suite: str = "sanity"
    flow_id: str | None = None
    timeout_s: float = 3600.0
    dry_run: bool = False


class PlaywrightRunner:
    """Deterministic suite runner — no LLM at execution time."""

    def __init__(self, config: PlaywrightRunnerConfig | None = None) -> None:
        env_dry = os.environ.get("QA_RUNNER", "playwright").lower() in {"dry_run", "dry-run", "mock"}
        self.config = config or PlaywrightRunnerConfig(
            automation_dir=Path(os.environ.get("QA_AUTOMATION_DIR", "automation")),
            suite=os.environ.get("QA_SUITE", "sanity"),
            flow_id=os.environ.get("QA_FLOW_ID"),
            dry_run=env_dry,
        )

    @property
    def mode(self) -> str:
        return "playwright_dry_run" if self.config.dry_run else "playwright"

    def run_plan(self, plan: ExecutionPlan) -> ExecutionResult:
        return self.run_suite(suite=self._suite_from_plan(plan), flow_id=self._flow_from_plan(plan))

    def run_selection(self, selection: SuiteSelectionPlan) -> ExecutionResult:
        if self.config.dry_run:
            return self._dry_run(selection)
        t0 = time.perf_counter()
        observations: list[StepObservation] = []
        overall_ok = True
        error_parts: list[str] = []

        for i, cmd in enumerate(selection.commands or ["npm run test:sanity"]):
            obs = self._run_command(cmd, step_index=i, params=selection.params)
            observations.append(obs)
            if not obs.ok:
                overall_ok = False
                error_parts.append(obs.message or f"command failed: {cmd}")

        result = ExecutionResult(
            ok=overall_ok,
            mode=self.mode,
            observations=observations,
            error="; ".join(error_parts) if error_parts else None,
            elapsed_ms=int((time.perf_counter() - t0) * 1000),
        )
        return result

    def run_suite(self, *, suite: str | None = None, flow_id: str | None = None) -> ExecutionResult:
        suite = suite or self.config.suite
        flow_id = flow_id or self.config.flow_id
        if flow_id:
            cmd = f"npm run test:flow -- @{flow_id}"
        elif suite == "sanity":
            cmd = "npm run test:sanity"
        elif suite == "regression":
            cmd = "npm run test:regression"
        else:
            cmd = f"npm run test:flow -- @{suite}"
        selection = SuiteSelectionPlan(commands=[cmd], flow_ids=[flow_id] if flow_id else [], suite_ids=[suite])
        return self.run_selection(selection)

    def _run_command(self, cmd: str, *, step_index: int, params: dict[str, Any]) -> StepObservation:
        cwd = self.config.automation_dir.resolve()
        if not cwd.exists():
            return StepObservation(
                step_index=step_index,
                action="playwright_suite",
                ok=False,
                message=f"missing automation dir: {cwd}",
            )

        env = os.environ.copy()
        for key, value in (params or {}).items():
            env[f"QA_PARAM_{str(key).upper()}"] = str(value)

        parts = cmd.split()
        try:
            proc = subprocess.run(
                parts,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=self.config.timeout_s,
                check=False,
                env=env,
            )
            ok = proc.returncode == 0
            meta: dict[str, Any] = {
                "command": cmd,
                "stdout_tail": proc.stdout[-8000:],
                "stderr_tail": proc.stderr[-4000:],
                "params": params,
            }
            report_path = cwd / "reports" / "results.json"
            if report_path.exists():
                try:
                    data = json.loads(report_path.read_text(encoding="utf-8"))
                    meta["playwright_report"] = {
                        "stats": data.get("stats"),
                        "suites": len(data.get("suites", [])),
                    }
                except json.JSONDecodeError:
                    pass
            return StepObservation(
                step_index=step_index,
                action="playwright_suite",
                ok=ok,
                message=cmd if ok else (proc.stderr.strip() or f"exit {proc.returncode}"),
                meta=meta,
            )
        except subprocess.TimeoutExpired:
            return StepObservation(
                step_index=step_index,
                action="playwright_suite",
                ok=False,
                message="playwright.timeout",
            )
        except Exception as exc:  # noqa: BLE001
            return StepObservation(
                step_index=step_index,
                action="playwright_suite",
                ok=False,
                message=f"playwright:{type(exc).__name__}:{exc}",
            )

    def _dry_run(self, selection: SuiteSelectionPlan) -> ExecutionResult:
        observations = [
            StepObservation(
                step_index=i,
                action="playwright_suite_dry_run",
                ok=True,
                message=cmd,
                meta={"dry_run": True, "flow_ids": selection.flow_ids, "params": selection.params},
            )
            for i, cmd in enumerate(selection.commands or ["npm run test:sanity"])
        ]
        return ExecutionResult(ok=True, mode=self.mode, observations=observations)

    def _suite_from_plan(self, plan: ExecutionPlan) -> str:
        rt = (plan.run_type or "").lower()
        if "sanity" in rt or "morning" in plan.goal.lower():
            return "sanity"
        if "regression" in rt:
            return "regression"
        return self.config.suite

    def _flow_from_plan(self, plan: ExecutionPlan) -> str | None:
        for ref in plan.kb_refs or []:
            if ref.startswith("BF-"):
                return ref
        return self.config.flow_id
