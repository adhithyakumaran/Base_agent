from __future__ import annotations

import re
from typing import Any

from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.llm_client import PlannerLlmClient
from qa_orchestrator.models import ExecutionMode, IntentClassification


CLASSIFIER_SYSTEM = """You are an enterprise QA orchestrator for Oracle APEX Endless Aisle UAT.
Classify the user's natural-language request ONLY. Do NOT invent browser steps.
Return ONLY valid JSON with keys:
  execution_mode (morning_sanity|adhoc_existing|adhoc_parameterized|incident_multi_flow|new_feature|discover)
  capability (string or null)
  flow_ids (array of BF-* ids — prefer READY primary flows from context)
  supporting_flow_ids (array of DRAFT BF-* ids for context only)
  suite_ids (array e.g. SUITE-SANITY-MORNING, SUITE-REGRESSION-FULL, or per-flow tags)
  params (object — e.g. sku, item_code, search_term)
  confidence (0.0-1.0)
  reasoning (one short sentence)
Use 19 READY flows as primary automation. DRAFT flows are supporting context only — never sole execution target.
Morning sanity / scheduled health → morning_sanity, no params.
Incident with multiple areas (payment failing, checkout broken) → incident_multi_flow.
New banner / UI change / untested feature → new_feature.
SKU/item code in prompt → adhoc_parameterized with params."""


