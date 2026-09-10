"""Central path resolution for enterprise repo layout."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Enterprise layout (canonical)
APPS_CONSOLE = ROOT / "apps" / "console"
APPS_AUTOMATION = ROOT / "apps" / "automation"
SERVICES_AGENT = ROOT / "services" / "agent-runtime"
SERVICES_ORCHESTRATOR = ROOT / "services" / "qa-orchestrator"
DATA_DISCOVERY_KB = ROOT / "data" / "discovery-kb"
PLUGINS = ROOT / "plugins"
INFRA_DEPLOY = ROOT / "infra" / "deploy"
SCRIPTS = ROOT / "scripts"
DOCS = ROOT / "docs"
TESTS = ROOT / "tests"

# Legacy aliases (still resolve if old paths exist during migration)
LEGACY_DISCOVERY = ROOT / "discovery" / "uat_ea"
LEGACY_AUTOMATION = ROOT / "automation"
LEGACY_CONSOLE = ROOT / "qa-console"


def discovery_root() -> Path:
    env = os.environ.get("QA_DISCOVERY_ROOT")
    if env:
        return Path(env)
    if DATA_DISCOVERY_KB.exists():
        return DATA_DISCOVERY_KB
    return LEGACY_DISCOVERY


def automation_dir() -> Path:
    env = os.environ.get("QA_AUTOMATION_DIR")
    if env:
        return Path(env)
    if APPS_AUTOMATION.exists():
        return APPS_AUTOMATION
    return LEGACY_AUTOMATION


def python_path_entries() -> list[str]:
    entries = [
        str(SERVICES_AGENT),
        str(SERVICES_ORCHESTRATOR),
        str(ROOT),
    ]
    legacy_src = ROOT / "src"
    if legacy_src.exists():
        entries.insert(0, str(legacy_src))
    return entries


def python_path() -> str:
    return os.pathsep.join(python_path_entries())
