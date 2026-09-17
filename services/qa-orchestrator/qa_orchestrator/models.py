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
    decision_diagnostics: dict[str, Any] | None = None


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
    """Contract consumed by the test generation pipeline."""

    flow_context: list[str] = Field(default_factory=list)
    scenario_objective: str
    preconditions: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    expected_outcomes: list[str] = Field(default_factory=list)
    test_data_requirements: dict[str, Any] = Field(default_factory=dict)
    approval_required: bool = True


ArtifactStatus = Literal["DRAFT", "PENDING_SME_APPROVAL", "APPROVED", "REJECTED"]
GenerationOutcomeStatus = Literal[
    "GENERATED",
    "INVALID",
    "VALIDATION_FAILED",
    "BLOCKED",
    "NEEDS_REVIEW",
    "READY_FOR_APPROVAL",
]
LocatorSource = Literal["OBSERVED", "GENERATED", "FALLBACK"]
AssertionQuality = Literal["STRONG", "MODERATE", "WEAK", "MISSING"]
AssertionSource = Literal["USER_REQUIREMENT", "GROUND_TRUTH", "EXISTING_TEST", "EXPLORATION"]


class GeneratedLocator(BaseModel):
    primary: str
    fallbacks: list[str] = Field(default_factory=list)
    source: LocatorSource = "OBSERVED"
    confidence: float = 0.0
    playwright_code: str = ""


class GeneratedAction(BaseModel):
    type: Literal["navigate", "fill", "click", "assert", "wait", "page_object"]
    locator: GeneratedLocator | None = None
    page_object: str | None = None
    page_object_method: str | None = None
    value_source: str | None = None
    value: str | None = None
    expectation: str | None = None
    evidence_required: bool = True
    assertion_quality: AssertionQuality | None = None
    assertion_source: AssertionSource | None = None
    assertion_text: str | None = None
    evidence_source: str | None = None
    locator_verified: bool | None = None


class TestCaseStep(BaseModel):
    step_id: str
    action: str
    target: str = ""
    input: str | None = None
    expected: str = ""
    evidence_required: bool = True
    generated_action: GeneratedAction | None = None


class TestScenario(BaseModel):
    scenario_id: str
    flow_id: str
    title: str
    objective: str
    preconditions: list[str] = Field(default_factory=list)
    test_data: dict[str, str] = Field(default_factory=dict)
    actions: list[str] = Field(default_factory=list)
    expected_outcomes: list[str] = Field(default_factory=list)
    polarity: TestPolarity = "positive"
    source: Literal["DISCOVERY", "USER_REQUEST", "EXISTING_FLOW", "RECORDER"] = "DISCOVERY"
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    status: ArtifactStatus = "DRAFT"


class GeneratedTestCase(BaseModel):
    test_case_id: str
    flow_id: str
    scenario_id: str
    title: str
    polarity: TestPolarity = "positive"
    preconditions: list[str] = Field(default_factory=list)
    test_data: dict[str, str] = Field(default_factory=dict)
    steps: list[TestCaseStep] = Field(default_factory=list)
    expected: str = ""
    status: ArtifactStatus = "DRAFT"


class GenerationValidation(BaseModel):
    valid: bool
    reason_code: str
    message: str
    checks: list[dict[str, Any]] = Field(default_factory=list)


class GenerationQualityReport(BaseModel):
    code_valid: bool = False
    typescript_valid: bool = False
    test_discovered: bool = False
    locator_quality: bool = False
    assertion_quality: AssertionQuality = "MISSING"
    page_object_valid: bool = False
    parameter_valid: bool = False
    evidence_ready: bool = False
    traceability_complete: bool = False
    warnings: list[str] = Field(default_factory=list)
    mandatory_pass: bool = False


