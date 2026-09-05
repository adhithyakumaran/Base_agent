from __future__ import annotations

from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.models import IntentClassification, SuiteSelectionPlan


class SuiteSelector:
    """Deterministic suite pick — approved Playwright automation only."""

    def __init__(self, graph: FlowKnowledgeGraph) -> None:
        self.graph = graph

    def select(self, intent: IntentClassification) -> SuiteSelectionPlan:
        notes: list[str] = []
        flow_ids: list[str] = []
        suite_ids: list[str] = list(intent.suite_ids)
        commands: list[str] = []
        params = dict(intent.params)

        mode = intent.execution_mode

        if mode == "morning_sanity":
            sanity = self.graph.sanity_suite()
            suite_ids = [str(sanity.get("id") or "SUITE-SANITY-MORNING")]
            flow_ids = list(sanity.get("flows") or self.graph.ready_flow_ids())
            commands = ["npm run test:sanity"]
            notes.append("Morning sanity: all READY flows, zero LLM at execution time")

        elif mode == "incident_multi_flow":
            flow_ids = list(intent.flow_ids)
            if intent.capability:
                flow_ids.extend(self.graph.flows_for_capability(intent.capability))
            for fid in intent.flow_ids:
                flow_ids.extend(self.graph.related_flows(fid))
            flow_ids = _unique_primary(self.graph, flow_ids)
            if not flow_ids:
                flow_ids = self.graph.search_flows(intent.goal, limit=4)
                flow_ids = _unique_primary(self.graph, flow_ids)
            commands = [f"npm run test:flow -- @{fid}" for fid in flow_ids]
            suite_ids = [f"FLOW-{fid}" for fid in flow_ids]
            notes.append(f"Incident traversal: {len(flow_ids)} related READY flow suite(s)")

        elif mode in {"new_feature", "discover"}:
            flow_ids = _unique_primary(self.graph, intent.flow_ids) or self.graph.search_flows(intent.goal, limit=1)
            if flow_ids:
                commands = [f"npm run test:flow -- @{flow_ids[0]}"]
                suite_ids = [f"FLOW-{flow_ids[0]}"]
            notes.append("Primary suite run plus discovery crawl for KB/suite suggestions")

        elif mode == "adhoc_parameterized":
            flow_ids = _unique_primary(self.graph, intent.flow_ids) or ["BF-PRODUCT-003"]
            fid = flow_ids[0]
            commands = [f"npm run test:flow -- @{fid}"]
            suite_ids = [f"FLOW-{fid}"]
            notes.append(f"Parameterized run — pass params via env: {params}")

        else:
            flow_ids = _unique_primary(self.graph, intent.flow_ids)
            if not flow_ids:
                hits = self.graph.search_flows(intent.goal, limit=1)
                flow_ids = _unique_primary(self.graph, hits)
            if len(flow_ids) == 1:
                fid = flow_ids[0]
                commands = [f"npm run test:flow -- @{fid}"]
                suite_ids = [f"FLOW-{fid}"]
            elif flow_ids:
                commands = [f"npm run test:flow -- @{fid}" for fid in flow_ids[:3]]
                suite_ids = [f"FLOW-{fid}" for fid in flow_ids[:3]]
            else:
                suite_ids = ["SUITE-SANITY-MORNING"]
                commands = ["npm run test:sanity"]
                notes.append("No READY flow match — fallback to sanity suite")

        draft_refs = [f for f in intent.supporting_flow_ids if f in self.graph.draft_flow_ids()]
        if draft_refs:
            notes.append(f"Supporting DRAFT context (not executed): {', '.join(draft_refs[:6])}")

        unsupported = [f for f in intent.flow_ids if f not in flow_ids and not self.graph._is_primary(f)]
        if unsupported:
            notes.append(f"Non-READY flows referenced but skipped for execution: {', '.join(unsupported)}")

        return SuiteSelectionPlan(
            execution_mode=mode,
            suite_ids=suite_ids,
            flow_ids=flow_ids,
            commands=commands,
            params=params,
            runner="playwright",
            primary_only=True,
            notes=notes,
        )


def _unique_primary(graph: FlowKnowledgeGraph, flow_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for fid in flow_ids:
        if fid in seen:
            continue
        if graph._is_primary(fid):
            seen.add(fid)
            out.append(fid)
    return out
