"""Orchestrator-facing exploration service."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from qa_orchestrator.exploration_session import ExplorationSession
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.models import ExplorationRequest, ExplorationResult, PlanningResult


class ExplorationService:
    def __init__(
        self,
        graph: FlowKnowledgeGraph,
        *,
        dry_run: bool | None = None,
        automation_dir: Path | None = None,
    ) -> None:
        self.graph = graph
        self.automation_dir = Path(
            automation_dir or graph.automation_dir
        )
        env_dry = os.environ.get("QA_EXPLORE_DRY_RUN", "").lower() in {"1", "true", "yes"}
        crawl_dry = os.environ.get("QA_CRAWL_LIVE", "").lower() not in {"1", "true", "yes"}
        self.dry_run = dry_run if dry_run is not None else (env_dry or crawl_dry)

    def run(
        self,
        request: ExplorationRequest,
        *,
        exploration_id: str | None = None,
        existing_page: Any | None = None,
    ) -> ExplorationResult:
        exp_id = exploration_id or f"explore-{uuid.uuid4().hex[:12]}"
        session = ExplorationSession(
            request,
            exploration_id=exp_id,
            automation_dir=self.automation_dir,
            dry_run=self.dry_run,
            existing_page=existing_page,
        )
        result = session.run()
        self._persist_candidates(result)
        return result

    def run_from_planning(
        self,
        planning: PlanningResult,
        *,
        exploration_id: str | None = None,
    ) -> ExplorationResult | None:
        if planning.strategy == "BLOCK":
            return None
        if not planning.exploration_required or planning.exploration is None:
            return None
        return self.run(planning.exploration, exploration_id=exploration_id)

    def _persist_candidates(self, result: ExplorationResult) -> None:
        candidates_dir = self.graph.discovery_root / "candidates"
        candidates_dir.mkdir(parents=True, exist_ok=True)
        for candidate in result.discovery_candidates:
            path = candidates_dir / f"{candidate.candidate_id}.json"
            path.write_text(
                json.dumps(candidate.model_dump(), indent=2, default=str),
                encoding="utf-8",
            )
