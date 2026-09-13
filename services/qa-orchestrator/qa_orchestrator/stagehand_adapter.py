"""Optional Stagehand augmentation — disabled by default."""

from __future__ import annotations

import os
from typing import Any


class StagehandAdapter:
    """LLM/Stagehand proposals must pass ExplorationPolicy before execution."""

    def __init__(self) -> None:
        self._enabled = os.environ.get("STAGEHAND_ENABLED", "").lower() in {"1", "true", "yes"}

    @property
    def enabled(self) -> bool:
        return self._enabled

    def observe(self, goal: str, *, elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        # Optional SDK hook — fallback to deterministic keyword matching when unavailable.
        try:
            return self._observe_sdk(goal, elements)
        except Exception:
            return self._observe_heuristic(goal, elements)

    def _observe_sdk(self, goal: str, elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Stagehand SDK is optional; keep import lazy so CI/tests do not require it.
        return self._observe_heuristic(goal, elements)

    def _observe_heuristic(self, goal: str, elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tokens = {t for t in goal.lower().replace("-", " ").split() if len(t) > 2}
        proposals: list[dict[str, Any]] = []
        for el in elements:
            hay = " ".join(
                [
                    str(el.get("text") or ""),
                    str(el.get("name") or ""),
                    str(el.get("role") or ""),
                    str(el.get("tag") or ""),
                ]
            ).lower()
            if tokens & set(hay.split()):
                proposals.append(
                    {
                        "action": "click" if el.get("tag") in {"button", "a"} else "fill",
                        "target": el.get("element_id"),
                        "description": hay[:120],
                        "source": "stagehand_heuristic",
                    }
                )
        return proposals[:5]
