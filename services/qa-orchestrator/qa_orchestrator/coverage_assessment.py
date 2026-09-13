"""Assess whether existing automation coverage is sufficient for a QA request."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.models import FlowCoverageSnapshot, IntentClassification

_NEW_FEATURE_MARKERS = (
    "new ",
    "just added",
    "recently added",
    "yesterday",
    "new banner",
    "new filter",
    "ui change",
    "added yesterday",
)

_GENERATION_MARKERS = (
    "create automation",
    "create automated coverage",
    "generate test",
    "write test",
    "automate",
)


class CoverageAssessor:
    def __init__(self, graph: FlowKnowledgeGraph) -> None:
        self.graph = graph
        self.design_root = graph.automation_dir / "test-design" / "flows"

    def assess_flow(self, flow_id: str, *, goal: str, intent: IntentClassification) -> FlowCoverageSnapshot:
        meta = self.graph.flow_meta(flow_id) or {}
        gate = self.graph.evaluate_execution(flow_id)
        positive, negative, parameterized = self._count_tests(flow_id)
        notes: list[str] = []
        sufficient = True

        g = goal.lower()
        needs_negative = intent.execution_mode == "negative_suite" or any(
            k in g for k in ("negative", "invalid", "wrong", "error case", "bad login", "bad sku")
        )
        needs_parameterized = intent.execution_mode == "adhoc_parameterized" or bool(intent.params)

        if needs_negative and negative == 0:
            sufficient = False
            notes.append("negative coverage missing for negative intent")
        if needs_parameterized and not parameterized:
            sufficient = False
            notes.append("parameterized coverage not confirmed in test design")
        if any(marker in g for marker in _NEW_FEATURE_MARKERS):
            sufficient = False
            notes.append("request references new/changed functionality beyond existing tests")
        if not gate.executable:
            sufficient = False
            notes.append(f"execution gate: {gate.reason_code}")

        return FlowCoverageSnapshot(
            flow_id=flow_id,
            kb_status=str(meta.get("status") or "UNKNOWN"),
            approval_status=gate.approval_status,
            gate_executable=gate.executable,
            gate_reason_code=gate.reason_code,
            positive_tests=positive,
            negative_tests=negative,
            parameterized=parameterized,
            sufficient=sufficient and gate.executable,
            notes=notes,
        )

    def coverage_summary(self, snapshots: list[FlowCoverageSnapshot]) -> str:
        if not snapshots:
            return "No candidate flows resolved for coverage assessment"
        executable = [s for s in snapshots if s.gate_executable]
        sufficient = [s for s in snapshots if s.sufficient]
        if sufficient:
            return f"Sufficient existing coverage for {len(sufficient)} flow(s)"
        if executable:
            return "Existing tests found but coverage match insufficient for request"
        if snapshots:
            return "Candidate flows exist but none pass execution gate"
        return "No coverage available"

    def needs_exploration(self, goal: str, intent: IntentClassification, snapshots: list[FlowCoverageSnapshot]) -> bool:
        g = goal.lower()
        if intent.execution_mode in {"new_feature", "discover"}:
            return True
        if any(marker in g for marker in _NEW_FEATURE_MARKERS):
            return True
        if "discover" in g or "explore" in g or "crawl" in g:
            return True
        if snapshots and not any(s.sufficient for s in snapshots):
            if any(marker in g for marker in ("filter", "banner", "new ")):
                return True
        return False

    def needs_generation(self, goal: str) -> bool:
        g = goal.lower()
        return any(marker in g for marker in _GENERATION_MARKERS)

    def _count_tests(self, flow_id: str) -> tuple[int, int, bool]:
        path = self.design_root / flow_id / "test-cases.yaml"
        if not path.exists():
            return 0, 0, False
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return 0, 0, False
        cases = doc.get("test_cases") or []
        positive = 0
        negative = 0
        parameterized = False
        for case in cases:
            case_type = str(case.get("type") or "").lower()
            if case_type == "positive":
                positive += 1
            elif case_type == "negative":
                negative += 1
            hay = yaml.safe_dump(case).lower()
            if "sku" in hay or "parameter" in hay:
                parameterized = True
        if re.search(r"\bsku\b", path.read_text(encoding="utf-8"), re.I):
            parameterized = True
        return positive, negative, parameterized