class IntentClassifier:
    def __init__(self, graph: FlowKnowledgeGraph, llm: PlannerLlmClient) -> None:
        self.graph = graph
        self.llm = llm

    def classify(
        self,
        goal: str,
        *,
        run_type: str = "adhoc",
        context_packets: list[dict[str, Any]] | None = None,
    ) -> IntentClassification:
        llm_data, llm_resp = self._classify_llm(goal, run_type=run_type, context_packets=context_packets)
        if llm_data:
            intent = self._from_llm(goal, run_type, llm_data)
            if intent.flow_ids or intent.execution_mode == "morning_sanity":
                return intent

        return self._classify_deterministic(goal, run_type=run_type, llm_error=llm_resp.error)

    def _classify_llm(
        self,
        goal: str,
        *,
        run_type: str,
        context_packets: list[dict[str, Any]] | None,
    ) -> tuple[dict[str, Any] | None, Any]:
        kb_context = self.graph.flow_kb.context_block(goal, limit=6)[0]
        graph_ctx = self.graph.graph_context(goal)
        packet_text = ""
        if context_packets:
            packet_text = "\n".join(str(p) for p in context_packets[:5])

        return self.llm.complete_json(
            purpose="intent_classify",
            system=CLASSIFIER_SYSTEM,
            prompt=(
                f"Run type hint: {run_type}\nUser request: {goal}\n\n"
                f"Knowledge graph:\n{graph_ctx}\n\n"
                f"Flow KB snippets:\n{kb_context}\n\n"
                f"Attached packets:\n{packet_text or '_none_'}\n"
            ),
        )

    def _from_llm(self, goal: str, run_type: str, data: dict[str, Any]) -> IntentClassification:
        mode = str(data.get("execution_mode") or "adhoc_existing")
        if mode not in {
            "morning_sanity",
            "adhoc_existing",
            "adhoc_parameterized",
            "incident_multi_flow",
            "new_feature",
            "discover",
        }:
            mode = "adhoc_existing"

        flow_ids = self._filter_primary([str(x) for x in data.get("flow_ids") or []])
        supporting = [str(x) for x in data.get("supporting_flow_ids") or []]
        if not flow_ids:
            flow_ids = self.graph.search_flows(goal, limit=3)
            flow_ids = self._filter_primary(flow_ids)

        params = data.get("params") if isinstance(data.get("params"), dict) else {}
        suite_ids = [str(x) for x in data.get("suite_ids") or []]

        return IntentClassification(
            goal=goal,
            run_type=run_type,
            execution_mode=mode,  # type: ignore[arg-type]
            capability=str(data.get("capability")) if data.get("capability") else None,
            flow_ids=flow_ids,
            supporting_flow_ids=supporting or self.graph.supporting_for_query(goal),
            suite_ids=suite_ids,
            params=params,
            confidence=float(data.get("confidence") or 0.75),
            reasoning=str(data.get("reasoning") or f"LLM classified as {mode}"),
            classifier="llm",
        )

    def _classify_deterministic(
        self,
        goal: str,
        *,
        run_type: str,
        llm_error: str | None = None,
    ) -> IntentClassification:
        g = goal.lower()
        mode: ExecutionMode = "adhoc_existing"
        params: dict[str, Any] = {}
        capability: str | None = None
        flow_ids: list[str] = []
        suite_ids: list[str] = []
        reasoning = "Deterministic keyword + graph classification"

        if run_type in {"sanity", "scheduled"} or any(k in g for k in ("morning sanity", "morning check", "health check", "sanity")):
            mode = "morning_sanity"
            suite_ids = ["SUITE-SANITY-MORNING"]
            flow_ids = self.graph.ready_flow_ids()
            reasoning = "Scheduled/morning sanity — all approved READY flows, no LLM at execution"
        elif any(k in g for k in ("new feature", "new banner", "ui change", "just added", "recently added")):
            mode = "new_feature"
            flow_ids = self._filter_primary(self.graph.search_flows(goal, limit=2))
            reasoning = "New/changed UI — run existing suite plus discovery crawl"
        elif any(k in g for k in ("payment fail", "checkout fail", "incident", "multiple flow", "end to end broken")):
            mode = "incident_multi_flow"
            caps = self.graph.match_capabilities(goal) or ["Product Search"]
            capability = caps[0] if caps else None
            for cap in caps[:3]:
                flow_ids.extend(self.graph.flows_for_capability(cap))
            flow_ids = list(dict.fromkeys(self._filter_primary(flow_ids)))
            reasoning = "Incident-style request — traverse capability graph for related suites"
        elif "discover" in g or "crawl" in g or "explore app" in g:
            mode = "discover"
            flow_ids = self._filter_primary(self.graph.search_flows(goal, limit=1))
            reasoning = "Discovery/crawl request"
        else:
            sku = _extract_param(g, r"\b(?:sku|item\s*code|itemcode|product\s*id)[:\s#-]*([a-z0-9-]{4,})\b")
            if sku:
                mode = "adhoc_parameterized"
                params["sku"] = sku
                flow_ids = self._primary_or(["BF-PRODUCT-003", "BF-HOME-010-01"])
                capability = "Product Search"
                reasoning = f"Parameterized product search for SKU/item {sku}"
            elif "find price" in g or "findprice" in g:
                mode = "adhoc_existing"
                flow_ids = self._primary_or(["BF-FINDPRICE-004"])
                supporting = ["BF-FINDPRICE-004"] if "BF-FINDPRICE-004" not in flow_ids else []
                capability = "Pricing"
                reasoning = "Find Price module check (DRAFT KB supporting until SME approves)"
            elif "login" in g:
                flow_ids = self._primary_or(["BF-LOGIN-001"])
                capability = "Authentication"
            elif "logout" in g:
                flow_ids = self._primary_or(["BF-LOGOUT-002"])
                capability = "Authentication"
            elif "report" in g:
                flow_ids = self._primary_or(["BF-REPORTS-007"])
                capability = "Reporting"
            elif "rivaah" in g or "wedding" in g:
                flow_ids = self._primary_or(["BF-RIVAAH-005"])
                capability = "Rivaah"
            elif "invoice" in g or "billing" in g:
                flow_ids = self._primary_or(["BF-MANUAL-INVOICE-009"])
                capability = "Billing"
            elif "admin" in g:
                flow_ids = self._primary_or(["BF-ADMINISTRATION-009"])
                capability = "Administration"
            elif "stock" in g or "inventory" in g:
                flow_ids = self._primary_or(["BF-PRODUCT-STOCK-VISIBILITY-009"])
                capability = "Inventory"
            elif "catalogue" in g or "catalog" in g:
                flow_ids = self._primary_or(["BF-PRODUCT-CATALOGUE-006"])
                capability = "Product Management"
            elif "best deal" in g:
                flow_ids = self._primary_or(["BF-BEST-DEAL-008"])
                capability = "Product Browse"
            elif "search" in g or "product" in g or "sku" in g:
                flow_ids = self._primary_or(["BF-PRODUCT-003", "BF-HOME-010-01"])
                capability = "Product Search"
            elif "home" in g or "navigation" in g:
                flow_ids = self._primary_or(["BF-HOME-010"])
                capability = "Application Navigation"
            else:
                hits = self.graph.search_flows(goal, limit=2)
                flow_ids = self._filter_primary(hits)

        supporting = self.graph.supporting_for_query(goal)
        if not capability and flow_ids:
            capability = self.graph.capability_for_flow(flow_ids[0])

        classifier = "deterministic" if not llm_error else f"deterministic_fallback({llm_error})"
        return IntentClassification(
            goal=goal,
            run_type=run_type,
            execution_mode=mode,
            capability=capability,
            flow_ids=flow_ids,
            supporting_flow_ids=supporting,
            suite_ids=suite_ids,
            params=params,
            confidence=0.65 if not llm_error else 0.5,
            reasoning=reasoning,
            classifier=classifier,
        )

    def _filter_primary(self, flow_ids: list[str]) -> list[str]:
        return [fid for fid in flow_ids if self.graph._is_primary(fid)]

    def _primary_or(self, candidates: list[str]) -> list[str]:
        primary = [f for f in candidates if self.graph._is_primary(f)]
        return primary or candidates[:1]


def _extract_param(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1) if m else None
