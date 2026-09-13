"""P9 — backend flow inventory with accurate ExecutionGate semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qa_orchestrator.execution_gate import ExecutionGate
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph


@dataclass(frozen=True)
class FlowInventoryRow:
    flow_id: str
    name: str
    kb_status: str
    sme_ready: bool
    approval_status: str | None
    executable: bool
    reason_code: str
    message: str
    in_catalog: bool


def build_flow_inventory(*, discovery_root: str = "data/discovery-kb") -> dict[str, Any]:
    graph = FlowKnowledgeGraph(discovery_root=discovery_root)
    gate = ExecutionGate(graph)
    sme_ready = set(graph.flow_kb.index.get("sme_ready") or [])
    rows: list[FlowInventoryRow] = []

    for flow_id in sorted(graph.flow_kb.flows):
        meta = graph.flow_meta(flow_id)
        decision = gate.evaluate(flow_id)
        rows.append(
            FlowInventoryRow(
                flow_id=flow_id,
                name=str(meta.get("name") or flow_id),
                kb_status=str(meta.get("status") or "UNKNOWN"),
                sme_ready=flow_id in sme_ready,
                approval_status=decision.approval_status,
                executable=decision.executable,
                reason_code=decision.reason_code,
                message=decision.message,
                in_catalog=decision.catalog_automated,
            )
        )

    totals = {
        "total_flows": len(rows),
        "sme_ready": sum(1 for r in rows if r.sme_ready),
        "kb_ready": sum(1 for r in rows if r.kb_status == "READY"),
        "approved": sum(1 for r in rows if r.approval_status == "APPROVED"),
        "pending_approval": sum(1 for r in rows if r.approval_status == "PENDING_SME_APPROVAL"),
        "rejected": sum(1 for r in rows if r.approval_status == "REJECTED"),
        "executable": sum(1 for r in rows if r.executable),
        "blocked": sum(1 for r in rows if not r.executable),
        "draft": sum(1 for r in rows if r.kb_status == "DRAFT"),
        "superseded": sum(1 for r in rows if r.kb_status == "SUPERSEDED"),
    }
    return {
        "flows": [row.__dict__ for row in rows],
        "totals": totals,
    }


def select_validation_subset(
    inventory: dict[str, Any],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Select representative SME-ready flows covering auth, search, nav, logout, parameterized."""
    preferred = [
        ("BF-LOGIN-001", "authentication"),
        ("BF-PRODUCT-003", "parameterized_search"),
        ("BF-LOGOUT-002", "logout"),
        ("BF-HOME-010", "navigation"),
        ("BF-PRODUCT-004", "product_view"),
        ("BF-HOME-010-01", "item_search"),
        ("BF-PRODUCT-STOCK-VISIBILITY-009", "stock_visibility"),
        ("BF-BEST-DEAL-008", "promotions"),
    ]
    by_id = {row["flow_id"]: row for row in inventory.get("flows", [])}
    selected: list[dict[str, Any]] = []
    for flow_id, category in preferred[:limit]:
        row = by_id.get(flow_id)
        if not row:
            continue
        selected.append({**row, "category": category})
    return selected
