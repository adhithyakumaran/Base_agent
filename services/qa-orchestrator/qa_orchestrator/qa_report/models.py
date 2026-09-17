"""Canonical QA report schema — authoritative, reproducible."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

REPORT_SCHEMA_VERSION = "qa-report-v1"

OverallResult = Literal["PASS", "FAIL", "NEEDS_REVIEW", "BLOCKED", "WAITING_FOR_APPROVAL", "UNKNOWN"]


class ReportPlanning(BaseModel):
    intent_execution_mode: str | None = None
    intent_capability: str | None = None
    selected_flows: list[str] = Field(default_factory=list)
    planner_strategy: str | None = None
    reason: str | None = None
    blocked_flows: list[str] = Field(default_factory=list)


class ReportExecution(BaseModel):
    execution_result: str | None = None
    command: str | None = None
    browser: str | None = None
    pages: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    execution_mode: str | None = None
    runner: str | None = None
    exit_code: int | None = None
    errors: list[str] = Field(default_factory=list)
    elapsed_ms: int | None = None


class EvidenceItem(BaseModel):
    evidence_id: str
    timestamp: str | None = None
    action: str | None = None
    description: str | None = None
    source: str | None = None
    path: str
    url: str | None = None
    related_step: str | None = None


class ReportEvidence(BaseModel):
    screenshots: list[EvidenceItem] = Field(default_factory=list)
    traces: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)


class ReportValidation(BaseModel):
    phase: str | None = None
    execution_gate_summary: list[str] = Field(default_factory=list)
    parameter_validation: dict[str, Any] = Field(default_factory=dict)
    ground_truth: dict[str, Any] = Field(default_factory=dict)
    assertions: list[str] = Field(default_factory=list)
    validation_result: str | None = None
    reason_code: str | None = None
    failed_checks: list[str] = Field(default_factory=list)
    decision_diagnostics: dict[str, Any] = Field(default_factory=dict)
    needs_review_detail: dict[str, str] = Field(default_factory=dict)


class ReportApprovals(BaseModel):
    flow_approval: list[str] = Field(default_factory=list)
    run_level_approval: str | None = None
    approver: str | None = None
    approval_timestamps: list[str] = Field(default_factory=list)
    approval_source: str | None = None
    resume_events: list[str] = Field(default_factory=list)


class ReportRecovery(BaseModel):
    healing_attempts: int = 0
    retries: int = 0
    recovery_result: str | None = None


class ReportTimelineEntry(BaseModel):
    timestamp: str
    stage: str
    action: str
    result: str
    evidence_ref: str | None = None


class ReportFinalResult(BaseModel):
    conclusion: OverallResult
    reason_code: str | None = None
    explanation: str


class OptionalLlmSummary(BaseModel):
    label: str = "Generated Analysis (non-authoritative)"
    text: str = ""
    enabled: bool = False


class QAReport(BaseModel):
    report_schema_version: str = REPORT_SCHEMA_VERSION
    report_id: str
    run_id: str
    generated_at: str
    application: str = "Oracle APEX Endless Aisle"
    environment: str = "UAT"
    flow_ids: list[str] = Field(default_factory=list)
    test_case_ids: list[str] = Field(default_factory=list)
    goal: str
    input_parameters: dict[str, Any] = Field(default_factory=dict)
    execution_mode: str | None = None
    runner: str | None = None
    agent_mode: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    duration_ms: int | None = None
    overall_result: OverallResult = "UNKNOWN"
    planning: ReportPlanning = Field(default_factory=ReportPlanning)
    execution: ReportExecution = Field(default_factory=ReportExecution)
    evidence: ReportEvidence = Field(default_factory=ReportEvidence)
    validation: ReportValidation = Field(default_factory=ReportValidation)
    approvals: ReportApprovals = Field(default_factory=ReportApprovals)
    recovery: ReportRecovery = Field(default_factory=ReportRecovery)
    timeline: list[ReportTimelineEntry] = Field(default_factory=list)
    executive_summary: str = ""
    final_result: ReportFinalResult | None = None
    optional_llm_summary: OptionalLlmSummary = Field(default_factory=OptionalLlmSummary)
    allure_note: str = (
        "Allure may be used for Playwright technical attachments; ScoutAI ExecutionGate, "
        "Ground Truth, Validator, and approval model remain authoritative for business result."
    )
