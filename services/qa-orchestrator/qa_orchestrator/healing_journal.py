"""Persist healing journals for traceability."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from qa_orchestrator.models import HealingJournal


def journal_dir(automation_dir: Path) -> Path:
    path = automation_dir / "healing" / "journals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_journal(automation_dir: Path, journal: HealingJournal) -> Path:
    path = journal_dir(automation_dir) / f"{journal.healing_id}.json"
    path.write_text(json.dumps(journal.model_dump(), indent=2), encoding="utf-8")
    return path


def load_journal(automation_dir: Path, healing_id: str) -> HealingJournal | None:
    path = journal_dir(automation_dir) / f"{healing_id}.json"
    if not path.exists():
        return None
    return HealingJournal.model_validate(json.loads(path.read_text(encoding="utf-8")))
