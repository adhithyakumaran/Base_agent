"""Read-only and safety policy for browser exploration actions."""

from __future__ import annotations

import re
from dataclasses import dataclass

_SAFE_ACTION_TYPES = frozenset(
    {"navigate", "inspect", "scroll", "screenshot", "observe", "capture", "expand_readonly", "fill", "click", "type"}
)

_READ_ONLY_CLICK_PATTERNS = (
    r"\bsearch\b",
    r"\bfind\b",
    r"\bexpand\b",
    r"\bshow\b",
    r"\bview\b",
    r"\bopen\b",
    r"\bnext\b",
    r"\btab\b",
)

_BLOCKED_TEXT_PATTERNS = (
    r"\bdelete\b",
    r"\bremove\b",
    r"\bsubmit\b",
    r"\bapprove\b",
    r"\bcreate invoice\b",
    r"\bmodify\b",
    r"\bupdate record\b",
    r"\bsave changes\b",
    r"\badmin\b",
    r"\bpurge\b",
    r"\btruncate\b",
    r"\bdrop\b",
)

_BLOCKED_FORM_PATTERNS = (
    r"\bdelete\b",
    r"\bremove\b",
    r"\bapprove\b",
    r"\binvoice\b",
    r"\badministration\b",
)


@dataclass(frozen=True)
class ActionPolicyDecision:
    allowed: bool
    reason_code: str
    message: str


class ExplorationPolicy:
    def __init__(self, *, read_only: bool = True, allowed_actions: list[str] | None = None) -> None:
        self.read_only = read_only
        self.allowed_actions = set(allowed_actions or []) | _SAFE_ACTION_TYPES

    def validate_action_type(self, action_type: str) -> ActionPolicyDecision:
        if action_type not in self.allowed_actions and action_type not in _SAFE_ACTION_TYPES:
            return ActionPolicyDecision(
                allowed=False,
                reason_code="BLOCKED_ACTION",
                message=f"Action type '{action_type}' not in allowed_actions",
            )
        return ActionPolicyDecision(True, "policy.ok", "Action type permitted")

    def validate_interaction(
        self,
        *,
        action_type: str,
        element_text: str = "",
        element_role: str = "",
        element_name: str = "",
        form_action: str = "",
        value: str | None = None,
    ) -> ActionPolicyDecision:
        base = self.validate_action_type(action_type)
        if not base.allowed:
            return base

        hay = " ".join([element_text, element_role, element_name, form_action, value or ""]).lower()
        for pattern in _BLOCKED_TEXT_PATTERNS:
            if re.search(pattern, hay):
                return ActionPolicyDecision(
                    allowed=False,
                    reason_code="BLOCKED_ACTION",
                    message=f"Read-only exploration blocked destructive control: {pattern.strip('\\\\b')}",
                )

        if self.read_only and action_type in {"click", "press", "submit"}:
            safe = any(re.search(p, hay) for p in _READ_ONLY_CLICK_PATTERNS)
            if element_role in {"link", "tab"}:
                safe = True
            if not safe:
                return ActionPolicyDecision(
                    allowed=False,
                    reason_code="BLOCKED_ACTION",
                    message="Read-only mode blocks mutating click/submit",
                )

        if self.read_only and action_type == "fill":
            if not any(k in hay for k in ("search", "sku", "find", "filter", "query", "textbox", "input")):
                return ActionPolicyDecision(
                    allowed=False,
                    reason_code="BLOCKED_ACTION",
                    message="Read-only mode allows fill only on search/filter inputs",
                )

        if form_action:
            for pattern in _BLOCKED_FORM_PATTERNS:
                if re.search(pattern, form_action.lower()):
                    return ActionPolicyDecision(
                        allowed=False,
                        reason_code="BLOCKED_ACTION",
                        message=f"Form action blocked by policy: {form_action}",
                    )
        return ActionPolicyDecision(True, "policy.ok", "Interaction permitted")

    def validate_stagehand_proposal(self, proposal: dict[str, object]) -> ActionPolicyDecision:
        action = str(proposal.get("action") or proposal.get("type") or "observe")
        target = str(proposal.get("target") or proposal.get("selector") or proposal.get("description") or "")
        return self.validate_interaction(action_type=action, element_text=target, element_name=target)
