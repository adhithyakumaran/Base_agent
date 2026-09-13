"""Classify Playwright test failures for controlled self-healing."""

from __future__ import annotations

import re

from qa_orchestrator.models import FailureClassification, FailureType, StepObservation


_LOCATOR_PATTERNS = (
    r"no locator resolved",
    r"locator\.",
    r"getbyrole",
    r"getbytestid",
    r"getbylabel",
    r"strict mode violation",
    r"waiting for locator",
    r"element\(s\) not found",
    r"selector.*not found",
    r"ambiguous locator",
)
_TIMING_PATTERNS = (
    r"timeout \d+ms exceeded",
    r"waiting until .* visible",
    r"waiting for selector",
    r"test timeout",
)
_NAV_PATTERNS = (r"navigation", r"page\.goto", r"net::err", r"404", r"url mismatch")
_AUTH_PATTERNS = (r"login", r"authentication", r"401", r"403", r"storagestate", r"unauthorized")
_DATA_PATTERNS = (
    r"qa_param",
    r"invalid sku",
    r"no item code",
    r"not set",
    r"invalid param",
    r"no result",
    r"empty result",
)
_APP_PATTERNS = (
    r"expect\(",
    r"tobevisible",
    r"tohavetext",
    r"product unavailable",
    r"assertion",
    r"expected.*received",
    r"business",
)
_INFRA_PATTERNS = (
    r"econnrefused",
    r"npm not found",
    r"browser.*not installed",
    r"playwright install",
    r"global-setup",
)


def classify_failure(
    *,
    observation: StepObservation,
    flow_id: str = "",
    test_id: str = "",
    step_id: str = "",
) -> FailureClassification:
    haystack = _failure_text(observation)
    failure_type, confidence, reason = _detect_type(haystack)
    locator_label, original_locator = _extract_locator_context(haystack, observation)
    screenshot, dom_path = _extract_evidence_paths(observation)
    eligible = failure_type in {"LOCATOR", "TIMING"}

    return FailureClassification(
        type=failure_type,
        test_id=test_id,
        flow_id=flow_id,
        step_id=step_id or str(observation.step_index),
        error_message=(observation.message or "")[:2000],
        stack=_extract_stack(observation),
        screenshot_path=screenshot,
        dom_evidence_path=dom_path,
        console_evidence=_extract_console(observation),
        network_evidence=_extract_network(observation),
        confidence=confidence,
        healing_eligible=eligible and failure_type == "LOCATOR",
        reason=reason,
        locator_label=locator_label,
        original_locator=original_locator,
    )


def _failure_text(observation: StepObservation) -> str:
    parts = [observation.message or ""]
    meta = observation.meta or {}
    parts.append(str(meta.get("stderr_tail") or ""))
    parts.append(str(meta.get("stdout_tail") or ""))
    report = meta.get("playwright_report") or {}
    parts.append(str(report))
    return "\n".join(parts).lower()


def _detect_type(haystack: str) -> tuple[FailureType, float, str]:
    if any(re.search(p, haystack) for p in _INFRA_PATTERNS):
        return "INFRASTRUCTURE", 0.95, "Infrastructure or environment failure"
    if any(re.search(p, haystack) for p in _AUTH_PATTERNS):
        return "AUTHENTICATION", 0.9, "Authentication/session failure — not healable"
    if _looks_like_business_assertion(haystack):
        return "APPLICATION", 0.92, "Business assertion or application outcome mismatch"
    if any(re.search(p, haystack) for p in _DATA_PATTERNS):
        return "DATA", 0.88, "Test data or parameter issue"
    if any(re.search(p, haystack) for p in _LOCATOR_PATTERNS):
        return "LOCATOR", 0.9, "Locator resolution failure"
    if any(re.search(p, haystack) for p in _NAV_PATTERNS):
        return "NAVIGATION", 0.85, "Navigation or URL failure"
    if any(re.search(p, haystack) for p in _TIMING_PATTERNS):
        return "TIMING", 0.8, "Timing/wait failure"
    return "UNKNOWN", 0.4, "Unclassified failure"


def _looks_like_business_assertion(haystack: str) -> bool:
    if "product unavailable" in haystack:
        return True
    if any(re.search(p, haystack) for p in _APP_PATTERNS):
        if any(re.search(p, haystack) for p in _LOCATOR_PATTERNS):
            return False
        return True
    return False


def _extract_locator_context(haystack: str, observation: StepObservation) -> tuple[str | None, str | None]:
    label = None
    original = None
    for match in re.finditer(r"for ([a-z0-9 _-]+):", haystack, re.I):
        label = match.group(1).strip()
    for match in re.finditer(r"(page\.getby\w+\([^\)]+\)|#[a-z0-9_-]+|\[data-testid[^\]]+\])", haystack, re.I):
        original = match.group(1)
    meta = observation.meta or {}
    for entry in meta.get("evidence") or []:
        entry_meta = entry.get("meta") or {}
        if entry_meta.get("locatorLabel"):
            label = str(entry_meta["locatorLabel"])
        if entry_meta.get("locator"):
            original = str(entry_meta["locator"])
    return label, original


def _extract_evidence_paths(observation: StepObservation) -> tuple[str | None, str | None]:
    screenshot = observation.screenshot_path
    dom_path = None
    for entry in (observation.meta or {}).get("evidence") or []:
        if entry.get("dom_path"):
            dom_path = str(entry["dom_path"])
        if not screenshot and entry.get("path"):
            screenshot = str(entry["path"])
    return screenshot, dom_path


def _extract_stack(observation: StepObservation) -> str:
    meta = observation.meta or {}
    tail = str(meta.get("stderr_tail") or meta.get("stdout_tail") or "")
    return tail[:4000]


def _extract_console(observation: StepObservation) -> list[str]:
    lines: list[str] = []
    for entry in (observation.meta or {}).get("evidence") or []:
        meta = entry.get("meta") or {}
        for event in meta.get("console") or []:
            lines.append(str(event))
    return lines[:20]


def _extract_network(observation: StepObservation) -> list[str]:
    lines: list[str] = []
    for entry in (observation.meta or {}).get("evidence") or []:
        meta = entry.get("meta") or {}
        for event in meta.get("network") or []:
            lines.append(str(event))
    return lines[:20]
