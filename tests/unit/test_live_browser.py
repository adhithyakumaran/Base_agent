"""Live interactive browser execution mode tests."""

from __future__ import annotations

import os

import pytest

from qa_orchestrator.live_browser_config import load_live_browser_config, require_live_environment
from qa_orchestrator.live_browser_events import LiveEventStore
from qa_orchestrator.live_browser_redaction import redact_event_payload
from qa_orchestrator.live_browser_registry import LiveBrowserSession, LiveBrowserSessionMeta, close_session, register_session


def test_ci_mode_defaults_headless(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_RUN_MODE", "CI")
    monkeypatch.delenv("QA_LIVE_BROWSER", raising=False)
    cfg = load_live_browser_config()
    assert cfg.headless is True
    assert cfg.keep_browser_open is False


def test_live_demo_mode_headed_keep_open_delay(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_RUN_MODE", "LIVE_DEMO")
    monkeypatch.setenv("EA_BASE_URL", "https://uat.example.com/ords/r/tjdcom/ea")
    cfg = load_live_browser_config()
    assert cfg.is_live is True
    assert cfg.headless is False
    assert cfg.keep_browser_open is True
    assert cfg.action_delay_ms >= 500
    assert cfg.browser_channel == "chrome"


def test_live_requires_configured_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_RUN_MODE", "LIVE")
    monkeypatch.delenv("EA_BASE_URL", raising=False)
    cfg = load_live_browser_config()
    assert require_live_environment(cfg) == "LIVE_ENV_BLOCKED: EA_BASE_URL is not configured"


def test_redaction_masks_passwords():
    payload = redact_event_payload(
        {"action": "FILL", "value_summary": "secret", "target": "input[name=password]"}
    )
    assert payload["value_summary"] == "[redacted]"


def test_live_event_store_persists(tmp_path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "events.jsonl"
    store = LiveEventStore("run-1", path=path)
    store.emit(phase="PLAN", action="SELECT", value_summary="BF-PRODUCT-003")
    rows = store.list_events()
    assert len(rows) == 1
    assert rows[0]["action"] == "SELECT"


def test_registry_close_session():
    register_session(
        LiveBrowserSession(
            meta=LiveBrowserSessionMeta(
                run_id="run-x",
                browser_session_id="live-run-x",
                profile_dir="/tmp/profile",
            )
        )
    )
    assert close_session("run-x") is True


def test_dry_run_not_live(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_RUN_MODE", "DRY_RUN")
    cfg = load_live_browser_config()
    assert cfg.run_mode == "DRY_RUN"


def test_parameter_rate_import_alias():
    assert p9_rate([]) is None
