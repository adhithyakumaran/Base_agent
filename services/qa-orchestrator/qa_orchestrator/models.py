from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


StepAction = Literal["navigate", "click", "type", "wait", "screenshot", "assert_text", "custom"]

ExecutionMode = Literal[
    "morning_sanity",
    "regression_suite",
    "negative_suite",
    "adhoc_existing",
    "adhoc_parameterized",
    "incident_multi_flow",
    "new_feature",
    "discover",
]

PlanningStrategy = Literal["REUSE_EXISTING", "EXPLORE", "GENERATE", "ASK_USER", "BLOCK"]

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "BLOCKED"]

TestPolarity = Literal["positive", "negative", "mixed", "parameterized"]


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
    suite_topic: str | None = None
    flow_ids: list[str] = Field(default_factory=list)
    supporting_flow_ids: list[str] = Field(default_factory=list)
    suite_ids: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    reasoning: str = ""
    classifier: str = "deterministic"


class ExecutionGateSnapshot(BaseModel):
    flow_id: str
    executable: bool
    reason_code: str
    message: str
    approval_status: str | None = None
    kb_ready: bool = False
    in_sme_ready: bool = False
    catalog_automated: bool = False
    approval_stale: bool = False


class SuiteSelectionPlan(BaseModel):
    execution_mode: ExecutionMode = "adhoc_existing"
    suite_ids: list[str] = Field(default_factory=list)
    flow_ids: list[str] = Field(default_factory=list)
    blocked_flows: list[str] = Field(default_factory=list)
    execution_gates: list[ExecutionGateSnapshot] = Field(default_factory=list)
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


class FlowCoverageSnapshot(BaseModel):
    flow_id: str
    kb_status: str = "UNKNOWN"
    approval_status: str | None = None
    gate_executable: bool = False
    gate_reason_code: str = ""
    positive_tests: int = 0
    negative_tests: int = 0
    parameterized: bool = False
    sufficient: bool = False
    notes: list[str] = Field(default_factory=list)


class ExplorationRequest(BaseModel):
    """Contract consumed by ExplorationSession — planner does not browse."""

    target_url: str | None = None
    target_page: str | None = None
    goal: str
    known_flow_context: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(
        default_factory=lambda: ["navigate", "click", "type", "fill", "screenshot", "assert_text"]
    )
    max_depth: int = 2
    max_pages: int = 10
    evidence_required: list[str] = Field(default_factory=lambda: ["screenshot", "dom", "url"])
    read_only: bool = True
    timeout_s: float = 300.0


ExplorationStatus = Literal[
    "COMPLETED",
    "PARTIAL",
    "BLOCKED",
    "TIMEOUT",
    "FAILED",
    "INSUFFICIENT_EVIDENCE",
]


class LocatorCandidate(BaseModel):
    strategy: str
    expression: str
    rank: int
    playwright_code: str = ""


class DiscoveredElement(BaseModel):
    element_id: str
    role: str = ""
    name: str = ""
    text: str = ""
    tag: str = ""
    attributes: dict[str, str] = Field(default_factory=dict)
    locator_candidates: list[LocatorCandidate] = Field(default_factory=list)
    visible: bool = True
    enabled: bool = True
    interactive: bool = False


class ExplorationPage(BaseModel):
    page_id: str
    url: str
    title: str = ""
    depth: int = 0
    elements: list[DiscoveredElement] = Field(default_factory=list)
    forms: list[dict[str, Any]] = Field(default_factory=list)
    links: list[dict[str, str]] = Field(default_factory=list)
    navigation: list[str] = Field(default_factory=list)


class ExplorationActionRecord(BaseModel):
    action_id: str
    action_type: str
    target_element_id: str | None = None
    locator: str | None = None
    value: str | None = None
    ok: bool = True
    blocked: bool = False
    reason_code: str | None = None
    message: str = ""
    evidence_paths: list[str] = Field(default_factory=list)


