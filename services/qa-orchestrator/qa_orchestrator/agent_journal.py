"""P6 — persist structured agent decision journals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from qa_orchestrator.agent_models import AgentDecisionEntry, AgentFailureRecord, AgentRunState


def journal_path(base_dir: str | Path, run_id: str) -> Path:
    return Path(base_dir) / run_id / "journal.json"


def load_journal(run_id: str, *, base_dir: str | Path = "reports/agent") -> dict[str, Any]:
    path = journal_path(base_dir, run_id)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_journal(state: AgentRunState, *, base_dir: str | Path = "reports/agent") -> Path:
    path = journal_path(base_dir, state.run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": state.run_id,
        "request": state.request,
        "status": state.status,
        "final_result": state.final_result,
        "reason_code": state.reason_code,
        "summary": state.summary,
        "iteration": state.iteration,
        "recovery_count": state.recovery_count,
        "evidence_count": len(state.evidence_paths),
        "decision_journal": [entry.model_dump() for entry in state.decision_journal],
        "recovery_history": [entry.model_dump() for entry in state.recovery_history],
        "metadata": state.metadata,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
