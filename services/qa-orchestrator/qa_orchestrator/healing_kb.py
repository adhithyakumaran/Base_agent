"""Apply approved healing proposals to locator-chain overlays — never direct KB YAML mutation."""

from __future__ import annotations

from qa_orchestrator.healing_overlay import (
    apply_approved_proposal,
    load_overlay_store,
    load_overlays,
    overlays_path,
    primary_to_css,
)

__all__ = [
    "apply_approved_proposal",
    "load_overlay_store",
    "load_overlays",
    "overlays_path",
    "primary_to_css",
]
