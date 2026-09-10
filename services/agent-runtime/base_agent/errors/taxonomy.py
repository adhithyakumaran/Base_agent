from __future__ import annotations

from dataclasses import dataclass

from base_agent.contracts.enums import ErrorClass


@dataclass(frozen=True)
class RetryPolicySpec:
    max_attempts: int
    backoff_ms: int
    retryable: bool


DEFAULT_RETRY: dict[ErrorClass, RetryPolicySpec] = {
    ErrorClass.TIMEOUT: RetryPolicySpec(2, 200, True),
    ErrorClass.NETWORK_FAILURE: RetryPolicySpec(3, 300, True),
    ErrorClass.AUTHENTICATION_FAILURE: RetryPolicySpec(0, 0, False),
    ErrorClass.AUTHORIZATION_FAILURE: RetryPolicySpec(0, 0, False),
    ErrorClass.INVALID_INPUT: RetryPolicySpec(0, 0, False),
    ErrorClass.TOOL_FAILURE: RetryPolicySpec(2, 200, True),
    ErrorClass.APPLICATION_FAILURE: RetryPolicySpec(0, 0, False),  # fact, not infra retry
    ErrorClass.VALIDATION_FAILURE: RetryPolicySpec(0, 0, False),
    ErrorClass.UNEXPECTED_RESULT: RetryPolicySpec(0, 0, False),
    ErrorClass.BUDGET_EXCEEDED: RetryPolicySpec(0, 0, False),
    ErrorClass.CYCLE_DETECTED: RetryPolicySpec(0, 0, False),
    ErrorClass.STUCK: RetryPolicySpec(0, 0, False),
}


def is_retryable(error_class: ErrorClass, attempt: int, override_max: int | None = None) -> bool:
    spec = DEFAULT_RETRY[error_class]
    max_attempts = override_max if override_max is not None else spec.max_attempts
    return spec.retryable and attempt < max_attempts


def classify_exception(exc: Exception) -> ErrorClass:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "timeout" in name or "timeout" in msg:
        return ErrorClass.TIMEOUT
    if "auth" in msg and "forbidden" in msg:
        return ErrorClass.AUTHORIZATION_FAILURE
    if "unauthorized" in msg or "authentication" in msg:
        return ErrorClass.AUTHENTICATION_FAILURE
    if "network" in msg or "connection" in msg:
        return ErrorClass.NETWORK_FAILURE
    if "validation" in msg or "schema" in msg:
        return ErrorClass.INVALID_INPUT
    return ErrorClass.TOOL_FAILURE