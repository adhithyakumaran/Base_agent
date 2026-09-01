from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


@pytest.fixture
def runtime():
    from base_agent.api import build_default_runtime

    return build_default_runtime(kb_dir=str(ROOT / "discovery/uat_ea/kb"))