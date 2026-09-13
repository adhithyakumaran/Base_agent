"""Test generation pipeline — scenario → test case → spec → validation → DRAFT."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from qa_orchestrator.action_model import build_action_model
from qa_orchestrator.generation_journal import new_journal_id, save_journal
from qa_orchestrator.generation_validator import (
    validate_output_path,
    validate_playwright_discovery,
    validate_spec_content,
    validate_syntax_typescript,
)
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.models import (
    DiscoveryCandidate,
    ExplorationResult,
    GeneratedLocator,
    GenerationRequest,
    GenerationResult,
    GeneratorJournal,
    PlanningResult,
)
from qa_orchestrator.playwright_codegen import generate_spec
from qa_orchestrator.scenario_builder import build_scenario
from qa_orchestrator.test_case_builder import build_test_case


class GenerationService:
    DRAFT_ROOT = "generated/drafts"

    def __init__(self, graph: FlowKnowledgeGraph) -> None:
        self.graph = graph
        self.automation_dir = Path(graph.automation_dir)

    def generate_from_planning(
        self,
        planning: PlanningResult,
        *,
        exploration: ExplorationResult | None = None,
        generation_id: str | None = None,
    ) -> GenerationResult:
        if planning.strategy == "BLOCK":
            return GenerationResult(
                generation_id=generation_id or new_journal_id(),
                status="BLOCKED",
                flow_id=planning.candidate_flows[0] if planning.candidate_flows else "UNKNOWN",
                message="Generation blocked by planner policy",
                blocked_execution=True,
            )
        if planning.strategy == "REUSE_EXISTING":
            flow_id = planning.selected_flows[0] if planning.selected_flows else (
                planning.candidate_flows[0] if planning.candidate_flows else "UNKNOWN"
            )
            return GenerationResult(
                generation_id=generation_id or new_journal_id(),
                status="BLOCKED",
                flow_id=flow_id,
                message="REUSE_EXISTING strategy — use approved coverage instead of generating",
                blocked_execution=True,
            )
        if not planning.generation_required or planning.generation is None:
            return GenerationResult(
                generation_id=generation_id or new_journal_id(),
                status="NEEDS_REVIEW",
                flow_id=planning.candidate_flows[0] if planning.candidate_flows else "UNKNOWN",
                message="Generation not requested by planner",
                blocked_execution=True,
            )
        if planning.strategy == "REUSE_EXISTING" and planning.execution_allowed:
            return GenerationResult(
                generation_id=generation_id or new_journal_id(),
                status="BLOCKED",
                flow_id=planning.selected_flows[0] if planning.selected_flows else (
                    planning.candidate_flows[0] if planning.candidate_flows else "UNKNOWN"
                ),
                message="Existing approved coverage sufficient — generation skipped",
                blocked_execution=True,
            )
        if self._has_existing_approved_spec(planning):
            flow_id = planning.candidate_flows[0] if planning.candidate_flows else "BF-PRODUCT-003"
            return GenerationResult(
                generation_id=generation_id or new_journal_id(),
                status="BLOCKED",
                flow_id=flow_id,
                message="Approved parameterized coverage already exists — do not regenerate",
                blocked_execution=True,
            )

        flow_id = self._resolve_flow_id(planning, exploration)
        candidate = self._load_candidate(exploration)
        return self.generate(
            flow_id=flow_id,
            request=planning.generation,
            exploration=exploration,
            candidate=candidate,
            goal=planning.request,
            polarity=planning.polarity,
            generation_id=generation_id,
        )

    def generate(
        self,
        *,
        flow_id: str,
        request: GenerationRequest,
        exploration: ExplorationResult | None = None,
        candidate: DiscoveryCandidate | None = None,
        goal: str = "",
        polarity: str = "positive",
        generation_id: str | None = None,
    ) -> GenerationResult:
        gen_id = generation_id or new_journal_id()
        scenario = build_scenario(
            flow_id=flow_id,
            request=request,
            exploration=exploration,
            candidate=candidate,
            goal=goal,
            polarity=polarity,  # type: ignore[arg-type]
        )
        test_case = build_test_case(scenario)
        actions = build_action_model(test_case, exploration=exploration, candidate=candidate)
        spec_content = generate_spec(scenario=scenario, test_case=test_case, actions=actions)

        rel_path = Path(self.DRAFT_ROOT) / flow_id / f"{test_case.test_case_id}.spec.ts"
        out_path = self.automation_dir / rel_path
        path_check = validate_output_path(out_path, self.automation_dir)
        if not path_check.valid:
            return self._failure(
                gen_id,
                flow_id,
                scenario,
                test_case,
                actions,
                message=path_check.message,
                status="INVALID",
                reason=path_check,
            )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            out_path.write_text(spec_content, encoding="utf-8")
        except OSError as exc:
            from qa_orchestrator.models import GenerationValidation

            write_check = GenerationValidation(
                valid=False,
                reason_code="generation.write_failed",
                message=str(exc),
            )
            return self._failure(
                gen_id,
                flow_id,
                scenario,
                test_case,
                actions,
                message=f"Failed to write generated spec: {exc}",
                status="VALIDATION_FAILED",
                reason=write_check,
            )

        checks = [path_check]
        content_check = validate_spec_content(spec_content, test_case=test_case)
        checks.append(content_check)
        syntax_check = validate_syntax_typescript(spec_content)
        checks.append(syntax_check)
        discovery_check = validate_playwright_discovery(out_path, self.automation_dir)
        checks.append(discovery_check)

        validation = self._merge_checks(checks)
        status = "READY_FOR_APPROVAL" if validation.valid else "VALIDATION_FAILED"
        review_status = "PENDING_SME_APPROVAL" if validation.valid else "DRAFT"

        locators = self._collect_locators(actions)
        journal = GeneratorJournal(
            generation_id=gen_id,
            request=goal or request.scenario_objective,
            flow_id=flow_id,
            scenario_id=scenario.scenario_id,
            test_case_id=test_case.test_case_id,
            source_observations=(exploration.observations if exploration else [])[:8],
            actions=actions,
            locators=locators,
            generated_file=str(rel_path),
            validation=validation,
            review_status=review_status,  # type: ignore[arg-type]
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        save_journal(self.automation_dir, journal)
        self._persist_draft_metadata(flow_id, scenario, test_case, journal)

        return GenerationResult(
            generation_id=gen_id,
            status=status,  # type: ignore[arg-type]
            flow_id=flow_id,
            scenario=scenario,
            test_case=test_case,
            actions=actions,
            generated_spec_path=str(rel_path),
            validation=validation,
            journal=journal,
            discovery_candidate_id=candidate.candidate_id if candidate else None,
            message=validation.message if validation.valid else f"Validation failed: {validation.message}",
            blocked_execution=True,
        )

    def _has_existing_approved_spec(self, planning: PlanningResult) -> bool:
        goal = planning.request.lower()
        if "sku" not in goal and planning.polarity != "parameterized":
            return False
        param_spec = self.automation_dir / "tests" / "product" / "QA-PARAM-SKU.spec.ts"
        return param_spec.exists()

    def _resolve_flow_id(
        self,
        planning: PlanningResult,
        exploration: ExplorationResult | None,
    ) -> str:
        for source in (
            planning.selected_flows,
            planning.candidate_flows,
            (exploration.discovered_flows if exploration else []),
            planning.generation.flow_context if planning.generation else [],
        ):
            for fid in source:
                if fid.startswith("BF-"):
                    return fid
        return "BF-PRODUCT-003"

    def _load_candidate(self, exploration: ExplorationResult | None) -> DiscoveryCandidate | None:
        if not exploration or not exploration.discovery_candidates:
            return None
        return exploration.discovery_candidates[0]

    def _collect_locators(self, actions: list) -> list[GeneratedLocator]:
        locs: list[GeneratedLocator] = []
        for action in actions:
            if action.locator:
                locs.append(action.locator)
        return locs

    def _merge_checks(self, checks: list) -> object:
        from qa_orchestrator.models import GenerationValidation

        failed = next((c for c in checks if not c.valid), None)
        if failed:
            return GenerationValidation(
                valid=False,
                reason_code=failed.reason_code,
                message=failed.message,
                checks=[c.model_dump() for c in checks],
            )
        return GenerationValidation(
            valid=True,
            reason_code="generation.valid",
            message="All validation checks passed",
            checks=[c.model_dump() for c in checks],
        )

    def _persist_draft_metadata(self, flow_id: str, scenario, test_case, journal) -> None:
        meta_dir = self.automation_dir / "generated" / "drafts" / flow_id
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "scenario.draft.json").write_text(
            json.dumps(scenario.model_dump(), indent=2),
            encoding="utf-8",
        )
        (meta_dir / "test-case.draft.json").write_text(
            json.dumps(test_case.model_dump(), indent=2),
            encoding="utf-8",
        )
        (meta_dir / "journal.json").write_text(
            json.dumps(journal.model_dump(), indent=2),
            encoding="utf-8",
        )

    def _failure(self, gen_id, flow_id, scenario, test_case, actions, *, message, status, reason):
        from qa_orchestrator.models import GenerationValidation

        validation = reason if isinstance(reason, GenerationValidation) else None
        return GenerationResult(
            generation_id=gen_id,
            status=status,  # type: ignore[arg-type]
            flow_id=flow_id,
            scenario=scenario,
            test_case=test_case,
            actions=actions,
            validation=validation,
            message=message,
            blocked_execution=True,
        )
