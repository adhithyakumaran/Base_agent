"""P7 — LLM decision proposal schema validation and safety checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from qa_orchestrator.agent_decision_context import AgentDecisionContext
from qa_orchestrator.agent_models import AgentActionType

ALLOWED_ACTIONS: frozenset[AgentActionType] = frozenset(
    {
        "RUN_EXISTING_TEST",
        "EXPLORE",
        "CAPTURE_EVIDENCE",
        "VERIFY",
        "RECOVER_LOCATOR",
        "WAIT_FOR_REVIEW",
        "STOP",
    }
)

INJECTION_PATTERNS = (
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(the\s+)?(system|developer)",
    r"you\s+are\s+now",
    r"execute\s+delete",
    r"run\s+shell",
    r"curl\s+",
    r"page\.goto",
    r"page\.locator",
    r"bypass\s+(the\s+)?(gate|policy|approval)",
    r"approve\s+(this|the)\s+(test|healing|flow)",
)

FORBIDDEN_REASON_PATTERNS = (
    "shell",
    "subprocess",
    "javascript:",
    "eval(",
    "exec(",
    "page.goto",
    "page.locator",
    "curl ",
    "wget ",
)


class AgentDecisionProposal(BaseModel):
    decision_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    proposed_action: AgentActionType
    reason: str = ""
    confidence: float = 0.0
    evidence_refs: list[str] = Field(default_factory=list)
    source: str = "LLM"
    allowed: bool = False
    policy_reason: str = ""

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, value: float) -> float:
        if value < 0.0 or value > 1.0:
            raise ValueError("confidence must be between 0 and 1")
        return value


@dataclass(frozen=True)
class ProposalValidationResult:
    ok: bool
    proposal: AgentDecisionProposal | None = None
    reason: str = ""
    rejected_as_injection: bool = False
    rejected_as_hallucination: bool = False
    rejected_as_malformed: bool = False
    rejected_low_confidence: bool = False


def _contains_injection(text: str) -> bool:
    lowered = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            return True
    return False


def parse_llm_payload(raw: dict[str, Any] | None) -> ProposalValidationResult:
    if not raw or not isinstance(raw, dict):
        return ProposalValidationResult(ok=False, reason="malformed_json", rejected_as_malformed=True)
    action = raw.get("proposed_action")
    if action not in ALLOWED_ACTIONS:
        return ProposalValidationResult(ok=False, reason="unknown_action", rejected_as_malformed=True)
    try:
        proposal = AgentDecisionProposal(
            proposed_action=action,  # type: ignore[arg-type]
            reason=str(raw.get("reason") or ""),
            confidence=float(raw.get("confidence", 0.0)),
            evidence_refs=[str(x) for x in (raw.get("evidence_refs") or [])],
        )
    except (TypeError, ValueError) as exc:
        return ProposalValidationResult(ok=False, reason=str(exc), rejected_as_malformed=True)
    return ProposalValidationResult(ok=True, proposal=proposal)


def validate_proposal(
    proposal: AgentDecisionProposal,
    context: AgentDecisionContext,
    *,
    min_confidence: float = 0.8,
    auto_decision: bool = False,
) -> ProposalValidationResult:
    reason_blob = proposal.reason.lower()
    for pattern in FORBIDDEN_REASON_PATTERNS:
        if pattern in reason_blob:
            proposal.allowed = False
            proposal.policy_reason = f"forbidden pattern in reason: {pattern}"
            return ProposalValidationResult(
                ok=False,
                proposal=proposal,
                reason=proposal.policy_reason,
                rejected_as_injection=True,
            )

    if _contains_injection(proposal.reason):
        proposal.allowed = False
        proposal.policy_reason = "prompt injection pattern in proposal reason"
        return ProposalValidationResult(
            ok=False,
            proposal=proposal,
            reason=proposal.policy_reason,
            rejected_as_injection=True,
        )

    if proposal.proposed_action not in context.allowed_actions:
        proposal.allowed = False
        proposal.policy_reason = "proposed action not in allowed candidate set"
        return ProposalValidationResult(ok=False, proposal=proposal, reason=proposal.policy_reason)

    if auto_decision and proposal.confidence < min_confidence:
        proposal.allowed = False
        proposal.policy_reason = f"confidence {proposal.confidence} below threshold {min_confidence}"
        return ProposalValidationResult(
            ok=False,
            proposal=proposal,
            reason=proposal.policy_reason,
            rejected_low_confidence=True,
        )

    known_refs = set(context.evidence_refs)
    if proposal.evidence_refs and not set(proposal.evidence_refs).issubset(known_refs):
        proposal.allowed = False
        proposal.policy_reason = "hallucinated evidence reference"
        return ProposalValidationResult(
            ok=False,
            proposal=proposal,
            reason=proposal.policy_reason,
            rejected_as_hallucination=True,
        )

    if (
        not proposal.evidence_refs
        and proposal.proposed_action in {"VERIFY", "RECOVER_LOCATOR"}
        and context.ambiguous
    ):
        proposal.allowed = False
        proposal.policy_reason = "insufficient evidence for proposed action"
        return ProposalValidationResult(ok=False, proposal=proposal, reason=proposal.policy_reason)

    proposal.allowed = True
    proposal.policy_reason = "proposal validated"
    return ProposalValidationResult(ok=True, proposal=proposal, reason=proposal.policy_reason)
