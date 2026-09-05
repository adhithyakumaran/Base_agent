from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


StepAction = Literal["navigate", "click", "type", "wait", "screenshot", "assert_text", "custom"]

ExecutionMode = Literal[
    "morning_sanity",
    "adhoc_existing",
    "adhoc_parameterized",
    "incident_multi_flow",
    "new_feature",
    "discover",
]


class PlanStep(BaseModel):
    action: StepAction
    target: str = ""
    value: str = ""
    note: str = ""
    kb_ref: str | None = None


class ExecutionPlan(BaseModel):
    goal: str
    run_type: str = "adhoc"
    summary: str = ""
    steps: list[PlanStep] = Field(default_factory=list)
    kb_refs: list[str] = Field(default_factory=list)
    planner: str = "deterministic"


class IntentClassification(BaseModel):
    goal: str
    run_type: str = "adhoc"
    execution_mode: ExecutionMode = "adhoc_existing"
    capability: str | None = None
    flow_ids: list[str] = Field(default_factory=list)
    supporting_flow_ids: list[str] = Field(default_factory=list)
    suite_ids: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    reasoning: str = ""
    classifier: str = "deterministic"


class SuiteSelectionPlan(BaseModel):
    execution_mode: ExecutionMode = "adhoc_existing"
    suite_ids: list[str] = Field(default_factory=list)
    flow_ids: list[str] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    runner: str = "playwright"
    primary_only: bool = True
    notes: list[str] = Field(default_factory=list)


class DiscoveryResult(BaseModel):
    ok: bool = False
    mode: str = "dry_run"
    pages_crawled: int = 0
    seed_url: str | None = None
    suggestions: list[str] = Field(default_factory=list)
    report: dict[str, Any] = Field(default_factory=dict)


class StepObservation(BaseModel):
    step_index: int
    action: str
    ok: bool
    message: str = ""
    screenshot_path: str | None = None
    url: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    ok: bool
    mode: str
    observations: list[StepObservation] = Field(default_factory=list)
    error: str | None = None
    elapsed_ms: int = 0


class ValidationFinding(BaseModel):
    code: str
    severity: Literal["info", "warn", "error"]
    message: str


class ValidationResult(BaseModel):
    phase: Literal["A", "B"]
    conclusion: str
    reason_code: str
    summary: str
    findings: list[ValidationFinding] = Field(default_factory=list)
    gt_refs: list[str] = Field(default_factory=list)


class OrchestratorResult(BaseModel):
    conclusion: str
    reason_code: str
    summary: str
    goal: str
    run_type: str = "adhoc"
    intent: IntentClassification
    suite_plan: SuiteSelectionPlan
    discovery: DiscoveryResult | None = None
    plan: ExecutionPlan
    execution: ExecutionResult
    validation: ValidationResult
    report_markdown: str = ""
    tool_calls: int = 0
    llm_calls: int = 0
    steps: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    kb_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
