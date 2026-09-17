"""Build QAReport from console run JSON and agent snapshot."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from qa_orchestrator.qa_report.models import (
    EvidenceItem,
    QAReport,
    ReportApprovals,
    ReportEvidence,
    ReportExecution,
    ReportPlanning,
    ReportRecovery,
    ReportTimelineEntry,
    ReportValidation,
    OverallResult,
)
from qa_orchestrator.qa_report.redaction import redact_dict
from qa_orchestrator.qa_report.summary import (
    build_executive_summary,
    build_final_result,
    needs_review_detail_from_diagnostics,
)
from qa_orchestrator.playwright_runner import classify_playwright_output


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_snapshot(journal_dir: Path, run_id: str) -> dict[str, Any] | None:
    path = journal_dir / run_id / "state.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _load_journal(journal_dir: Path, run_id: str) -> dict[str, Any] | None:
    path = journal_dir / run_id / "journal.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _normalize_conclusion(raw: str | None) -> OverallResult:
    if not raw:
        return "UNKNOWN"
    upper = raw.upper().replace(" ", "_")
    for candidate in ("PASS", "FAIL", "NEEDS_REVIEW", "BLOCKED", "WAITING_FOR_APPROVAL"):
        if candidate in upper or upper == candidate:
            return candidate  # type: ignore[return-value]
    if upper in {"COMPLETED"}:
        return "PASS"
    if upper in {"FAILED"}:
        return "FAIL"
    return "UNKNOWN"


def _collect_evidence_from_local(local: dict, run_id: str, repo_root: Path) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    execution = local.get("execution") or {}
    idx = 0
    for obs in execution.get("observations") or []:
        meta = obs.get("meta") or {}
        for entry in meta.get("evidence") or []:
            idx += 1
            path = str(entry.get("path") or "")
            items.append(
                EvidenceItem(
                    evidence_id=f"EV-{idx:03d}",
                    timestamp=None,
                    action=str(obs.get("action") or ""),
                    description=str(entry.get("label") or f"capture-{idx}"),
                    source="playwright",
                    path=path,
                    url=(entry.get("meta") or {}).get("url") if isinstance(entry.get("meta"), dict) else entry.get("url"),
                    related_step=str(obs.get("step_index", "")),
                )
            )
        if obs.get("screenshot_path"):
            idx += 1
            items.append(
                EvidenceItem(
                    evidence_id=f"EV-{idx:03d}",
                    action=str(obs.get("action") or ""),
                    description=obs.get("message"),
                    source="playwright",
                    path=str(obs["screenshot_path"]),
                    url=obs.get("url"),
                )
            )
    evidence_root = repo_root / "reports" / "evidence" / run_id
    if evidence_root.is_dir():
        for png in sorted(evidence_root.rglob("*.png"))[:40]:
            idx += 1
            rel = str(png.relative_to(repo_root))
            if any(e.path == rel for e in items):
                continue
            items.append(
                EvidenceItem(
                    evidence_id=f"EV-{idx:03d}",
                    description=png.parent.name,
                    source="filesystem",
                    path=rel,
                )
            )
    return items


def _timeline_from_run(console_run: dict, snapshot: dict | None) -> list[ReportTimelineEntry]:
    entries: list[ReportTimelineEntry] = []
    for tr in console_run.get("traces") or []:
        entries.append(
            ReportTimelineEntry(
                timestamp=str(tr.get("at") or ""),
                stage=str(tr.get("kind") or "info"),
                action=str(tr.get("message") or "")[:120],
                result="logged",
            )
        )
    state = (snapshot or {}).get("state") or {}
    for row in state.get("decision_journal") or []:
        entries.append(
            ReportTimelineEntry(
                timestamp=str(row.get("timestamp") or ""),
                stage=str(row.get("state") or ""),
                action=str(row.get("decision") or ""),
                result=str(row.get("result") or row.get("reason") or ""),
            )
        )
    return entries[:80]


def build_qa_report(
    *,
    run_id: str,
    console_run: dict[str, Any] | None = None,
    journal_dir: str | Path = "reports/agent",
    repo_root: str | Path = ".",
    environment: str | None = None,
) -> QAReport:
    console_run = console_run or {}
    repo_root = Path(repo_root)
    journal_dir = Path(journal_dir)
    snapshot = _load_snapshot(journal_dir, run_id)

    snapshot_state = (snapshot.get("state") or {}) if snapshot else {}

    agent_payload = ((console_run.get("report") or {}).get("json") or {}).get("agent") or {}
    local = agent_payload.get("local") or {}
    if not local and snapshot_state:
        local = {
            "intent": snapshot_state.get("intent"),
            "planning": snapshot_state.get("plan"),
            "suite_plan": snapshot_state.get("suite_plan"),
            "execution": snapshot_state.get("execution"),
            "validation": snapshot_state.get("validation"),
            "executor": (snapshot_state.get("metadata") or {}).get("executor"),
        }

    intent = local.get("intent") or {}
    planning_raw = local.get("planning") or snapshot_state.get("plan") or {}
    suite = local.get("suite_plan") or snapshot_state.get("suite_plan") or {}
    execution = local.get("execution") or snapshot_state.get("execution") or {}
    validation = local.get("validation") or snapshot_state.get("validation") or {}

    flow_ids = list(suite.get("flow_ids") or intent.get("flow_ids") or [])
    if not flow_ids:
        flow_ids = list(snapshot_state.get("selected_flows") or [])[:8]

    diagnostics = console_run.get("decisionDiagnostics") or {}
    if not diagnostics:
        diagnostics = snapshot_state.get("decision_diagnostics") or {}
        if not diagnostics:
            diagnostics = (snapshot_state.get("metadata") or {}).get("decision_diagnostics") or {}

    conclusion = _normalize_conclusion(console_run.get("conclusion") or snapshot_state.get("final_result"))
    if conclusion == "UNKNOWN" and validation:
        conclusion = _normalize_conclusion(validation.get("conclusion"))

    gates = suite.get("execution_gates") or []
    gate_lines = [
        f"{g.get('flow_id')}: executable={g.get('executable')} reason={g.get('reason_code')}"
        for g in gates[:12]
    ]

    commands = suite.get("commands") or []
    command = commands[0] if commands else None
    obs_actions = [str(o.get("action")) for o in execution.get("observations") or []]
    errors = [execution.get("error")] if execution.get("error") else []
    for o in execution.get("observations") or []:
        if not o.get("ok") and o.get("message"):
            errors.append(str(o.get("message")))

    exit_code = 0 if execution.get("ok") else 1

    playwright_meta: dict[str, Any] = {}
    for obs in execution.get("observations") or []:
        if isinstance(obs.get("meta"), dict):
            playwright_meta = obs["meta"]
    exec_status = playwright_meta.get("execution_status")
    infra_warnings = list(playwright_meta.get("infrastructure_warnings") or [])
    combined_tail = (playwright_meta.get("stdout_tail") or "") + (playwright_meta.get("stderr_tail") or "")
    if not exec_status and combined_tail:
        exec_status, inferred = classify_playwright_output(
            playwright_meta.get("stdout_tail") or "",
            playwright_meta.get("stderr_tail") or "",
            exit_code,
        )
        for w in inferred:
            if w not in infra_warnings:
                infra_warnings.append(w)

    validation_block = ReportValidation(
        phase=validation.get("phase"),
        execution_gate_summary=gate_lines,
        parameter_validation={"params": redact_dict(suite.get("params") or intent.get("params") or {})},
        ground_truth={
            "approved_available": diagnostics.get("ground_truth", {}).get("approved_available")
            if isinstance(diagnostics.get("ground_truth"), dict)
            else None,
        },
        validation_result=validation.get("conclusion"),
        reason_code=validation.get("reason_code") or console_run.get("reasonCode"),
        failed_checks=list(diagnostics.get("failed_checks") or []) if isinstance(diagnostics, dict) else [],
        decision_diagnostics=redact_dict(diagnostics) if isinstance(diagnostics, dict) else {},
        needs_review_detail=needs_review_detail_from_diagnostics(diagnostics if isinstance(diagnostics, dict) else {}),
    )

    report = QAReport(
        report_id=f"qrpt-{run_id}",
        run_id=run_id,
        generated_at=_utc_now(),
        environment=environment or __import__("os").environ.get("QA_ENV", "UAT"),
        flow_ids=flow_ids,
        goal=str(console_run.get("goal") or snapshot_state.get("request") or run_id),
        input_parameters=redact_dict(dict(suite.get("params") or intent.get("params") or {})),
        execution_mode=str(console_run.get("executionMode") or local.get("execution_mode") or intent.get("execution_mode") or ""),
        runner=str(suite.get("runner") or local.get("executor") or execution.get("mode") or ""),
        agent_mode=str(local.get("classifier") or intent.get("classifier") or ""),
        start_time=str(console_run.get("createdAt") or snapshot_state.get("started_at") or ""),
        end_time=str(console_run.get("updatedAt") or snapshot_state.get("updated_at") or ""),
        overall_result=conclusion,
        business_validation_status=conclusion,
        planning=ReportPlanning(
            intent_execution_mode=intent.get("execution_mode"),
            intent_capability=intent.get("capability"),
            selected_flows=list(planning_raw.get("selected_flows") or flow_ids),
            planner_strategy=planning_raw.get("strategy"),
            reason=planning_raw.get("reasoning_summary") or intent.get("reasoning"),
            blocked_flows=list(planning_raw.get("blocked_flows") or suite.get("blocked_flows") or []),
        ),
        execution=ReportExecution(
            execution_result=str(execution.get("mode") or ""),
            command=command,
            browser=str(console_run.get("executionMode") or ""),
            actions=obs_actions,
            execution_mode=str(console_run.get("executionMode") or execution.get("mode") or ""),
            runner=str(suite.get("runner") or execution.get("mode") or ""),
            exit_code=exit_code,
            errors=[e for e in errors if e],
            elapsed_ms=execution.get("elapsed_ms"),
            execution_status=str(exec_status) if exec_status else None,
            infrastructure_warnings=infra_warnings,
        ),
        evidence=ReportEvidence(screenshots=_collect_evidence_from_local(local, run_id, repo_root)),
        validation=validation_block,
        approvals=ReportApprovals(
            flow_approval=gate_lines,
            run_level_approval=str(snapshot.get("approval_reason") if snapshot else console_run.get("approvalReason") or ""),
            approval_source=str(snapshot.get("approval_pause_kind") if snapshot else console_run.get("approvalPauseKind") or ""),
        ),
        recovery=ReportRecovery(
            healing_attempts=int(snapshot_state.get("recovery_count") or 0),
            retries=int(snapshot_state.get("iteration") or 0),
        ),
        timeline=_timeline_from_run(console_run, snapshot),
    )
    report.executive_summary = build_executive_summary(report)
    report.final_result = build_final_result(report)
    return report
