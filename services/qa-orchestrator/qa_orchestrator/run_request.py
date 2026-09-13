from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunRequest:
    goal: str
    run_type: str = "adhoc"
    model: str | None = None
    run_id: str | None = None
    context_packets: list[dict[str, Any]] = field(default_factory=list)
    skip_discovery: bool = False
    skip_execution: bool = False
