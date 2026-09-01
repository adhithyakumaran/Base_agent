from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from plugins.qa_apex.crawler.apex_waits import wait_for_ajax, wait_settle
from plugins.qa_apex.crawler.selectors import parse_apex_url


@dataclass
class SessionConfig:
    login_url: str
    username: str
    password: str
    username_selectors: tuple[str, ...] = (
        "#P9999_USERNAME",
        "#P101_USERNAME",
        "input[name*='USERNAME' i]",
        "input[type='text']",
        "input[type='email']",
    )
    password_selectors: tuple[str, ...] = (
        "#P9999_PASSWORD",
        "#P101_PASSWORD",
        "input[name*='PASSWORD' i]",
        "input[type='password']",
    )
    submit_selectors: tuple[str, ...] = (
        "#P9999_LOGIN",
        "button:has-text('Sign In')",
        "button:has-text('Login')",
        "input[type='submit']",
        "button[type='submit']",
    )
    type_delay_ms: int = 25  # CSP-safe typing for APEX login
    navigation_timeout_ms: int = 45_000


def session_from_env() -> SessionConfig | None:
    url = os.environ.get("APEX_TARGET_URL") or os.environ.get("TARGET_URL")
    user = os.environ.get("APEX_USERNAME") or os.environ.get("TARGET_USERNAME")
    password = os.environ.get("APEX_PASSWORD") or os.environ.get("TARGET_PASSWORD")
    if not (url and user and password):
        return None
    return SessionConfig(login_url=url, username=user, password=password)


def _first_visible(page: Any, selectors: tuple[str, ...]) -> Any | None:
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            if loc.count() and loc.is_visible(timeout=800):
                return loc
        except Exception:
            continue
    return None


def login_apex(page: Any, cfg: SessionConfig) -> dict[str, Any]:
    """Deterministic APEX login. Uses type-with-delay when needed (CSP)."""
    page.set_default_navigation_timeout(cfg.navigation_timeout_ms)
    page.goto(cfg.login_url, wait_until="domcontentloaded")
    wait_settle(page, settle_ms=800)
    user = _first_visible(page, cfg.username_selectors)
    pwd = _first_visible(page, cfg.password_selectors)
    if user is None or pwd is None:
        return {"ok": False, "reason": "login.fields_not_found", "url": page.url}
    try:
        user.click(timeout=2000)
        user.fill("")
        user.type(cfg.username, delay=cfg.type_delay_ms)
        pwd.click(timeout=2000)
        pwd.fill("")
        pwd.type(cfg.password, delay=cfg.type_delay_ms)
    except Exception as exc:
        return {"ok": False, "reason": f"login.type_failed:{type(exc).__name__}", "url": page.url}
    submit = _first_visible(page, cfg.submit_selectors)
    try:
        if submit is not None:
            submit.click(timeout=5000)
        else:
            pwd.press("Enter")
        page.wait_for_load_state("domcontentloaded", timeout=cfg.navigation_timeout_ms)
        wait_for_ajax(page, timeout_ms=5000)
        wait_settle(page, settle_ms=1000)
    except Exception as exc:
        return {"ok": False, "reason": f"login.navigate_failed:{type(exc).__name__}", "url": page.url}
    parsed = parse_apex_url(page.url)
    ok = bool(parsed.session) and "login" not in (parsed.page_alias or "").lower()
    return {
        "ok": ok,
        "reason": "login.ok" if ok else "login.still_on_login_or_no_session",
        "url": page.url,
        "session": parsed.session,
        "page_alias": parsed.page_alias,
        "app_alias": parsed.app_alias,
    }
