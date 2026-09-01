"""Deterministic technical rules for APEX QA — no Ground Truth required."""

from __future__ import annotations

from typing import Any


def evaluate_technical_rules(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return rule check records with outcome pass|fail|insufficient."""
    checks: list[dict[str, Any]] = []
    body = str(payload.get("body_text") or "")
    low = body.lower()
    pages = payload.get("pages") or []
    blockers = payload.get("blockers") or []
    stats = payload.get("stats") or {}

    # Error page
    if any(tok in body for tok in ("ORA-", "Unexpected error", "APEX error")) or "apex.error_page" in str(
        payload
    ):
        checks.append({"id": "rule.apex.error_page", "outcome": "fail", "detail": "ORA/APEX error text observed"})
    else:
        checks.append({"id": "rule.apex.error_page", "outcome": "pass", "detail": "no ORA/APEX error text"})

    # Session — only assert when live crawl pages expose session fields
    session_fields = [p for p in pages if isinstance(p, dict) and ("session" in p or "url" in p and "ords" in str(p.get("url") or ""))]
    session_ok = any(isinstance(p, dict) and p.get("session") for p in session_fields)
    apex = payload.get("apex") or {}
    if apex.get("session_captured"):
        session_ok = True
    if session_fields:
        checks.append(
            {
                "id": "rule.session.present",
                "outcome": "pass" if session_ok else "fail",
                "detail": "session query captured on crawled pages",
            }
        )
    elif pages:
        checks.append(
            {
                "id": "rule.session.present",
                "outcome": "insufficient",
                "detail": "KB page maps only — live session not in scope",
            }
        )
    else:
        checks.append({"id": "rule.session.present", "outcome": "insufficient", "detail": "no pages in payload"})

    # Anti-stuck: modal hang would show as timed_out without dismissed when found
    modal_hang = False
    for p in pages:
        if not isinstance(p, dict):
            continue
        for ev in p.get("modal_events") or []:
            if ev.get("found") and ev.get("timed_out") and not ev.get("dismissed"):
                modal_hang = True
    checks.append(
        {
            "id": "rule.anti_stuck.modal",
            "outcome": "fail" if modal_hang else "pass",
            "detail": "modal timed out without dismiss" if modal_hang else "no modal hang",
        }
    )

    # Budget honesty
    if stats.get("truncated"):
        checks.append(
            {
                "id": "rule.budget.max_pages",
                "outcome": "pass",
                "detail": "crawl stopped at max_pages (honest truncation, not loop)",
            }
        )
    else:
        checks.append({"id": "rule.budget.max_pages", "outcome": "pass", "detail": "within page budget"})

    # Auth blockers
    auth_block = any(
        isinstance(b, dict) and str(b.get("reason", "")).startswith("login.") for b in blockers
    )
    if auth_block:
        checks.append({"id": "rule.auth.login", "outcome": "fail", "detail": "login blocker present"})
    elif blockers and not pages:
        checks.append({"id": "rule.auth.login", "outcome": "insufficient", "detail": "blockers without pages"})
    else:
        checks.append({"id": "rule.auth.login", "outcome": "pass", "detail": "no login blocker"})

    # Stuck keyword
    if "session has expired" in low or "your session has ended" in low:
        checks.append({"id": "rule.session.dead", "outcome": "fail", "detail": "session expiry text"})
    else:
        checks.append({"id": "rule.session.dead", "outcome": "pass", "detail": "no session-expiry text"})

    return checks


def technical_outcome(checks: list[dict[str, Any]]) -> str:
    """Aggregate: any fail → fail; else if any insufficient → insufficient; else pass."""
    outcomes = {c.get("outcome") for c in checks}
    if "fail" in outcomes:
        return "fail"
    if "insufficient" in outcomes:
        return "insufficient"
    return "pass"
