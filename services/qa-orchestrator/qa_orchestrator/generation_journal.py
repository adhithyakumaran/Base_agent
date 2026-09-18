"""Persist generator journals for traceability."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from qa_orchestrator.models import GeneratorJournal


def journal_dir(automation_dir: Path) -> Path:
    path = automation_dir / "generated" / "journals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_journal(automation_dir: Path, journal: GeneratorJournal) -> Path:
    directory = journal_dir(automation_dir)
    path = directory / f"{journal.generation_id}.json"
    path.write_text(json.dumps(journal.model_dump(), indent=2), encoding="utf-8")
    return path


def load_journal(automation_dir: Path, generation_id: str) -> GeneratorJournal | None:
    path = journal_dir(automation_dir) / f"{generation_id}.json"
    if not path.exists():
        return None
    return GeneratorJournal.model_validate(json.loads(path.read_text(encoding="utf-8")))


def new_journal_id(prefix: str = "gen") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{prefix}-{ts}"
