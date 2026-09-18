from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session", autouse=True)
def restore_controlled_dev_approval_baseline_after_tests() -> None:
    """Re-sync approval-log.json after unit tests that mutate repo automation artifacts."""
    automation = ROOT / "apps" / "automation"
    if automation.is_dir():
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            [
                str(ROOT / "services" / "qa-orchestrator"),
                str(ROOT / "services" / "agent-runtime"),
                str(ROOT),
            ]
        )
        env["QA_BOOTSTRAP_APPROVALS"] = "true"

        def _sync_baseline() -> None:
            login_artifact = (
                ROOT / "apps" / "automation" / "test-design" / "flows" / "BF-LOGIN-001" / "test-cases.yaml"
            )
            subprocess.run(
                ["git", "checkout", "--", str(login_artifact.relative_to(ROOT))],
                cwd=str(ROOT),
                check=False,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "approve-sme-ready-flows.py"),
                    "--enable",
                    "--automation-dir",
                    "apps/automation",
                ],
                cwd=str(ROOT),
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

        _sync_baseline()
    yield
    if automation.is_dir():
        _sync_baseline()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Run controlled-dev approval inventory guard last (other tests mutate repo artifacts)."""
    guard: list[pytest.Item] = []
    rest: list[pytest.Item] = []
    for item in items:
        if item.name == "test_controlled_dev_approved_sme_ready_catalog_flows_executable":
            guard.append(item)
        else:
            rest.append(item)
    items[:] = rest + guard


@pytest.fixture
def runtime():
    from base_agent.api import build_default_runtime

    return build_default_runtime(kb_dir=str(ROOT / "data" / "discovery-kb" / "kb"))