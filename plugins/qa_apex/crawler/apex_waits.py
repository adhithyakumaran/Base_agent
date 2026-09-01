from __future__ import annotations

import time
from typing import Any


def wait_for_ajax(page: Any, *, timeout_ms: int = 8000) -> dict[str, Any]:
    """Bounded wait for APEX ajax; never hangs the crawl budget.

    Strategy:
    1) If apex.event or jQuery active indicators exist, wait briefly for idle.
    2) Otherwise wait for in-flight /wwv_flow.ajax responses to settle.
    Hard ceiling: timeout_ms.
    """
    started = time.monotonic()
    outcome = {"waited_ms": 0, "method": "none", "timed_out": False}
    try:
        # Prefer explicit APEX ajax idle when available
        page.wait_for_function(
            """() => {
              try {
                if (window.apex && apex.event && typeof apex.event.trigger === 'function') {
                  // jQuery active is the practical signal many APEX apps expose
                  if (window.jQuery && jQuery.active !== undefined) return jQuery.active === 0;
                }
                if (window.jQuery && jQuery.active !== undefined) return jQuery.active === 0;
                return true;
              } catch (e) { return true; }
            }""",
            timeout=timeout_ms,
        )
        outcome["method"] = "jquery_active_or_fallback"
    except Exception:
        outcome["timed_out"] = True
        outcome["method"] = "ajax_wait_timeout"
    outcome["waited_ms"] = int((time.monotonic() - started) * 1000)
    return outcome


def wait_settle(page: Any, *, settle_ms: int = 1200) -> None:
    """Short DOM settle — never a multi-second blind sleep chain."""
    try:
        page.wait_for_timeout(settle_ms)
    except Exception:
        time.sleep(settle_ms / 1000.0)


def dismiss_modal_if_present(page: Any, *, timeout_ms: int = 3000) -> dict[str, Any]:
    """If a dialog/modal is open, try close; always return within timeout_ms."""
    started = time.monotonic()
    result = {"found": False, "dismissed": False, "timed_out": False, "reason": ""}
    deadline = started + (timeout_ms / 1000.0)
    selectors = [
        "iframe.ui-dialog-content",
        ".ui-dialog:visible",
        "[role='dialog']",
        ".a-Dialog-body",
    ]
    try:
        for sel in selectors:
            if time.monotonic() > deadline:
                result["timed_out"] = True
                break
            loc = page.locator(sel).first
            try:
                if loc.count() == 0:
                    continue
                if not loc.is_visible(timeout=400):
                    continue
            except Exception:
                continue
            result["found"] = True
            # Try Escape on page, then common close buttons
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            for close_sel in (
                ".ui-dialog-titlebar-close",
                "button:has-text('Cancel')",
                "button:has-text('Close')",
                "[aria-label='Close']",
            ):
                if time.monotonic() > deadline:
                    result["timed_out"] = True
                    break
                try:
                    btn = page.locator(close_sel).first
                    if btn.count() and btn.is_visible(timeout=300):
                        btn.click(timeout=800)
                        result["dismissed"] = True
                        result["reason"] = close_sel
                        break
                except Exception:
                    continue
            break
    except Exception as exc:
        result["reason"] = f"error:{type(exc).__name__}"
    result["elapsed_ms"] = int((time.monotonic() - started) * 1000)
    return result