class GeneratorJournal(BaseModel):
    generation_id: str
    request: str
    flow_id: str
    scenario_id: str
    test_case_id: str
    source_observations: list[str] = Field(default_factory=list)
    actions: list[GeneratedAction] = Field(default_factory=list)
    locators: list[GeneratedLocator] = Field(default_factory=list)
    generated_file: str | None = None
    validation: GenerationValidation | None = None
    quality_report: GenerationQualityReport | None = None
    review_status: ArtifactStatus = "DRAFT"
    timestamp: str = ""
    generator_version: str = "p2.1"
    playwright_version: str = ""
    codegen_bridge_available: bool = False
    codegen_bridge_reason: str = ""
    assertion_quality: AssertionQuality | None = None
    locator_verification: list[dict[str, Any]] = Field(default_factory=list)
    parameter_trace: list[dict[str, str]] = Field(default_factory=list)
    generated_code_hash: str = ""


class GenerationResult(BaseModel):
    generation_id: str
    status: GenerationOutcomeStatus
    flow_id: str
    scenario: TestScenario | None = None
    test_case: GeneratedTestCase | None = None
    actions: list[GeneratedAction] = Field(default_factory=list)
    generated_spec_path: str | None = None
    validation: GenerationValidation | None = None
    quality_report: GenerationQualityReport | None = None
    journal: GeneratorJournal | None = None
    discovery_candidate_id: str | None = None
    message: str = ""
    blocked_execution: bool = True


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
    retrieval_diagnostics: dict[str, Any] | None = None


FailureType = Literal[
    "LOCATOR",
    "TIMING",
    "NAVIGATION",
    "AUTHENTICATION",
    "DATA",
    "APPLICATION",
    "INFRASTRUCTURE",
    "UNKNOWN",
]

HealingProposalStatus = Literal["DRAFT", "PENDING_SME_APPROVAL", "APPROVED", "REJECTED"]
HealingOutcomeStatus = Literal[
    "NOT_HEALABLE",
    "NO_CANDIDATE",
    "NEEDS_REVIEW",
    "HEALED_PENDING_APPROVAL",
    "HEALING_FAILED",
    "REVERTED",
]


class FailureClassification(BaseModel):
    type: FailureType
    test_id: str = ""
    flow_id: str = ""
    step_id: str = ""
    error_message: str = ""
    stack: str = ""
    screenshot_path: str | None = None
    dom_evidence_path: str | None = None
    console_evidence: list[str] = Field(default_factory=list)
    network_evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    healing_eligible: bool = False
    reason: str = ""
    locator_label: str | None = None
    original_locator: str | None = None


class HealingLocatorCandidate(BaseModel):
    primary: str
    fallbacks: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    evidence: str = ""
    reason: str = ""
    css_selectors: list[str] = Field(default_factory=list)
    validated: bool = False


class HealingAttemptRecord(BaseModel):
    attempt: int
    candidate: HealingLocatorCandidate
    applied: bool = False
    retry_ok: bool = False
    evidence_dir: str = ""
    message: str = ""


class HealingProposal(BaseModel):
    healing_id: str
    flow_id: str
    test_id: str
    step_id: str = ""
    locator_label: str = ""
    old_locator: str = ""
    new_locator: str = ""
    fallbacks: list[str] = Field(default_factory=list)
    reason: str = ""
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    validation: dict[str, Any] = Field(default_factory=dict)
    result: str = ""
    status: HealingProposalStatus = "DRAFT"
    failure_type: FailureType = "UNKNOWN"
    created_at: str = ""


class HealingJournal(BaseModel):
    healing_id: str
    run_id: str = ""
    flow_id: str = ""
    test_id: str = ""
    failure: FailureClassification | None = None
    attempts: list[HealingAttemptRecord] = Field(default_factory=list)
    proposal: HealingProposal | None = None
    outcome: HealingOutcomeStatus = "NOT_HEALABLE"
    evidence_paths: list[str] = Field(default_factory=list)
    timestamp: str = ""
    healer_version: str = "p3.0"


class HealingResult(BaseModel):
    healing_id: str
    status: HealingOutcomeStatus
    failure: FailureClassification | None = None
    proposal: HealingProposal | None = None
    journal: HealingJournal | None = None
    attempts_used: int = 0
    message: str = ""
    execution_still_blocked: bool = True


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
    generation_result: GenerationResult | None = None
    healing_result: HealingResult | None = None
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
