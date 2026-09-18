"""Deterministic executive summary and final explanations."""

from __future__ import annotations

from qa_orchestrator.qa_report.models import QAReport, ReportFinalResult


def build_executive_summary(report: QAReport) -> str:
    sentences: list[str] = []
    flows = ", ".join(report.flow_ids[:3]) if report.flow_ids else "selected flow(s)"
    sentences.append(f"The {flows} flow coverage was planned for goal: {report.goal}.")
    if report.input_parameters:
        param_text = ", ".join(f"{k}={v}" for k, v in list(report.input_parameters.items())[:4])
        sentences.append(f"Input parameters: {param_text}.")
    if report.execution.command:
        sentences.append(
            f"Execution used {report.execution.runner or report.execution.execution_mode or 'runner'} "
            f"with command `{report.execution.command}`."
        )
    elif report.execution.execution_result:
        sentences.append(f"Execution result mode was `{report.execution.execution_result}`.")
    count = len(report.evidence.screenshots)
    if count:
        sentences.append(f"{count} evidence capture(s) were recorded.")
    elif report.execution.errors:
        sentences.append(f"Execution reported: {report.execution.errors[0]}.")
    conclusion = report.overall_result
    if conclusion == "NEEDS_REVIEW":
        failed = report.validation.failed_checks
        if "ground_truth" in failed or report.validation.ground_truth.get("approved_available") is False:
            sentences.append(
                "Business validation could not be finalized because approved Ground Truth was not available."
            )
        elif report.validation.reason_code:
            sentences.append(f"Validation returned `{report.validation.reason_code}`.")
    elif conclusion == "PASS":
        sentences.append("Structured validation concluded PASS based on recorded execution and assertions.")
    elif conclusion == "FAIL":
        sentences.append("Structured validation concluded FAIL based on recorded execution failures.")
    elif conclusion == "BLOCKED":
        sentences.append("Execution was blocked by policy or execution gate before completion.")
    return " ".join(sentences)


def build_final_result(report: QAReport) -> ReportFinalResult:
    conclusion = report.overall_result
    reason = report.validation.reason_code
    explanation_parts: list[str] = [f"Final structured conclusion: {conclusion}."]
    if reason:
        explanation_parts.append(f"Reason code: `{reason}`.")
    if report.validation.needs_review_detail:
        detail = report.validation.needs_review_detail
        if detail.get("failed_check"):
            explanation_parts.append(f"Failed check: {detail['failed_check']}.")
        if detail.get("message"):
            explanation_parts.append(detail["message"])
    elif report.validation.failed_checks:
        explanation_parts.append(f"Failed checks: {', '.join(report.validation.failed_checks)}.")
    return ReportFinalResult(
        conclusion=conclusion,
        reason_code=reason,
        explanation=" ".join(explanation_parts),
    )


def needs_review_detail_from_diagnostics(diagnostics: dict) -> dict[str, str]:
    if not diagnostics:
        return {}
    failed = diagnostics.get("failed_checks") or []
    failed_check = ", ".join(failed) if isinstance(failed, list) else str(failed)
    return {
        "reason": str(diagnostics.get("reason_code") or ""),
        "failed_check": failed_check,
        "message": str(diagnostics.get("message") or diagnostics.get("failed_condition") or ""),
        "expected": "Approved Ground Truth or passing structured validation",
        "actual": str(diagnostics.get("failed_condition") or "not satisfied"),
        "what_prevented_pass": str(diagnostics.get("message") or diagnostics.get("reason_code") or ""),
    }
