"""Aggregate generation quality scoring for P2.1 hardening."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from qa_orchestrator.assertion_quality import AssertionQuality, classify_actions, status_for_assertion_quality
from qa_orchestrator.locator_verification import verify_action_locators
from qa_orchestrator.models import (
    GeneratedAction,
    GeneratedTestCase,
    GenerationQualityReport,
    GenerationValidation,
    TestScenario,
)
from qa_orchestrator.page_object_validator import validate_page_object_actions


def build_parameter_trace(
    *,
    user_goal: str,
    test_case: GeneratedTestCase,
    actions: list[GeneratedAction],
) -> list[dict[str, str]]:
    trace: list[dict[str, str]] = []
    sku_match = re.search(r"\b([A-Za-z0-9-]{3,32})\b", user_goal)
    if sku_match and "sku" in user_goal.lower():
        literal = sku_match.group(1)
        trace.append({"step": "request", "value": literal})
        trace.append({"step": "validated_parameter", "value": f"sku={literal}"})
        trace.append({"step": "env_var", "value": "QA_PARAM_SKU"})
    for action in actions:
        if action.value_source:
            trace.append(
                {
                    "step": "generated_action",
                    "value": f"{action.type}:{action.value_source}",
                }
            )
            if action.page_object_method:
                trace.append(
                    {
                        "step": "page_object_method",
                        "value": f"{action.page_object}.{action.page_object_method}",
                    }
                )
    if test_case.test_data:
        for key, val in test_case.test_data.items():
            trace.append({"step": "test_data", "value": f"{key}={val}"})
    return trace


def validate_parameter_trace(
    content: str,
    *,
    user_goal: str,
    test_case: GeneratedTestCase,
    trace: list[dict[str, str]],
) -> GenerationValidation:
    literals: set[str] = set()
    if "sku" in user_goal.lower():
        for match in re.finditer(r"\b([A-Za-z0-9-]{3,32})\b", user_goal):
            token = match.group(1)
            if token.upper() not in {"SKU", "SEARCH", "ABC"} and len(token) >= 3:
                literals.add(token)
    for literal in literals:
        if literal in content and f"QA_PARAM" not in content:
            return GenerationValidation(
                valid=False,
                reason_code="generation.hardcoded_parameter",
                message=f"Hard-coded user parameter {literal} found in generated source",
            )
        if literal in content and f"process.env" not in content:
            return GenerationValidation(
                valid=False,
                reason_code="generation.hardcoded_parameter",
                message=f"User parameter {literal} must use QA_PARAM_* env, not literal",
            )
    if literals and "QA_PARAM_SKU" not in content and test_case.polarity == "parameterized":
        return GenerationValidation(
            valid=False,
            reason_code="generation.parameter_not_propagated",
            message="Parameterized test must reference QA_PARAM_SKU",
        )
    return GenerationValidation(
        valid=True,
        reason_code="generation.parameter_ok",
        message="Parameter traceability validated",
        checks=[{"trace": trace}],
    )


def build_quality_report(
    *,
    checks: list[GenerationValidation],
    assertion_quality: AssertionQuality,
    locator_results: list[dict[str, object]],
    actions: list[GeneratedAction],
    content: str,
    parameter_valid: bool,
    automation_dir,
) -> GenerationQualityReport:
    structural_codes = (
        "generation.path_ok",
        "generation.valid",
        "generation.syntax_ok",
        "generation.fixture_ok",
        "generation.page_object_ok",
        "generation.parameter_ok",
    )
    code_valid = all(
        c.valid for c in checks if c.reason_code in structural_codes or c.reason_code == "generation.valid"
    )
    typescript_valid = any(c.valid and c.reason_code == "generation.typescript_ok" for c in checks)
    test_discovered = any(c.valid and c.reason_code == "generation.discovery_ok" for c in checks)
    has_locators = any(a.locator for a in actions)
    if has_locators and locator_results:
        locator_quality = all(r.get("locator_verified") for r in locator_results)
    elif has_locators:
        locator_quality = False
    else:
        locator_quality = True
    page_object_valid = all(
        c.valid for c in checks if c.reason_code.startswith("generation.page_object") or c.reason_code == "generation.page_object_ok"
    ) or not any(c.reason_code.startswith("generation.page_object") for c in checks)
    evidence_ready = "recordStep" in content

    def _is_assertion_action(action: GeneratedAction) -> bool:
        return action.type == "assert" or (
            action.type == "page_object" and action.page_object_method == "expectResultRegion"
        )

    assertion_actions = [a for a in actions if _is_assertion_action(a)]
    traceability_complete = bool(assertion_actions) and all(
        a.assertion_source and a.assertion_text for a in assertion_actions
    )
    warnings: list[str] = []
    if assertion_quality == "MODERATE":
        warnings.append("Assertion quality is MODERATE — SME should confirm business outcome")
    if has_locators and locator_results and not locator_quality:
        warnings.append("Some locators were not verified against exploration evidence")

    mandatory = (
        code_valid
        and typescript_valid
        and test_discovered
        and page_object_valid
        and parameter_valid
        and evidence_ready
        and traceability_complete
        and assertion_quality not in {"MISSING", "WEAK"}
        and (locator_quality or not has_locators)
    )
    return GenerationQualityReport(
        code_valid=code_valid,
        typescript_valid=typescript_valid,
        test_discovered=test_discovered,
        locator_quality=locator_quality,
        assertion_quality=assertion_quality,
        page_object_valid=page_object_valid,
        parameter_valid=parameter_valid,
        evidence_ready=evidence_ready,
        traceability_complete=traceability_complete,
        warnings=warnings,
        mandatory_pass=mandatory,
    )


def resolve_outcome_status(
    quality: GenerationQualityReport,
    assertion_quality: AssertionQuality,
) -> str:
    assertion_status = status_for_assertion_quality(assertion_quality)
    if assertion_status == "INVALID":
        return "INVALID"
    if assertion_status == "NEEDS_REVIEW":
        return "NEEDS_REVIEW"
    if not quality.mandatory_pass:
        return "VALIDATION_FAILED"
    return "READY_FOR_APPROVAL"


def code_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
