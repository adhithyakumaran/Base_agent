from __future__ import annotations

from qa_orchestrator.execution_gate import ExecutionGateDecision
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.models import ExecutionGateSnapshot, IntentClassification, SuiteSelectionPlan
from qa_orchestrator.suite_commands import (
    build_flow_command,
    build_negative_flow_commands,
    build_positive_flow_commands,
    build_regression_command,
    build_sanity_command,
)


class SuiteSelector:
    """Deterministic suite pick — approved Playwright automation only."""

    def __init__(self, graph: FlowKnowledgeGraph) -> None:
        self.graph = graph

    def select(self, intent: IntentClassification) -> SuiteSelectionPlan:
        notes: list[str] = []
        candidate_flow_ids: list[str] = []
        suite_ids: list[str] = list(intent.suite_ids)
        commands: list[str] = []
        params = dict(intent.params)

        mode = intent.execution_mode

        if mode == "morning_sanity":
            sanity = self.graph.sanity_suite()
            suite_ids = [str(sanity.get("id") or "SUITE-SANITY-MORNING")]
            candidate_flow_ids = list(sanity.get("flows") or self.graph.ready_flow_ids())
            commands = [build_sanity_command(positive_only=True)]
            notes.append("Morning sanity: all READY flows, positive-only, zero LLM at execution time")

        elif mode == "regression_suite":
            reg = self.graph.regression_suite()
            suite_ids = [str(reg.get("id") or "SUITE-REGRESSION-FULL")]
            candidate_flow_ids = self.graph.ready_flow_ids()
            commands = [build_regression_command()]
            notes.append("Full regression suite — all @regression tagged flows")

        elif mode == "negative_suite":
            candidate_flow_ids = _unique_candidates(intent.flow_ids) or self.graph.flows_for_query_semantic(
                intent.goal, limit=4
            )
            if candidate_flow_ids:
                commands = build_negative_flow_commands(candidate_flow_ids[:5])
                suite_ids = [f"NEG-{fid}" for fid in candidate_flow_ids[:5]]
            else:
                commands = ["npm run test:negative"]
                suite_ids = ["SUITE-NEGATIVE"]
            notes.append("Negative / edge-case suite — invalid inputs and error paths")

        elif mode == "incident_multi_flow":
            candidate_flow_ids = list(intent.flow_ids)
            caps = self.graph.match_capabilities(intent.goal)
            for cap in caps[:4]:
                candidate_flow_ids.extend(self.graph.flows_for_capability(cap))
            if not caps and intent.capability:
                candidate_flow_ids.extend(self.graph.flows_for_capability(intent.capability))
            for fid in list(intent.flow_ids):
                candidate_flow_ids.extend(self.graph.related_flows(fid))
            candidate_flow_ids = _unique_candidates(candidate_flow_ids)
            if not candidate_flow_ids:
                candidate_flow_ids = self.graph.flows_for_query_semantic(intent.goal, limit=6)
            commands = build_positive_flow_commands(candidate_flow_ids)
            suite_ids = [f"FLOW-{fid}" for fid in candidate_flow_ids]
            notes.append(f"Incident / keyword traversal: {len(candidate_flow_ids)} related READY flow suite(s)")

        elif mode in {"new_feature", "discover"}:
            candidate_flow_ids = _unique_candidates(intent.flow_ids) or self.graph.search_flows(intent.goal, limit=1)
            if candidate_flow_ids:
                commands = [build_flow_command(candidate_flow_ids[0], polarity="positive")]
                suite_ids = [f"FLOW-{candidate_flow_ids[0]}"]
            notes.append("Primary suite run plus discovery crawl for KB/suite suggestions")

        elif mode == "adhoc_parameterized":
            candidate_flow_ids = _unique_candidates(intent.flow_ids) or ["BF-PRODUCT-003"]
            primary = candidate_flow_ids[0]
            candidate_flow_ids = [primary]
            commands = [build_flow_command(primary, polarity="positive")]
            suite_ids = [f"FLOW-{primary}"]
            notes.append(f"Parameterized run — primary executable {primary}; params via env: {params}")

        else:
            candidate_flow_ids = _unique_candidates(intent.flow_ids)
            if not candidate_flow_ids:
                candidate_flow_ids = self.graph.flows_for_query_semantic(intent.goal, limit=3)
            negative_goal = any(
                k in intent.goal.lower()
                for k in ("negative", "invalid", "wrong password", "error case", "bad login")
            )
            polarity = "negative" if negative_goal else "positive"
            if len(candidate_flow_ids) > 1:
                primary = candidate_flow_ids[0]
                notes.append(
                    f"Primary executable flow {primary}; "
                    f"{len(candidate_flow_ids) - 1} additional mapped flow(s) treated as supporting context"
                )
                candidate_flow_ids = [primary]
            if len(candidate_flow_ids) == 1:
                fid = candidate_flow_ids[0]
                commands = [build_flow_command(fid, polarity=polarity)]
                suite_ids = [f"FLOW-{fid}"]
                notes.append(f"Adhoc {polarity} run for single flow {fid}")
            elif candidate_flow_ids:
                builder = build_negative_flow_commands if polarity == "negative" else build_positive_flow_commands
                commands = builder(candidate_flow_ids[:5])
                suite_ids = [f"FLOW-{fid}" for fid in candidate_flow_ids[:5]]
                notes.append(f"Adhoc multi-flow ({polarity}): {len(candidate_flow_ids)} suite(s)")
            else:
                suite_ids = ["SUITE-SANITY-MORNING"]
                commands = [build_sanity_command(positive_only=True)]
                notes.append("No READY flow match — fallback to positive sanity suite")

        draft_refs = [f for f in intent.supporting_flow_ids if f in self.graph.draft_flow_ids()]
        if draft_refs:
            notes.append(f"Supporting DRAFT context (not executed): {', '.join(draft_refs[:6])}")

        flow_ids, blocked_flow_ids, execution_gates = _apply_execution_gate(self.graph, candidate_flow_ids)
        if blocked_flow_ids:
            notes.append(
                "Execution gate blocked "
                f"{len(blocked_flow_ids)} flow(s): {', '.join(blocked_flow_ids[:8])}"
            )
            for gate in execution_gates:
                if not gate.executable:
                    notes.append(f"  · {gate.flow_id}: `{gate.reason_code}` — {gate.message}")

        if candidate_flow_ids and not flow_ids and commands:
            notes.append(
                "All candidate flows blocked by execution gate — per-flow commands cleared; "
                "aggregate suite commands retained only when explicitly selected"
            )
            if mode not in {"morning_sanity", "regression_suite"}:
                commands = []
                suite_ids = []

        if mode in {"morning_sanity", "regression_suite"} and not flow_ids:
            notes.append("No executable flows for aggregate suite — gate requires APPROVED artifacts")

        unsupported = [
            f
            for f in intent.flow_ids
            if f not in flow_ids and f not in blocked_flow_ids and not self.graph._is_primary(f)
        ]
        if unsupported:
            notes.append(f"Non-READY flows referenced but skipped for execution: {', '.join(unsupported)}")

        primary_executable = flow_ids[0] if flow_ids else (candidate_flow_ids[0] if candidate_flow_ids else None)
        supporting_context = list(
            dict.fromkeys(
                [
                    *intent.supporting_flow_ids,
                    *[f for f in intent.flow_ids if f != primary_executable],
                    *[f for f in candidate_flow_ids if f != primary_executable and f not in flow_ids],
                ]
            )
        )

        return SuiteSelectionPlan(
            execution_mode=mode,
            suite_ids=suite_ids,
            flow_ids=flow_ids,
            blocked_flows=blocked_flow_ids,
            execution_gates=execution_gates,
            commands=commands,
            params=params,
            runner="playwright",
            primary_only=True,
            primary_executable_flow_id=primary_executable,
            supporting_flow_ids=supporting_context,
            notes=notes,
        )


def _unique_candidates(flow_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for fid in flow_ids:
        if fid in seen:
            continue
        seen.add(fid)
        out.append(fid)
    return out


def _apply_execution_gate(
    graph: FlowKnowledgeGraph,
    candidate_flow_ids: list[str],
) -> tuple[list[str], list[str], list[ExecutionGateSnapshot]]:
    executable: list[str] = []
    blocked: list[str] = []
    gates: list[ExecutionGateSnapshot] = []
    seen: set[str] = set()

    for fid in candidate_flow_ids:
        if fid in seen:
            continue
        seen.add(fid)
        decision = graph.evaluate_execution(fid)
        gates.append(_snapshot(decision))
        if decision.executable:
            executable.append(fid)
        else:
            blocked.append(fid)

    return executable, blocked, gates


def _snapshot(decision: ExecutionGateDecision) -> ExecutionGateSnapshot:
    return ExecutionGateSnapshot(
        flow_id=decision.flow_id,
        executable=decision.executable,
        reason_code=decision.reason_code,
        message=decision.message,
        approval_status=decision.approval_status,
        kb_ready=decision.kb_ready,
        in_sme_ready=decision.in_sme_ready,
        catalog_automated=decision.catalog_automated,
        approval_stale=decision.approval_stale,
    )
