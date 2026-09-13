"""Unified execution gating — artifact approval + KB sme_ready + safety checks."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph

CANONICAL_ARTIFACT = "test-cases.yaml"
APPROVAL_STATUSES = frozenset({"PENDING_SME_APPROVAL", "APPROVED", "REJECTED"})


@dataclass(frozen=True)
class ExecutionGateDecision:
    flow_id: str
    executable: bool
    reason_code: str
    message: str
    approval_status: str | None = None
    kb_ready: bool = False
    in_sme_ready: bool = False
    catalog_automated: bool = False
    approval_stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutionGate:
    """Single source of truth for whether a flow may be executed.

    Canonical rule:
      executable =
        artifact test-cases.yaml status is APPROVED
        AND approval is not stale
        AND flow is in KB sme_ready list
        AND KB status/catalog safety checks pass (existing _is_primary semantics)
    """

    def __init__(self, graph: FlowKnowledgeGraph) -> None:
        self.graph = graph
        self.design_root = graph.automation_dir / "test-design" / "flows"
        self.log_path = graph.automation_dir / "approval" / "approval-log.json"

    def evaluate(self, flow_id: str) -> ExecutionGateDecision:
        meta = self.graph.flow_meta(flow_id)
        in_sme_ready = flow_id in set(self.graph.flow_kb.index.get("sme_ready", []))
        catalog_automated = self.graph.is_automated(flow_id)
        kb_ready, kb_reason = self._kb_readiness(flow_id, meta, in_sme_ready, catalog_automated)

        status = self._read_artifact_status(flow_id)
        artifact_path = self.design_root / flow_id / CANONICAL_ARTIFACT

        if status is None:
            return ExecutionGateDecision(
                flow_id=flow_id,
                executable=False,
                reason_code="approval.missing",
                message=f"{flow_id}: missing {CANONICAL_ARTIFACT} approval status",
                approval_status=None,
                kb_ready=kb_ready,
                in_sme_ready=in_sme_ready,
                catalog_automated=catalog_automated,
            )

        if status == "PENDING_SME_APPROVAL":
            return ExecutionGateDecision(
                flow_id=flow_id,
                executable=False,
                reason_code="approval.pending",
                message=f"{flow_id}: artifact approval is PENDING_SME_APPROVAL",
                approval_status=status,
                kb_ready=kb_ready,
                in_sme_ready=in_sme_ready,
                catalog_automated=catalog_automated,
            )

        if status == "REJECTED":
            return ExecutionGateDecision(
                flow_id=flow_id,
                executable=False,
                reason_code="approval.rejected",
                message=f"{flow_id}: artifact approval is REJECTED",
                approval_status=status,
                kb_ready=kb_ready,
                in_sme_ready=in_sme_ready,
                catalog_automated=catalog_automated,
            )

        stale = status == "APPROVED" and self._approval_is_stale(flow_id, artifact_path)
        if stale:
            return ExecutionGateDecision(
                flow_id=flow_id,
                executable=False,
                reason_code="approval.stale",
                message=(
                    f"{flow_id}: APPROVED artifact changed after last SME sign-off — re-approval required"
                ),
                approval_status=status,
                kb_ready=kb_ready,
                in_sme_ready=in_sme_ready,
                catalog_automated=catalog_automated,
                approval_stale=True,
            )

        if not in_sme_ready:
            return ExecutionGateDecision(
                flow_id=flow_id,
                executable=False,
                reason_code="kb.not_sme_ready",
                message=f"{flow_id}: not in KB sme_ready list",
                approval_status=status,
                kb_ready=False,
                in_sme_ready=False,
                catalog_automated=catalog_automated,
            )

        if not kb_ready:
            return ExecutionGateDecision(
                flow_id=flow_id,
                executable=False,
                reason_code=kb_reason,
                message=f"{flow_id}: KB readiness failed ({kb_reason})",
                approval_status=status,
                kb_ready=False,
                in_sme_ready=in_sme_ready,
                catalog_automated=catalog_automated,
            )

        return ExecutionGateDecision(
            flow_id=flow_id,
            executable=True,
            reason_code="gate.executable",
            message=f"{flow_id}: APPROVED artifact + sme_ready + KB safety checks satisfied",
            approval_status=status,
            kb_ready=True,
            in_sme_ready=True,
            catalog_automated=catalog_automated,
        )

    def filter_executable(self, flow_ids: list[str]) -> tuple[list[str], list[ExecutionGateDecision]]:
        allowed: list[str] = []
        decisions: list[ExecutionGateDecision] = []
        for fid in flow_ids:
            decision = self.evaluate(fid)
            decisions.append(decision)
            if decision.executable:
                allowed.append(fid)
        return allowed, decisions

    def _kb_readiness(
        self,
        flow_id: str,
        meta: dict[str, Any] | None,
        in_sme_ready: bool,
        catalog_automated: bool,
    ) -> tuple[bool, str]:
        if not meta:
            return False, "kb.missing_flow"
        if not in_sme_ready:
            return False, "kb.not_sme_ready"
        if meta.get("status") in self.graph.PRIMARY_STATUSES:
            if not catalog_automated:
                return False, "kb.not_in_catalog"
            return True, "kb.ready"
        if in_sme_ready:
            return True, "kb.sme_ready_only"
        return False, "kb.not_ready_status"

    def _read_artifact_status(self, flow_id: str) -> str | None:
        path = self.design_root / flow_id / CANONICAL_ARTIFACT
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
        match = re.search(
            r"^status:\s*(PENDING_SME_APPROVAL|APPROVED|REJECTED)\s*$",
            raw,
            re.MULTILINE,
        )
        if not match:
            return None
        return match.group(1)

    def _load_approval_log(self) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        try:
            data = json.loads(self.log_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        records = data.get("records") if isinstance(data, dict) else None
        return list(records) if isinstance(records, list) else []

    def _approval_is_stale(self, flow_id: str, artifact_path: Path) -> bool:
        if not artifact_path.exists():
            return False
        approved_records = [
            r
            for r in self._load_approval_log()
            if r.get("flowId") == flow_id
            and r.get("artifact") == CANONICAL_ARTIFACT
            and r.get("status") == "APPROVED"
        ]
        if not approved_records:
            return True
        latest = max(approved_records, key=lambda r: str(r.get("decidedAt") or ""))
        decided_at = str(latest.get("decidedAt") or "")
        if not decided_at:
            return True
        try:
            decided_ts = datetime.fromisoformat(decided_at.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return True
        artifact_mtime = artifact_path.stat().st_mtime
        return artifact_mtime > decided_ts + 1.0

    @staticmethod
    def is_valid_transition(current: str, new: str) -> bool:
        if current == new:
            return False
        if current == "PENDING_SME_APPROVAL" and new in {"APPROVED", "REJECTED"}:
            return True
        if current == "REJECTED" and new == "PENDING_SME_APPROVAL":
            return True
        return False
