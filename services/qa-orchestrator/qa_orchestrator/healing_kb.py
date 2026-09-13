"""Apply approved healing proposals to locator-chain overlays — never direct KB YAML mutation."""

from __future__ import annotations

import json
from pathlib import Path

from qa_orchestrator.models import HealingProposal


def overlays_path(automation_dir: Path) -> Path:
    return automation_dir / "healing" / "approved" / "locator-overlays.json"


def load_overlays(automation_dir: Path) -> dict[str, dict[str, list[str]]]:
    path = overlays_path(automation_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def apply_approved_proposal(automation_dir: Path, proposal: HealingProposal) -> Path:
    if proposal.status != "APPROVED":
        raise ValueError("Only APPROVED proposals may update locator overlays")
    overlays = load_overlays(automation_dir)
    flow_key = proposal.flow_id
    label_key = proposal.locator_label or "default"
    chain = overlays.setdefault(flow_key, {})
    prepend = proposal.fallbacks[:] if proposal.fallbacks else []
    if proposal.new_locator:
        css = _primary_to_css(proposal.new_locator)
        if css:
            prepend = [css, *prepend]
    chain[label_key] = prepend
    path = overlays_path(automation_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(overlays, indent=2), encoding="utf-8")
    return path


def _primary_to_css(primary: str) -> str | None:
    if primary.startswith("#") or primary.startswith("["):
        return primary
    if "getByTestId" in primary:
        import re

        match = re.search(r"getByTestId\('([^']+)'\)", primary)
        if match:
            return f'[data-testid="{match.group(1)}"]'
    if "getByRole" in primary:
        import re

        match = re.search(r"getByRole\('([^']+)',\s*\{\s*name:\s*'([^']+)'", primary)
        if match:
            return f'{match.group(1)}[aria-label="{match.group(2)}"]'
    return None
