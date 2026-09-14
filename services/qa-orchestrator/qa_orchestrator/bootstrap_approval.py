"""Bootstrap SME-ready flow approvals for controlled QA/demo environments only."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qa_orchestrator.execution_gate import CANONICAL_ARTIFACT, ExecutionGate
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph

BOOTSTRAP_REASON = "Initial approved baseline for controlled QA environment"
BOOTSTRAP_SOURCE = "BOOTSTRAP"


@dataclass
class BootstrapApprovalResult:
    flow_id: str
    outcome: str
    message: str = ""
    executable: bool = False
    reason_code: str = ""


@dataclass
class BootstrapApprovalSummary:
    approved: list[str] = field(default_factory=list)
    already_approved: list[str] = field(default_factory=list)
    blocked: list[BootstrapApprovalResult] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)
    gate_rows: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "already_approved": self.already_approved,
            "blocked": [r.__dict__ for r in self.blocked],
            "rejected": self.rejected,
            "stale": self.stale,
            "gate_rows": self.gate_rows,
            "counts": {
                "approved_baseline_flows": len(self.approved),
                "already_approved": len(self.already_approved),
                "blocked": len(self.blocked),
                "rejected": len(self.rejected),
                "stale": len(self.stale),
                "executable_after": sum(1 for r in self.gate_rows if r.get("executable")),
            },
        }


def bootstrap_approvals_enabled() -> bool:
    return os.environ.get("QA_BOOTSTRAP_APPROVALS", "false").strip().lower() in {"1", "true", "yes"}


def _bootstrap_actor() -> str:
    return os.environ.get("QA_BOOTSTRAP_ACTOR", "bootstrap-system").strip() or "bootstrap-system"


def _read_artifact_status(path: Path) -> str | None:
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    match = re.search(
        r"^status:\s*(PENDING_SME_APPROVAL|APPROVED|REJECTED)\s*$",
        raw,
        re.MULTILINE,
    )
    return match.group(1) if match else None


def _write_artifact_status(path: Path, status: str) -> None:
    raw = path.read_text(encoding="utf-8")
    if not re.search(r"^status:\s*(PENDING_SME_APPROVAL|APPROVED|REJECTED)\s*$", raw, re.MULTILINE):
        raise ValueError(f"{path}: missing status field")
    updated = re.sub(
        r"^status:\s*(PENDING_SME_APPROVAL|APPROVED|REJECTED)\s*$",
        f"status: {status}",
        raw,
        count=1,
        flags=re.MULTILINE,
    )
    path.write_text(updated, encoding="utf-8")


def _append_approval_record(
    log_path: Path,
    *,
    flow_id: str,
    status: str,
    actor: str,
    decided_at: str,
) -> None:
    records: list[dict[str, Any]] = []
    if log_path.exists():
        try:
            data = json.loads(log_path.read_text(encoding="utf-8"))
            records = list(data.get("records") or [])
        except json.JSONDecodeError:
            records = []
    records.append(
        {
            "flowId": flow_id,
            "artifact": CANONICAL_ARTIFACT,
            "status": status,
            "approver": actor,
            "decidedAt": decided_at,
            "source": BOOTSTRAP_SOURCE,
            "reason": BOOTSTRAP_REASON,
        }
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps({"records": records}, indent=2), encoding="utf-8")


def _validate_bootstrap_candidate(
    graph: FlowKnowledgeGraph,
    gate: ExecutionGate,
    flow_id: str,
) -> BootstrapApprovalResult | None:
    sme_ready = set(graph.flow_kb.index.get("sme_ready") or [])
    if flow_id not in sme_ready:
        return BootstrapApprovalResult(flow_id, "blocked", "not in sme_ready list")
    if not graph.is_automated(flow_id):
        return BootstrapApprovalResult(flow_id, "blocked", "not in automation catalog")
    artifact = gate.design_root / flow_id / CANONICAL_ARTIFACT
    if not artifact.exists():
        return BootstrapApprovalResult(flow_id, "blocked", "missing test-cases.yaml")
    status = _read_artifact_status(artifact)
    if status is None:
        return BootstrapApprovalResult(flow_id, "blocked", "malformed test-cases.yaml status")
    if status == "REJECTED":
        return BootstrapApprovalResult(flow_id, "rejected", "artifact is REJECTED")

    decision = gate.evaluate(flow_id)
    if status == "APPROVED" and decision.executable:
        return None  # already approved + executable
    if status == "APPROVED":
        if decision.reason_code == "approval.stale":
            return BootstrapApprovalResult(flow_id, "stale_refresh", decision.message, reason_code=decision.reason_code)
        if not decision.executable:
            return BootstrapApprovalResult(
                flow_id,
                "blocked",
                decision.message,
                reason_code=decision.reason_code,
            )
        return None  # already approved + executable
    if status == "PENDING_SME_APPROVAL":
        meta = graph.flow_meta(flow_id)
        if not meta:
            return BootstrapApprovalResult(flow_id, "blocked", "missing KB flow metadata")
        return None
    return BootstrapApprovalResult(flow_id, "blocked", f"unexpected status {status}")


def bootstrap_approve_sme_ready_flows(
    *,
    discovery_root: str = "data/discovery-kb",
    automation_dir: str | None = None,
    enabled: bool | None = None,
) -> BootstrapApprovalSummary:
    if enabled is None:
        enabled = bootstrap_approvals_enabled()
    if not enabled:
        raise RuntimeError("QA_BOOTSTRAP_APPROVALS is disabled (set QA_BOOTSTRAP_APPROVALS=true to run)")

    graph = FlowKnowledgeGraph(discovery_root=discovery_root, automation_dir=automation_dir)
    gate = ExecutionGate(graph)
    sme_ready = list(dict.fromkeys(graph.flow_kb.index.get("sme_ready") or []))
    summary = BootstrapApprovalSummary()
    actor = _bootstrap_actor()
    log_path = gate.log_path

    for flow_id in sorted(sme_ready):
        check = _validate_bootstrap_candidate(graph, gate, flow_id)
        artifact = gate.design_root / flow_id / CANONICAL_ARTIFACT
        status = _read_artifact_status(artifact)
        if check is None and status == "APPROVED":
            post = gate.evaluate(flow_id)
            if post.executable:
                summary.already_approved.append(flow_id)
                continue
        if check is not None:
            if check.outcome == "rejected":
                summary.rejected.append(flow_id)
                continue
            if check.outcome == "stale_refresh":
                decided_at = datetime.now(timezone.utc).isoformat()
                _append_approval_record(
                    log_path,
                    flow_id=flow_id,
                    status="APPROVED",
                    actor=actor,
                    decided_at=decided_at,
                )
                post = gate.evaluate(flow_id)
                if post.executable:
                    summary.approved.append(flow_id)
                else:
                    summary.stale.append(flow_id)
                    summary.blocked.append(
                        BootstrapApprovalResult(
                            flow_id,
                            "blocked",
                            post.message,
                            reason_code=post.reason_code,
                        )
                    )
                continue
            if check.outcome == "stale":
                summary.stale.append(flow_id)
            else:
                summary.blocked.append(check)
            continue

        if not ExecutionGate.is_valid_transition("PENDING_SME_APPROVAL", "APPROVED"):
            summary.blocked.append(
                BootstrapApprovalResult(flow_id, "blocked", "invalid approval transition")
            )
            continue

        _write_artifact_status(artifact, "APPROVED")
        time.sleep(0.05)
        decided_at = datetime.now(timezone.utc).isoformat()
        _append_approval_record(
            log_path,
            flow_id=flow_id,
            status="APPROVED",
            actor=actor,
            decided_at=decided_at,
        )
        post = gate.evaluate(flow_id)
        if not post.executable:
            summary.blocked.append(
                BootstrapApprovalResult(
                    flow_id,
                    "blocked",
                    post.message,
                    executable=False,
                    reason_code=post.reason_code,
                )
            )
            continue
        summary.approved.append(flow_id)

    for flow_id in sorted(sme_ready):
        decision = gate.evaluate(flow_id)
        summary.gate_rows.append(
            {
                "flow_id": flow_id,
                "executable": decision.executable,
                "reason_code": decision.reason_code,
            }
        )

    return summary


def format_gate_evaluation_table(summary: BootstrapApprovalSummary) -> str:
    lines = ["Flow ID             Executable", "------------------- ----------"]
    yes = 0
    for row in summary.gate_rows:
        flag = "YES" if row["executable"] else "NO"
        if row["executable"]:
            yes += 1
        lines.append(f"{row['flow_id']:<19} {flag}")
    lines.append(f"{yes}/{len(summary.gate_rows)} executable")
    return "\n".join(lines)
