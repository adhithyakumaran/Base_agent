"""QA Planning Layer — structured plans between intent classification and execution."""

from __future__ import annotations

import re
from typing import Any

from qa_orchestrator.coverage_assessment import CoverageAssessor
from qa_orchestrator.flow_resolver import FlowResolver
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.knowledge_retriever import KnowledgeRetriever
from qa_orchestrator.llm_client import PlannerLlmClient
from qa_orchestrator.models import (
    ExecutionGateSnapshot,
    ExplorationRequest,
    FlowCoverageSnapshot,
    GenerationRequest,
    IntentClassification,
    PlanningResult,
    PlanningStrategy,
    RiskLevel,
    TestPolarity,
)
from qa_orchestrator.param_validator import validate_run_params
from qa_orchestrator.planner_policy import PlannerPolicy


PLANNER_SYSTEM = """You are ScoutAI QA Planner for Oracle APEX Endless Aisle.
Propose a structured QA plan. Do NOT emit browser steps or Playwright code.
Return ONLY valid JSON with keys:
  strategy (REUSE_EXISTING|EXPLORE|GENERATE|ASK_USER|BLOCK)
  secondary_strategies (array of same enum, optional)
  candidate_flows (array of BF-* ids from context)
  capabilities (array of strings)
  polarity (positive|negative|mixed|parameterized)
  parameters (object — e.g. sku)
  expected_evidence (array — screenshot, dom, url, console, network, api_response, business_marker)
  reasoning_summary (2 sentences)
  confidence (0.0-1.0)
Prefer REUSE_EXISTING when approved coverage exists. Use EXPLORE for new/changed UI. Use GENERATE only when user asks to create automation. Never bypass approval gates."""


