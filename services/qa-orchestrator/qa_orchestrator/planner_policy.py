"""Risk and destructive-action policy guards for the QA planner."""

from __future__ import annotations

import re
from dataclasses import dataclass

from qa_orchestrator.models import RiskLevel

_DESTRUCTIVE_PATTERNS = (
    r"\bdelete\s+all\b",
    r"\bremove\s+all\b",
    r"\bdrop\s+(table|database|schema)\b",
    r"\btruncate\b",
    r"\bwipe\b",
    r"\bdestroy\b",
    r"\bpurge\b",
    r"\berase\s+all\b",
)

_HIGH_RISK_FLOW_PREFIXES = (
    "BF-ADMINISTRATION-",
    "BF-MANUAL-INVOICE-",
)

_MEDIUM_RISK_KEYWORDS = (
    "account",
    "invoice",
    "billing",
    "checkout",
    "payment",
    "admin",
    "administration",
)


@dataclass(frozen=True)
class PolicyDecision:
    risk_level: RiskLevel
    blocked: bool
    ask_user: bool
    reason_code: str
    message: str


class PlannerPolicy:
    """Deterministic policy layer — LLM proposals must pass these guards."""

    def evaluate_request(self, goal: str) -> PolicyDecision:
        g = goal.lower()
        for pattern in _DESTRUCTIVE_PATTERNS:
            if re.search(pattern, g):
                if re.search(r"\b(with\s+approval|authorized|explicit\s+authorization)\b", g):
                    return PolicyDecision(
                        risk_level="HIGH",
                        blocked=False,
                        ask_user=True,
                        reason_code="policy.destructive_requires_authorization",
                        message="Destructive action requires explicit human authorization",
                    )
                return PolicyDecision(
                    risk_level="BLOCKED",
                    blocked=True,
                    ask_user=False,
                    reason_code="policy.destructive_blocked",
                    message="Destructive or data-mutation request blocked by policy",
                )
        return PolicyDecision(
            risk_level="LOW",
            blocked=False,
            ask_user=False,
            reason_code="policy.ok",
            message="Request passes baseline policy checks",
        )

    def evaluate_flow(self, flow_id: str, goal: str) -> RiskLevel:
        g = goal.lower()
        if any(flow_id.startswith(prefix) for prefix in _HIGH_RISK_FLOW_PREFIXES):
            return "HIGH"
        if any(k in g for k in _MEDIUM_RISK_KEYWORDS):
            return "MEDIUM"
        if "admin" in g or "invoice" in g:
            return "HIGH"
        return "LOW"

    def aggregate_risk(self, *levels: RiskLevel) -> RiskLevel:
        order = {"BLOCKED": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        if not levels:
            return "LOW"
        return max(levels, key=lambda lv: order.get(lv, 0))
