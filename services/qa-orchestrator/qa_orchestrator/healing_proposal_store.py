"""Persist healing proposals without mutating discovery KB YAML."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from qa_orchestrator.models import HealingProposal, HealingProposalStatus


def proposals_dir(automation_dir: Path) -> Path:
    path = automation_dir / "healing" / "proposals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def approved_dir(automation_dir: Path) -> Path:
    path = automation_dir / "healing" / "approved"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_proposal(automation_dir: Path, proposal: HealingProposal) -> Path:
    path = proposals_dir(automation_dir) / f"{proposal.healing_id}.json"
    path.write_text(json.dumps(proposal.model_dump(), indent=2), encoding="utf-8")
    return path


def load_proposal(automation_dir: Path, healing_id: str) -> HealingProposal | None:
    path = proposals_dir(automation_dir) / f"{healing_id}.json"
    if not path.exists():
        return None
    return HealingProposal.model_validate(json.loads(path.read_text(encoding="utf-8")))


def update_proposal_status(
    automation_dir: Path,
    healing_id: str,
    status: HealingProposalStatus,
) -> HealingProposal | None:
    proposal = load_proposal(automation_dir, healing_id)
    if proposal is None:
        return None
    proposal.status = status
    save_proposal(automation_dir, proposal)
    if status == "APPROVED":
        approved_path = approved_dir(automation_dir) / f"{proposal.flow_id}.json"
        approved_path.write_text(json.dumps(proposal.model_dump(), indent=2), encoding="utf-8")
    return proposal


def new_healing_id(prefix: str = "heal") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{prefix}-{ts}"