class QaPlanner:
    """Transform intent + KB context into a validated PlanningResult."""

    def __init__(
        self,
        graph: FlowKnowledgeGraph,
        llm: PlannerLlmClient | None = None,
        retriever: KnowledgeRetriever | None = None,
    ) -> None:
        self.graph = graph
        self.llm = llm or PlannerLlmClient(enabled=False)
        self.retriever = retriever
        self.policy = PlannerPolicy()
        self.coverage = CoverageAssessor(graph)

    def plan(
        self,
        intent: IntentClassification,
        *,
        context_packets: list[dict[str, Any]] | None = None,
    ) -> PlanningResult:
        policy = self.policy.evaluate_request(intent.goal)
        resolution = None
        if intent.execution_mode not in {"morning_sanity", "regression_suite"}:
            resolution = FlowResolver(self.graph, self.llm).resolve(
                intent.goal, intent_flow_ids=list(intent.flow_ids)
            )

        if resolution and resolution.decision == "FLOW_MISMATCH":
            blocked_intent = intent.model_copy(
                update={
                    "flow_ids": [],
                    "reasoning": "; ".join(resolution.match_reasons) or "Flow path mismatch",
                }
            )
            return PlanningResult(
                request=intent.goal,
                intent=blocked_intent,
                strategy="BLOCK",
                confidence=resolution.confidence,
                candidate_flows=[c.flow_id for c in resolution.candidate_flows],
                selected_flows=[],
                blocked_flows=[c.flow_id for c in resolution.candidate_flows if not c.executable],
                reasoning_summary="FLOW_MISMATCH — documented path conflicts with request; automatic execution blocked.",
                next_actions=["Review flow audit", "Update KB navigation or select correct capability"],
                planner="flow_resolver",
                flow_resolution=resolution.model_dump(),
                execution_allowed=False,
                requires_human_approval=True,
            )

        if resolution and resolution.decision == "DISCOVERY_REQUIRED" and not intent.flow_ids:
            explore_intent = intent.model_copy(
                update={
                    "flow_ids": [],
                    "execution_mode": "discover"
                    if intent.execution_mode == "adhoc_existing"
                    else intent.execution_mode,
                    "reasoning": "; ".join(resolution.match_reasons) or "No trusted executable flow",
                }
            )
            exploration, generation = self._build_contracts(
                intent=explore_intent,
                strategy="EXPLORE",
                secondary=["GENERATE"],
                candidate_flows=[c.flow_id for c in resolution.candidate_flows[:6]],
                capabilities=[resolution.capability] if resolution.capability else [],
                validated_params={},
            )
            return PlanningResult(
                request=intent.goal,
                intent=explore_intent,
                strategy="EXPLORE",
                secondary_strategies=["GENERATE"],
                confidence=resolution.confidence,
                candidate_flows=[c.flow_id for c in resolution.candidate_flows],
                selected_flows=[],
                exploration_required=True,
                generation_required=True,
                exploration=exploration,
                generation=generation,
                reasoning_summary=(
                    "DISCOVERY_REQUIRED — explore app, draft scenario/automation, "
                    "SME approval before execution."
                ),
                next_actions=[
                    "Run read-only exploration",
                    "Draft scenario/test case",
                    "Capture evidence",
                    "SME approval before marking executable",
                ],
                planner="flow_resolver",
                flow_resolution=resolution.model_dump(),
                execution_allowed=False,
                requires_human_approval=True,
            )

        if resolution and resolution.primary_flow_id:
            primary_id = resolution.primary_flow_id
            meta = self.graph.flow_meta(primary_id) or {}
            if meta.get("status") == "SUPERSEDED" and meta.get("superseded_by"):
                primary_id = str(meta["superseded_by"])
            intent = intent.model_copy(
                update={
                    "flow_ids": [primary_id],
                    "supporting_flow_ids": list(
                        dict.fromkeys([*resolution.supporting_flow_ids, *intent.supporting_flow_ids])
                    ),
                    "capability": resolution.capability or intent.capability,
                    "confidence": max(float(intent.confidence or 0), resolution.confidence),
                    "reasoning": "; ".join(resolution.match_reasons) or intent.reasoning,
                }
            )

        llm_proposal = self._propose_llm(intent, context_packets=context_packets)

        candidate_flows, retrieval_diag = self._resolve_candidates(intent, llm_proposal)
        candidate_flows, superseded_notes = self._redirect_superseded(candidate_flows)

        validated_params, param_error = self._validate_parameters(intent, llm_proposal)
        polarity = self._resolve_polarity(intent, llm_proposal)
        capabilities = self._resolve_capabilities(intent, candidate_flows, llm_proposal)

        gates, selected_flows, blocked_flows = self._apply_gate(candidate_flows)
        coverage_snaps = [
            self.coverage.assess_flow(fid, goal=intent.goal, intent=intent) for fid in candidate_flows
        ]
        coverage_summary = self.coverage.coverage_summary(coverage_snaps)

        strategy, secondary, next_actions = self._choose_strategy(
            intent=intent,
            policy=policy,
            candidate_flows=candidate_flows,
            selected_flows=selected_flows,
            blocked_flows=blocked_flows,
            coverage_snaps=coverage_snaps,
            param_error=param_error,
            llm_proposal=llm_proposal,
        )

        risk = self._resolve_risk(policy.risk_level, candidate_flows, intent.goal)
        requires_approval = self._requires_human_approval(
            strategy=strategy,
            gates=gates,
            coverage_snaps=coverage_snaps,
            risk=risk,
        )
        execution_allowed = self._execution_allowed(
            strategy=strategy,
            intent=intent,
            selected_flows=selected_flows,
            blocked_flows=blocked_flows,
            param_error=param_error,
            policy_blocked=policy.blocked,
        )
        expected_evidence = self._expected_evidence(intent, llm_proposal, polarity, risk)
        exploration, generation = self._build_contracts(
            intent=intent,
            strategy=strategy,
            secondary=secondary,
            candidate_flows=candidate_flows,
            capabilities=capabilities,
            validated_params=validated_params,
        )

        refined_intent = intent.model_copy(
            update={
                "flow_ids": selected_flows if selected_flows else candidate_flows[:5],
                "params": validated_params or intent.params,
                "capability": capabilities[0] if capabilities and not intent.capability else intent.capability,
            }
        )

        reasoning = (llm_proposal or {}).get("reasoning_summary") or intent.reasoning
        if superseded_notes:
            reasoning = f"{reasoning} {'; '.join(superseded_notes)}"
        if param_error:
            reasoning = f"{reasoning} Parameter validation failed: {param_error}"

        confidence = float((llm_proposal or {}).get("confidence") or intent.confidence or 0.65)
        planner_tag = "llm+deterministic" if llm_proposal else "deterministic"

        return PlanningResult(
            request=intent.goal,
            intent=refined_intent,
            strategy=strategy,
            secondary_strategies=secondary,
            confidence=confidence,
            capabilities=capabilities,
            candidate_flows=candidate_flows,
            selected_flows=selected_flows,
            blocked_flows=blocked_flows,
            execution_gates=gates,
            existing_coverage=coverage_snaps,
            exploration_required=strategy == "EXPLORE" or "EXPLORE" in secondary,
            generation_required=strategy == "GENERATE" or "GENERATE" in secondary,
            exploration=exploration,
            generation=generation,
            parameters=intent.params,
            validated_parameters=validated_params,
            expected_evidence=expected_evidence,
            risk_level=risk,
            requires_human_approval=requires_approval,
            execution_allowed=execution_allowed,
            polarity=polarity,
            coverage_assessment=coverage_summary,
            reasoning_summary=str(reasoning or intent.reasoning),
            next_actions=next_actions,
            planner=planner_tag,
            retrieval_diagnostics=retrieval_diag,
            flow_resolution=resolution.model_dump() if resolution else None,
        )

    def _propose_llm(
        self,
        intent: IntentClassification,
        *,
        context_packets: list[dict[str, Any]] | None,
    ) -> dict[str, Any] | None:
        if not self.llm.enabled:
            return None
        kb_context = self.graph.flow_kb.context_block(intent.goal, limit=6)[0]
        graph_ctx = self.graph.graph_context(intent.goal)
        packet_text = "\n".join(str(p) for p in (context_packets or [])[:5])
        data, _resp = self.llm.complete_json(
            purpose="qa_plan",
            system=PLANNER_SYSTEM,
            prompt=(
                f"User request: {intent.goal}\n"
                f"Classifier mode: {intent.execution_mode}\n"
                f"Classifier flows: {', '.join(intent.flow_ids) or 'none'}\n"
                f"Classifier params: {intent.params}\n\n"
                f"Knowledge graph:\n{graph_ctx}\n\n"
                f"Flow KB snippets:\n{kb_context}\n\n"
                f"Attached packets:\n{packet_text or '_none_'}\n"
            ),
        )
        return data

    def _resolve_candidates(
        self,
        intent: IntentClassification,
        llm_proposal: dict[str, Any] | None,
    ) -> tuple[list[str], dict[str, Any] | None]:
        seen: set[str] = set()
        out: list[str] = []
        retrieval_diag: dict[str, Any] | None = None

        def add(flow_ids: list[str]) -> None:
            for fid in flow_ids:
                if fid and fid not in seen and self.graph.flow_meta(fid):
                    seen.add(fid)
                    out.append(fid)

        if llm_proposal:
            bounded = [str(x) for x in llm_proposal.get("candidate_flows") or []]
            add([x for x in bounded if self.graph.flow_meta(x)])
        add(list(intent.flow_ids))

        if intent.execution_mode in {"morning_sanity", "regression_suite"}:
            add(self.graph.ready_flow_ids())
        elif not out:
            add(self.graph.flows_for_query_semantic(intent.goal, limit=4))
            if not out:
                add([str(x) for x in self.graph.search_flows(intent.goal, limit=4)])

        if self.retriever is not None:
            retrieval = self.retriever.retrieve(
                intent.goal,
                sme_ready_only=False,
                approval_only=False,
                top_k=6,
            )
            retrieval_diag = retrieval.diagnostics.model_dump()
            add(retrieval.flow_ids)

        return out, retrieval_diag

    def _redirect_superseded(self, flow_ids: list[str]) -> tuple[list[str], list[str]]:
        notes: list[str] = []
        out: list[str] = []
        seen: set[str] = set()
        for fid in flow_ids:
            meta = self.graph.flow_meta(fid) or {}
            status = str(meta.get("status") or "")
            superseded_by = meta.get("superseded_by")
            if status == "SUPERSEDED" and superseded_by:
                replacement = str(superseded_by)
                notes.append(f"{fid} superseded by {replacement}")
                fid = replacement
            if fid not in seen:
                seen.add(fid)
                out.append(fid)
        return out, notes

    def _validate_parameters(
        self,
        intent: IntentClassification,
        llm_proposal: dict[str, Any] | None,
    ) -> tuple[dict[str, str], str | None]:
        raw = dict(intent.params)
        if llm_proposal and isinstance(llm_proposal.get("parameters"), dict):
            raw.update({str(k): v for k, v in llm_proposal["parameters"].items()})
        if not raw:
            return {}, None
        try:
            return validate_run_params(raw), None
        except ValueError as exc:
            return {}, str(exc)

    def _resolve_polarity(
        self,
        intent: IntentClassification,
        llm_proposal: dict[str, Any] | None,
    ) -> TestPolarity:
        if llm_proposal:
            pol = str(llm_proposal.get("polarity") or "")
            if pol in {"positive", "negative", "mixed", "parameterized"}:
                return pol  # type: ignore[return-value]
        if intent.execution_mode == "adhoc_parameterized" or intent.params:
            return "parameterized"
        if intent.execution_mode == "negative_suite":
            return "negative"
        g = intent.goal.lower()
        if any(k in g for k in ("negative", "invalid", "wrong", "error case", "bad login", "bad sku")):
            return "negative"
        return "positive"

    def _resolve_capabilities(
        self,
        intent: IntentClassification,
        candidate_flows: list[str],
        llm_proposal: dict[str, Any] | None,
    ) -> list[str]:
        caps: list[str] = []
        if llm_proposal:
            caps.extend(str(x) for x in llm_proposal.get("capabilities") or [])
        if intent.capability:
            caps.append(intent.capability)
        caps.extend(self.graph.match_capabilities(intent.goal))
        for fid in candidate_flows[:3]:
            cap = self.graph.capability_for_flow(fid)
            if cap:
                caps.append(cap)
        seen: set[str] = set()
        out: list[str] = []
        for cap in caps:
            if cap not in seen:
                seen.add(cap)
                out.append(cap)
        return out

    def _apply_gate(
        self,
        candidate_flows: list[str],
    ) -> tuple[list[ExecutionGateSnapshot], list[str], list[str]]:
        gates: list[ExecutionGateSnapshot] = []
        selected: list[str] = []
        blocked: list[str] = []
        for fid in candidate_flows:
            decision = self.graph.evaluate_execution(fid)
            snap = ExecutionGateSnapshot(
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
            gates.append(snap)
            if decision.executable:
                selected.append(fid)
            else:
                blocked.append(fid)
        return gates, selected, blocked

    def _choose_strategy(
        self,
        *,
        intent: IntentClassification,
        policy: Any,
        candidate_flows: list[str],
        selected_flows: list[str],
        blocked_flows: list[str],
        coverage_snaps: list[FlowCoverageSnapshot],
        param_error: str | None,
        llm_proposal: dict[str, Any] | None,
    ) -> tuple[PlanningStrategy, list[PlanningStrategy], list[str]]:
        if policy.blocked:
            return "BLOCK", [], ["Request blocked by destructive-action policy"]

        if param_error:
            return "ASK_USER", [], [f"Fix parameters: {param_error}"]

        llm_strategy = str(llm_proposal.get("strategy") or "") if llm_proposal else ""
        llm_secondary = [str(x) for x in (llm_proposal or {}).get("secondary_strategies") or []]

        needs_generation = self.coverage.needs_generation(intent.goal)
        needs_explore = self.coverage.needs_exploration(intent.goal, intent, coverage_snaps)

        if intent.execution_mode in {"morning_sanity", "regression_suite"}:
            return "REUSE_EXISTING", [], ["Run aggregate suite via existing Playwright commands"]

        if needs_explore or intent.execution_mode in {"new_feature", "discover"}:
            secondary: list[PlanningStrategy] = []
            next_actions = ["Launch read-only exploration crawl"]
            if needs_generation:
                secondary.append("GENERATE")
                next_actions.append("Draft automation artifacts for SME approval")
            if llm_strategy == "GENERATE" and "GENERATE" not in secondary:
                secondary.append("GENERATE")
            return "EXPLORE", secondary, next_actions

        if not candidate_flows:
            return "ASK_USER", [], ["Clarify target flow or capability"]

        if _is_ambiguous(intent.goal) and not selected_flows:
            return "ASK_USER", [], ["Clarify ambiguous QA request or approve pending artifacts"]

        if any(s.sufficient for s in coverage_snaps):
            return "REUSE_EXISTING", [], ["Execute existing approved Playwright coverage"]

        if selected_flows:
            return "REUSE_EXISTING", [], ["Execute existing Playwright coverage for gated flows"]

        if blocked_flows:
            return "REUSE_EXISTING", [], ["Existing flow identified but blocked by execution gate"]

        if llm_strategy in {"REUSE_EXISTING", "EXPLORE", "GENERATE", "ASK_USER", "BLOCK"}:
            secondary = [s for s in llm_secondary if s in {"REUSE_EXISTING", "EXPLORE", "GENERATE", "ASK_USER", "BLOCK"}]
            return llm_strategy, secondary, [f"LLM-proposed strategy {llm_strategy}"]

        return "ASK_USER", [], ["Unable to determine safe execution path"]

    def _resolve_risk(self, base: RiskLevel, candidate_flows: list[str], goal: str) -> RiskLevel:
        levels = [base]
        for fid in candidate_flows[:5]:
            levels.append(self.policy.evaluate_flow(fid, goal))
        return self.policy.aggregate_risk(*levels)

    def _requires_human_approval(
        self,
        *,
        strategy: PlanningStrategy,
        gates: list[ExecutionGateSnapshot],
        coverage_snaps: list[FlowCoverageSnapshot],
        risk: RiskLevel,
    ) -> bool:
        if strategy in {"EXPLORE", "GENERATE", "ASK_USER"}:
            return True
        if any(not g.executable for g in gates):
            return True
        if any(not snap.sufficient for snap in coverage_snaps):
            return True
        if risk in {"HIGH", "BLOCKED"}:
            return True
        return False

    def _execution_allowed(
        self,
        *,
        strategy: PlanningStrategy,
        intent: IntentClassification,
        selected_flows: list[str],
        blocked_flows: list[str],
        param_error: str | None,
        policy_blocked: bool,
    ) -> bool:
        if policy_blocked or param_error:
            return False
        if strategy in {"BLOCK", "ASK_USER", "EXPLORE", "GENERATE"}:
            return False
        if intent.execution_mode in {"morning_sanity", "regression_suite"}:
            return bool(selected_flows)
        return bool(selected_flows)

    def _expected_evidence(
        self,
        intent: IntentClassification,
        llm_proposal: dict[str, Any] | None,
        polarity: TestPolarity,
        risk: RiskLevel,
    ) -> list[str]:
        if llm_proposal:
            ev = [str(x) for x in llm_proposal.get("expected_evidence") or []]
            if ev:
                return ev
        base = ["screenshot", "dom", "url"]
        if polarity == "negative" or risk in {"HIGH", "MEDIUM"}:
            base.extend(["console", "network"])
        if "api" in intent.goal.lower():
            base.extend(["api_response", "network"])
        if "business" in intent.goal.lower() or "invoice" in intent.goal.lower():
            base.append("business_marker")
        seen: set[str] = set()
        out: list[str] = []
        for item in base:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out

    def _build_contracts(
        self,
        *,
        intent: IntentClassification,
        strategy: PlanningStrategy,
        secondary: list[PlanningStrategy],
        candidate_flows: list[str],
        capabilities: list[str],
        validated_params: dict[str, str],
    ) -> tuple[ExplorationRequest | None, GenerationRequest | None]:
        exploration: ExplorationRequest | None = None
        generation: GenerationRequest | None = None

        if strategy == "EXPLORE" or "EXPLORE" in secondary:
            seed_flow = candidate_flows[0] if candidate_flows else (intent.flow_ids[0] if intent.flow_ids else None)
            target_url, target_page = self._seed_target(seed_flow)
            exploration = ExplorationRequest(
                target_url=target_url,
                target_page=target_page,
                goal=intent.goal,
                known_flow_context=candidate_flows[:6],
                read_only=True,
                evidence_required=["screenshot", "dom", "url"],
            )

        if strategy == "GENERATE" or "GENERATE" in secondary:
            generation = GenerationRequest(
                flow_context=candidate_flows[:6],
                scenario_objective=intent.goal,
                preconditions=[f"Capability context: {', '.join(capabilities) or 'unknown'}"],
                actions=["Observe UI paths relevant to request", "Capture evidence for SME review"],
                expected_outcomes=["Proposed Playwright scenarios aligned to business rules"],
                test_data_requirements=dict(validated_params),
                approval_required=True,
            )

        return exploration, generation

    def _seed_target(self, flow_id: str | None) -> tuple[str | None, str | None]:
        if not flow_id:
            overview = self.graph.flow_kb.app_overview()
            return overview.get("login_url"), "login"
        meta = self.graph.flow_meta(flow_id) or {}
        doc = meta.get("doc") or {}
        entry = doc.get("entry_point") or {}
        route = entry.get("route")
        page = entry.get("page") or doc.get("pages", [None])[0] if doc.get("pages") else None
        return (str(route) if route else None, str(page) if page else flow_id)


def _is_ambiguous(goal: str) -> bool:
    g = goal.lower().strip()
    if len(g.split()) <= 2 and g in {"test", "check", "run", "verify", "qa"}:
        return True
    if re.search(r"\b(something|anything|not sure|maybe)\b", g):
        return True
    return False
