"""Execute approved Playwright suites from the orchestrator."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qa_orchestrator.models import ExecutionPlan, ExecutionResult, StepObservation


@dataclass
class PlaywrightRunnerConfig:
    automation_dir: Path = field(default_factory=lambda: Path("automation"))
    suite: str = "sanity"  # sanity | regression | flow tag
    flow_id: str | None = None
    timeout_s: float = 3600.0


class PlaywrightRunner:
    """Deterministic suite runner — no LLM at execution time."""

    def __init__(self, config: PlaywrightRunnerConfig | None = None) -> None:
        self.config = config or PlaywrightRunnerConfig(
            automation_dir=Path(os.environ.get("QA_AUTOMATION_DIR", "automation")),
            suite=os.environ.get("QA_SUITE", "sanity"),
            flow_id=os.environ.get("QA_FLOW_ID"),
        )

    def run_plan(self, plan: ExecutionPlan) -> ExecutionResult:
        return self.run_suite(suite=self._suite_from_plan(plan), flow_id=self._flow_from_plan(plan))

    def run_suite(self, *, suite: str | None = None, flow_id: str | None = None) -> ExecutionResult:
        suite = suite or self.config.suite
        flow_id = flow_id or self.config.flow_id
        cwd = self.config.automation_dir.resolve()
        if not cwd.exists():
            return ExecutionResult(ok=False, mode="playwright", error=f"missing automation dir: {cwd}")

        if flow_id:
            cmd = ["npm", "run", "test:flow", "--", f"@{flow_id}"]
        elif suite == "sanity":
            cmd = ["npm", "run", "test:sanity"]
        elif suite == "regression":
            cmd = ["npm", "run", "test:regression"]
        else:
            cmd = ["npm", "run", "test:flow", "--", f"@{suite}"]

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=self.config.timeout_s,
                check=False,
            )
            ok = proc.returncode == 0
            obs = [
                StepObservation(
                    step_index=0,
                    action="playwright_suite",
                    ok=ok,
                    detail=cmd,
                    evidence={"stdout": proc.stdout[-8000:], "stderr": proc.stderr[-4000:]},
                )
            ]
            report_path = cwd / "reports" / "results.json"
            if report_path.exists():
                try:
                    data = json.loads(report_path.read_text(encoding="utf-8"))
                    obs[0].evidence["playwright_report"] = {
                        "stats": data.get("stats"),
                        "suites": len(data.get("suites", [])),
                    }
                except json.JSONDecodeError:
                    pass
            return ExecutionResult(
                ok=ok,
                mode="playwright",
                observations=obs,
                error=None if ok else proc.stderr.strip() or f"exit {proc.returncode}",
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(ok=False, mode="playwright", error="playwright.timeout")
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(ok=False, mode="playwright", error=f"playwright:{type(exc).__name__}:{exc}")

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
