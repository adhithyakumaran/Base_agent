"""Parse warm-server / HTTP bodies into RunRequest with explicit skip_execution semantics."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any

from qa_orchestrator.run_request import RunRequest

PRODUCT_EXECUTION_MODES = frozenset({"CI", "LIVE", "LIVE_DEMO"})
HARNESS_OVERRIDE_KEYS = ("allow_skip_execution", "test_harness_skip_override", "harness_skip_execution")


@dataclass(frozen=True)
class RunRequestParseResult:
    request: RunRequest | None = None
    execution_mode: str = "CI"
    skip_execution_resolved: bool = False
    error_code: str | None = None
    error_message: str | None = None
    http_status: int = 400


def parse_strict_bool(value: Any, *, default: bool = False) -> bool:
    """Never treat arbitrary strings as true (fixes bool(\"false\") == True)."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
        return default
    return default


def _body_field(body: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in body:
            return body[key]
    return None


def normalize_execution_mode(raw: Any) -> str:
    mode = str(raw or "CI").strip().upper()
    if mode in PRODUCT_EXECUTION_MODES | {"DRY_RUN"}:
        return mode
    return "CI"


def harness_override_allowed(body: dict[str, Any]) -> bool:
    for key in HARNESS_OVERRIDE_KEYS:
        if parse_strict_bool(_body_field(body, key), default=False):
            return True
    return False


def resolve_skip_execution(
    *,
    body: dict[str, Any],
    execution_mode: str,
) -> tuple[bool, str | None, str | None]:
    """Return (skip_execution, error_code, error_message)."""
    explicit_raw = _body_field(body, "skip_execution", "skipExecution")
    explicit_skip = (
        parse_strict_bool(explicit_raw, default=False)
        if explicit_raw is not None
        else None
    )
    harness = harness_override_allowed(body)

    if execution_mode == "DRY_RUN":
        return True, None, None

    if execution_mode in {"LIVE", "LIVE_DEMO"}:
        if explicit_skip is True and not harness:
            return (
                False,
                "execution.live_skip_rejected",
                (
                    f"skip_execution=true is not allowed for execution_mode={execution_mode} "
                    "without allow_skip_execution harness override"
                ),
            )
        if explicit_skip is True and harness:
            return True, None, None
        return False, None, None

    if execution_mode == "CI":
        if explicit_skip is True:
            return True, None, None
        return False, None, None

    if explicit_skip is True:
        return True, None, None
    return False, None, None


def build_run_request_from_body(body: dict[str, Any]) -> RunRequestParseResult:
    goal = str(body.get("goal") or body.get("message") or "").strip()
    if not goal:
        return RunRequestParseResult(
            error_code="goal_required",
            error_message="goal is required",
            http_status=400,
        )

    execution_mode = normalize_execution_mode(_body_field(body, "execution_mode", "executionMode"))
    skip_execution, err_code, err_msg = resolve_skip_execution(body=body, execution_mode=execution_mode)
    if err_code:
        return RunRequestParseResult(
            execution_mode=execution_mode,
            skip_execution_resolved=skip_execution,
            error_code=err_code,
            error_message=err_msg,
            http_status=400,
        )

    run_type = str(body.get("run_type") or body.get("type") or "adhoc")
    model = body.get("model")
    run_id = body.get("run_id") or body.get("runId")
    context_packets = body.get("context_packets") if isinstance(body.get("context_packets"), list) else []
    skip_discovery = parse_strict_bool(_body_field(body, "skip_discovery", "skipDiscovery"), default=False)

    req = RunRequest(
        goal=goal,
        run_type=run_type,
        model=str(model) if model is not None else None,
        run_id=str(run_id) if run_id else None,
        context_packets=context_packets,
        skip_discovery=skip_discovery,
        skip_execution=skip_execution,
        execution_mode=execution_mode,
        allow_skip_execution=harness_override_allowed(body),
    )
    return RunRequestParseResult(
        request=req,
        execution_mode=execution_mode,
        skip_execution_resolved=skip_execution,
    )


def log_run_request_accepted(
    *,
    run_id: str | None,
    execution_mode: str,
    skip_execution: bool,
    run_type: str,
    goal: str,
    stream: Any | None = None,
) -> None:
    target = stream if stream is not None else sys.stderr
    safe_goal = goal.replace("\n", " ").strip()[:160]
    payload = {
        "event": "RUN_REQUEST_ACCEPTED",
        "run_id": run_id or "-",
        "execution_mode": execution_mode,
        "skip_execution": skip_execution,
        "run_type": run_type,
        "goal": safe_goal,
    }
    target.write(json.dumps(payload, ensure_ascii=True) + "\n")
    try:
        target.flush()
    except Exception:
        pass
