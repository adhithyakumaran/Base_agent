"""Load P12 canonical flow audit records for path/automation verification."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def audit_path(discovery_root: Path) -> Path:
    return discovery_root / "flows" / "p12-canonical-flow-audit.yaml"


@lru_cache(maxsize=4)
def load_flow_audit_registry(discovery_root_str: str) -> dict[str, dict[str, Any]]:
    path = audit_path(Path(discovery_root_str))
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    flows = data.get("flows") or {}
    return {str(k): v for k, v in flows.items() if isinstance(v, dict)}


def audit_record(discovery_root: Path | str, flow_id: str) -> dict[str, Any] | None:
    root = str(discovery_root)
    reg = load_flow_audit_registry(root)
    rec = reg.get(flow_id)
    return rec if isinstance(rec, dict) else None
