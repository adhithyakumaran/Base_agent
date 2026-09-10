from enum import Enum


class Conclusion(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class DecisionAction(str, Enum):
    CONTINUE = "CONTINUE"
    CALL_TOOL = "CALL_TOOL"
    RETRY = "RETRY"
    ASK_USER = "ASK_USER"
    ESCALATE = "ESCALATE"
    COMPLETE = "COMPLETE"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class AgentStatus(str, Enum):
    NEW = "new"
    RUNNING = "running"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class ErrorClass(str, Enum):
    TIMEOUT = "timeout"
    NETWORK_FAILURE = "network_failure"
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_FAILURE = "authorization_failure"
    INVALID_INPUT = "invalid_input"
    TOOL_FAILURE = "tool_failure"
    APPLICATION_FAILURE = "application_failure"
    VALIDATION_FAILURE = "validation_failure"
    UNEXPECTED_RESULT = "unexpected_result"
    BUDGET_EXCEEDED = "budget_exceeded"
    CYCLE_DETECTED = "cycle_detected"
    STUCK = "stuck"


class ExecutionMode(str, Enum):
    DETERMINISTIC = "deterministic"
    SIDE_EFFECTING = "side_effecting"
    LLM_BACKED = "llm_backed"


class RoutingMethod(str, Enum):
    RULE = "rule"
    SEMANTIC = "semantic"
    LLM = "llm"
    HYBRID = "hybrid"