class ExplorationEvidenceItem(BaseModel):
    exploration_id: str
    page_id: str
    action_id: str
    timestamp: str
    label: str
    screenshot_path: str | None = None
    dom_path: str | None = None
    url: str | None = None
    console_events: list[dict[str, Any]] = Field(default_factory=list)
    network_events: list[dict[str, Any]] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class DiscoveryCandidate(BaseModel):
    """Draft KB candidate — never mutates approved YAML flows."""

    candidate_id: str
    candidate_flow: str | None = None
    observed_page: str = ""
    elements: list[DiscoveredElement] = Field(default_factory=list)
    locators: list[LocatorCandidate] = Field(default_factory=list)
    actions: list[ExplorationActionRecord] = Field(default_factory=list)
    possible_business_behavior: list[str] = Field(default_factory=list)
    evidence: list[ExplorationEvidenceItem] = Field(default_factory=list)
    confidence: float = 0.0
    status: Literal["DRAFT"] = "DRAFT"


class ExplorationResult(BaseModel):
    request_id: str
    exploration_id: str
    status: ExplorationStatus
    target_url: str | None = None
    target_page: str | None = None
    goal: str
    pages: list[ExplorationPage] = Field(default_factory=list)
    elements: list[DiscoveredElement] = Field(default_factory=list)
    actions: list[ExplorationActionRecord] = Field(default_factory=list)
    navigation: list[dict[str, str]] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    locators: list[LocatorCandidate] = Field(default_factory=list)
    screenshots: list[str] = Field(default_factory=list)
    dom_snapshots: list[str] = Field(default_factory=list)
    console_events: list[dict[str, Any]] = Field(default_factory=list)
    network_events: list[dict[str, Any]] = Field(default_factory=list)
    business_signals: list[str] = Field(default_factory=list)
    discovered_flows: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: list[ExplorationEvidenceItem] = Field(default_factory=list)
    discovery_candidates: list[DiscoveryCandidate] = Field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    dry_run: bool = False
    message: str = ""


class GenerationRequest(BaseModel):
    """Contract for a future test generator — no Playwright code emitted here."""

    flow_context: list[str] = Field(default_factory=list)
    scenario_objective: str
    preconditions: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    expected_outcomes: list[str] = Field(default_factory=list)
    test_data_requirements: dict[str, Any] = Field(default_factory=dict)
    approval_required: bool = True


class PlanningResult(BaseModel):
    """Structured QA plan between intent classification and deterministic execution."""

    request: str
    intent: IntentClassification
    strategy: PlanningStrategy
    secondary_strategies: list[PlanningStrategy] = Field(default_factory=list)
    confidence: float = 0.0
    capabilities: list[str] = Field(default_factory=list)
    candidate_flows: list[str] = Field(default_factory=list)
    selected_flows: list[str] = Field(default_factory=list)
    blocked_flows: list[str] = Field(default_factory=list)
    execution_gates: list[ExecutionGateSnapshot] = Field(default_factory=list)
    existing_coverage: list[FlowCoverageSnapshot] = Field(default_factory=list)
    exploration_required: bool = False
    generation_required: bool = False
    exploration: ExplorationRequest | None = None
    generation: GenerationRequest | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    validated_parameters: dict[str, str] = Field(default_factory=dict)
    expected_evidence: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = "LOW"
    requires_human_approval: bool = False
    execution_allowed: bool = False
    polarity: TestPolarity = "positive"
    coverage_assessment: str = ""
    reasoning_summary: str = ""
    next_actions: list[str] = Field(default_factory=list)
    planner: str = "deterministic"


class OrchestratorResult(BaseModel):
    conclusion: str
    reason_code: str
    summary: str
    goal: str
    run_type: str = "adhoc"
    intent: IntentClassification
    planning: PlanningResult | None = None
    suite_plan: SuiteSelectionPlan
    discovery: DiscoveryResult | None = None
    exploration: ExplorationResult | None = None
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
