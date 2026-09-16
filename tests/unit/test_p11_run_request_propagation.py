"""P11.1 — run request propagation (skip_execution / execution_mode)."""

from __future__ import annotations

import json

import pytest

from qa_orchestrator.run_request import RunRequest
from qa_orchestrator.run_request_parse import (
    build_run_request_from_body,
    parse_strict_bool,
    resolve_skip_execution,
)


def test_parse_strict_bool_rejects_string_false_truthiness_bug() -> None:
    assert parse_strict_bool("false") is False
    assert parse_strict_bool("true") is True
    assert parse_strict_bool(None, default=False) is False
    assert parse_strict_bool(True) is True


def test_missing_skip_execution_defaults_false_ci() -> None:
    parsed = build_run_request_from_body({"goal": "Search SKU ABC123", "run_type": "adhoc"})
    assert parsed.request is not None
    assert parsed.execution_mode == "CI"
    assert parsed.skip_execution_resolved is False
    assert parsed.request.skip_execution is False


def test_console_like_live_demo_request() -> None:
    parsed = build_run_request_from_body(
        {
            "goal": "Search SKU 552811DUDABA00",
            "run_type": "adhoc",
            "run_id": "run_mj4qy16gpz6s",
            "execution_mode": "LIVE_DEMO",
            "skip_execution": False,
            "allow_skip_execution": False,
        }
    )
    assert parsed.request is not None
    assert parsed.execution_mode == "LIVE_DEMO"
    assert parsed.request.skip_execution is False


def test_live_demo_rejects_accidental_skip_without_harness() -> None:
    parsed = build_run_request_from_body(
        {
            "goal": "Search SKU ABC",
            "execution_mode": "LIVE_DEMO",
            "skip_execution": True,
        }
    )
    assert parsed.request is None
    assert parsed.error_code == "execution.live_skip_rejected"


def test_dry_run_mode_forces_skip_execution() -> None:
    skip, code, _ = resolve_skip_execution(
        body={"skip_execution": False},
        execution_mode="DRY_RUN",
    )
    assert skip is True
    assert code is None


def test_ci_explicit_skip_true_for_harness() -> None:
    parsed = build_run_request_from_body(
        {
            "goal": "Check login",
            "run_type": "adhoc",
            "execution_mode": "CI",
            "skip_execution": True,
        }
    )
    assert parsed.request is not None
    assert parsed.request.skip_execution is True


def test_p10_harness_explicit_skip_unchanged() -> None:
    parsed = build_run_request_from_body(
        {
            "goal": "Check login",
            "run_type": "adhoc",
            "skip_execution": True,
        }
    )
    assert parsed.request is not None
    assert parsed.request.skip_execution is True


def test_string_false_skip_not_truthy_on_ci() -> None:
    parsed = build_run_request_from_body(
        {
            "goal": "Search SKU ABC",
            "execution_mode": "CI",
            "skip_execution": "false",
        }
    )
    assert parsed.request is not None
    assert parsed.request.skip_execution is False


def test_harness_override_allows_live_skip_when_explicit() -> None:
    parsed = build_run_request_from_body(
        {
            "goal": "eval only",
            "execution_mode": "LIVE_DEMO",
            "skip_execution": True,
            "allow_skip_execution": True,
        }
    )
    assert parsed.request is not None
    assert parsed.request.skip_execution is True
    assert parsed.request.allow_skip_execution is True


def test_run_request_dataclass_defaults() -> None:
    req = RunRequest(goal="x")
    assert req.skip_execution is False
    assert req.execution_mode == "CI"
    assert req.allow_skip_execution is False


def test_acceptance_log_shape(capsys: pytest.CaptureFixture[str]) -> None:
    from qa_orchestrator.run_request_parse import log_run_request_accepted

    log_run_request_accepted(
        run_id="run_test",
        execution_mode="LIVE_DEMO",
        skip_execution=False,
        run_type="adhoc",
        goal="Search SKU",
    )
    out = capsys.readouterr().err
    payload = json.loads(out.strip())
    assert payload["event"] == "RUN_REQUEST_ACCEPTED"
    assert payload["skip_execution"] is False
    assert payload["execution_mode"] == "LIVE_DEMO"
