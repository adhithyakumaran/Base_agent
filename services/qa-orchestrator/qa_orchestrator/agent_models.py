"""P6 — controlled agent state, action, and journal models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from qa_orchestrator.models import (
    DiscoveryResult,
    ExecutionPlan,
    ExecutionResult,
    ExplorationResult,
    GenerationResult,
    HealingResult,
    IntentClassification,
    PlanningResult,
    SuiteSelectionPlan,
    ValidationResult,
)

AgentStatus = Literal[
    "PLANNING",
    "READY",
    "EXECUTING",
    "OBSERVING",
    "VERIFYING",
    "RECOVERING",
    "WAITING_FOR_APPROVAL",
    "COMPLETED",
    "FAILED",
    "BLOCKED",
    "NEEDS_REVIEW",
]

AgentActionType = Literal[
    "RUN_EXISTING_TEST",
    "EXPLORE",
    "CAPTURE_EVIDENCE",
    "VERIFY",
    "RECOVER_LOCATOR",
    "WAIT_FOR_REVIEW",
    "STOP",
]

AgentDecisionSource = Literal["RULE", "POLICY", "LLM", "SYSTEM"]

AgentFailureCategory = Literal[
    "PLANNING",
    "POLICY",
    "AUTHENTICATION",
    "LOCATOR",
    "TIMING",
    "NAVIGATION",
    "DATA",
    "APPLICATION",
    "INFRASTRUCTURE",
    "VERIFICATION",
    "UNKNOWN",
]

TerminalStatus = Literal["COMPLETED", "FAILED", "BLOCKED", "NEEDS_REVIEW", "WAITING_FOR_APPROVAL"]


class AgentAction(BaseModel):
    action_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    type: AgentActionType
    target: str = ""
    value: str = ""
    source: AgentDecisionSource = "RULE"
    confidence: float = 1.0
    requires_approval: bool = False
    reason: str = ""


class AgentDecisionEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    iteration: int = 0
    state: AgentStatus
    decision: AgentActionType | str
    action_id: str | None = None
    reason: str = ""
    source: AgentDecisionSource = "RULE"
    confidence: float = 1.0
    approved: bool = True
    result: str = ""
    resume_reason: str | None = None
    checkpoint: str | None = None
    previous_state: str | None = None
    new_state: str | None = None
    decision_source: AgentDecisionSource = "RULE"
    model: str | None = None
    model_version: str | None = None
    proposal: dict[str, Any] | None = None
    validation_result: str | None = None
    policy_result: str | None = None
    final_action: AgentActionType | str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    llm_invoked: bool = False
    llm_accepted: bool = False


class AgentFailureRecord(BaseModel):
    category: AgentFailureCategory = "UNKNOWN"
    message: str = ""
    evidence: list[str] = Field(default_factory=list)
    recovery_eligible: bool = False
    recovery_attempted: bool = False
    recovery_outcome: str = ""


class AgentRunState(BaseModel):
    run_id: str
    request: str
    run_type: str = "adhoc"
    status: AgentStatus = "PLANNING"
    iteration: int = 0
    step_count: int = 0
    recovery_count: int = 0
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    intent: IntentClassification | None = None
    plan: PlanningResult | None = None
    retrieval_used: bool = False
    suite_plan: SuiteSelectionPlan | None = None
    execution_plan: ExecutionPlan | None = None
    selected_flows: list[str] = Field(default_factory=list)
    current_flow: str | None = None
    current_test: str | None = None
    current_step: str | None = None
    current_action: AgentAction | None = None
    discovery: DiscoveryResult | None = None
    exploration: ExplorationResult | None = None
    generation_result: GenerationResult | None = None
    execution: ExecutionResult | None = None
    healing_result: HealingResult | None = None
    validation: ValidationResult | None = None
    evidence_paths: list[str] = Field(default_factory=list)
    recovery_history: list[AgentFailureRecord] = Field(default_factory=list)
    decision_journal: list[AgentDecisionEntry] = Field(default_factory=list)
    failure: AgentFailureRecord | None = None
    final_result: str | None = None
    reason_code: str | None = None
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentMetrics(BaseModel):
    planning_success_rate: float = 0.0
    terminal_state_accuracy: float = 0.0
    execution_attempt_rate: float = 0.0
    execution_attempt_success_rate: float = 0.0
    verification_success_rate: float = 0.0
    approval_routing_accuracy: float = 0.0
    recovery_attempt_rate: float = 0.0
    recovery_success_rate: float = 0.0
    recovery_failure_rate: float = 0.0
    false_recovery_rate: float = 0.0
    average_recoveries_per_failed_run: float = 0.0
    waiting_for_approval_rate: float = 0.0
    blocked_rate: float = 0.0
    needs_review_rate: float = 0.0
    average_iterations: float = 0.0
    average_recoveries: float = 0.0
    evidence_completeness: float = 0.0
    decision_trace_completeness: float = 0.0
    deterministic_decision_accuracy: float = 0.0
    llm_proposal_accuracy: float = 0.0
    policy_rejection_accuracy: float = 0.0
    final_action_accuracy: float = 0.0
    unsafe_proposal_rejection_rate: float = 0.0
    prompt_injection_rejection_rate: float = 0.0
    hallucinated_evidence_rejection_rate: float = 0.0
    low_confidence_escalation_accuracy: float = 0.0
    average_llm_calls_per_run: float = 0.0
    average_llm_latency_ms: float = 0.0
    # Deprecated aliases kept for backward-compatible payloads
    execution_success_rate: float = 0.0
    approval_escalation_rate: float = 0.0


class AgentRunResult(BaseModel):
    state: AgentRunState
    conclusion: str
    reason_code: str
    summary: str
    metrics: AgentMetrics = Field(default_factory=AgentMetrics)
    report_markdown: str = ""
    orchestrator_metadata: dict[str, Any] = Field(default_factory=dict)
