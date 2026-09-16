"""Healing eligibility policy and confidence thresholds."""

from __future__ import annotations

from qa_orchestrator.models import FailureClassification, FailureType, HealingLocatorCandidate

AUTO_HEAL_THRESHOLD = 0.90
HUMAN_REVIEW_THRESHOLD = 0.70
MAX_HEALING_ATTEMPTS = 2
TIMING_RETRY_MS = 2000


def is_healing_eligible(failure: FailureClassification) -> bool:
    if failure.type == "LOCATOR":
        return True
    if failure.type == "TIMING":
        return True
    return False


def is_auto_heal_candidate(candidate: HealingLocatorCandidate) -> bool:
    return candidate.validated and candidate.confidence >= AUTO_HEAL_THRESHOLD


def requires_human_review(candidate: HealingLocatorCandidate) -> bool:
    return (
        candidate.validated
        and HUMAN_REVIEW_THRESHOLD <= candidate.confidence < AUTO_HEAL_THRESHOLD
    )


def reject_candidate(candidate: HealingLocatorCandidate) -> bool:
    return not candidate.validated or candidate.confidence < HUMAN_REVIEW_THRESHOLD


def never_heal_types() -> set[FailureType]:
    return {"APPLICATION", "AUTHENTICATION", "DATA", "INFRASTRUCTURE", "NAVIGATION", "UNKNOWN"}


def policy_reason(failure: FailureClassification) -> str:
    if failure.type in never_heal_types():
        return f"{failure.type} failures must remain real failures — no automatic healing"
    if failure.type == "TIMING":
        return "Bounded deterministic wait retry only — no locator substitution"
    if failure.type == "LOCATOR":
        return "Locator failure eligible for evidence-backed candidate healing"
    return "Not eligible for healing"
