"""P9 — backend flow inventory with accurate ExecutionGate semantics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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


def list_duplicate_flow_ids_in_index(*, discovery_root: str | Path = "data/discovery-kb") -> list[str]:
    """Return flow IDs that appear more than once in index.yaml flows list or sme_ready."""
    index_path = Path(discovery_root) / "flows" / "index.yaml"
    if not index_path.exists():
        return []
    raw = index_path.read_text(encoding="utf-8")
    import re

    flow_ids: list[str] = []
    sme_ids: list[str] = []
    for line in raw.splitlines():
        hit = re.match(r"^\s+-\s+(BF-[A-Z0-9-]+)\s*$", line)
        if hit:
            sme_ids.append(hit.group(1))
        id_hit = re.match(r"^\s+-\s+id:\s*(BF-[A-Z0-9-]+)\s*$", line)
        if id_hit:
            flow_ids.append(id_hit.group(1))
    dupes: set[str] = set()
    for bucket in (flow_ids, sme_ids):
        seen: set[str] = set()
        for fid in bucket:
            if fid in seen:
                dupes.add(fid)
            seen.add(fid)
    return sorted(dupes)


def canonical_inventory_summary(inventory: dict[str, Any]) -> dict[str, int]:
    """Single canonical inventory block for P9 JSON/Markdown reports."""
    totals = inventory.get("totals") or {}
    flows = inventory.get("flows") or []
    stale = sum(1 for row in flows if row.get("reason_code") == "approval.stale")
    blocked = sum(1 for row in flows if not row.get("executable"))
    return {
        "total_flows": int(totals.get("total_flows", len(flows))),
        "sme_ready_flows": int(totals.get("sme_ready", 0)),
        "approved_flows": int(totals.get("approved", 0)),
        "executable_flows": int(totals.get("executable", 0)),
        "pending_approval_flows": int(totals.get("pending_approval", 0)),
        "rejected_flows": int(totals.get("rejected", 0)),
        "stale_flows": stale,
        "blocked_flows": blocked,
    }


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
        "stale": sum(1 for r in rows if r.reason_code == "approval.stale"),
        "draft": sum(1 for r in rows if r.kb_status == "DRAFT"),
        "superseded": sum(1 for r in rows if r.kb_status == "SUPERSEDED"),
    }
    payload = {
        "flows": [row.__dict__ for row in rows],
        "totals": totals,
    }
    payload["inventory_summary"] = canonical_inventory_summary(payload)
    return payload


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
