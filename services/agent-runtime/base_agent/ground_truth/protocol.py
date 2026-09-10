from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class GroundTruthFact(BaseModel):
    id: str
    version: str = "1.0.0"
    subject: str
    predicate: str
    expected: Any
    applies_when: dict[str, Any] = Field(default_factory=dict)
    authority: str = "approved"
    compare_mode: str = "equals"  # equals|exists|not_exists|expr|contains
    meta: dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    outcome: str  # pass|fail|not_applicable|insufficient
    expected: Any = None
    actual: Any = None
    reason_code: str
    gt_id: str | None = None


class ProviderMetadata(BaseModel):
    name: str
    version: str = "0.1.0"
    backend: str = "memory"


class GroundTruthProvider(Protocol):
    def get_expected(self, subject: str, context: dict[str, Any]) -> GroundTruthFact | None: ...

    def validate(self, subject: str, actual: Any, context: dict[str, Any]) -> ValidationReport: ...

    def metadata(self) -> ProviderMetadata: ...

    def record_approved_result(self, fact: GroundTruthFact) -> None: ...


def _applies(fact: GroundTruthFact, context: dict[str, Any]) -> bool:
    for k, v in fact.applies_when.items():
        if context.get(k) != v:
            return False
    return True


def _compare(fact: GroundTruthFact, actual: Any) -> ValidationReport:
    mode = fact.compare_mode
    if mode == "equals":
        ok = actual == fact.expected
        return ValidationReport(
            outcome="pass" if ok else "fail",
            expected=fact.expected,
            actual=actual,
            reason_code="gt.equals" if ok else "gt.mismatch",
            gt_id=fact.id,
        )
    if mode == "exists":
        ok = actual is not None and actual != ""
        return ValidationReport(
            outcome="pass" if ok else "fail",
            expected="exists",
            actual=actual,
            reason_code="gt.exists" if ok else "gt.missing",
            gt_id=fact.id,
        )
    if mode == "contains":
        ok = fact.expected in (actual or [])
        return ValidationReport(
            outcome="pass" if ok else "fail",
            expected=fact.expected,
            actual=actual,
            reason_code="gt.contains" if ok else "gt.not_contains",
            gt_id=fact.id,
        )
    if mode == "expr" and isinstance(fact.expected, dict) and "start" in fact.expected and "end" in fact.expected:
        # banner-style visibility window helper: expected dict + actual bool visible
        # context must provide local_time "HH:MM"
        return ValidationReport(
            outcome="insufficient",
            expected=fact.expected,
            actual=actual,
            reason_code="gt.expr_needs_helper",
            gt_id=fact.id,
        )
    return ValidationReport(
        outcome="insufficient",
        expected=fact.expected,
        actual=actual,
        reason_code="gt.unsupported_compare",
        gt_id=fact.id,
    )


class InMemoryGroundTruthProvider:
    def __init__(self) -> None:
        self._facts: dict[str, GroundTruthFact] = {}

    def load_many(self, facts: list[GroundTruthFact]) -> None:
        for f in facts:
            self._facts[f.id] = f

    def get_expected(self, subject: str, context: dict[str, Any]) -> GroundTruthFact | None:
        for fact in self._facts.values():
            if fact.subject == subject and _applies(fact, context):
                return fact
        return None

    def validate(self, subject: str, actual: Any, context: dict[str, Any]) -> ValidationReport:
        fact = self.get_expected(subject, context)
        if fact is None:
            return ValidationReport(outcome="insufficient", actual=actual, reason_code="gt.missing")
        # special-case time window visibility
        if fact.predicate == "visible_between" and isinstance(fact.expected, dict):
            local_time = context.get("local_time")
            if not local_time:
                return ValidationReport(
                    outcome="insufficient",
                    expected=fact.expected,
                    actual=actual,
                    reason_code="gt.missing_clock",
                    gt_id=fact.id,
                )
            start, end = fact.expected.get("start"), fact.expected.get("end")
            in_window = start <= local_time <= end
            expected_visible = in_window
            actual_visible = bool(actual.get("visible")) if isinstance(actual, dict) else bool(actual)
            ok = actual_visible == expected_visible
            reason = "expected_presence" if expected_visible else "expected_absence"
            return ValidationReport(
                outcome="pass" if ok else "fail",
                expected={"visible": expected_visible, "window": fact.expected},
                actual={"visible": actual_visible, "local_time": local_time},
                reason_code=reason if ok else "gt.visibility_mismatch",
                gt_id=fact.id,
            )
        return _compare(fact, actual)

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(name="in_memory_gt", backend="memory")

    def record_approved_result(self, fact: GroundTruthFact) -> None:
        if fact.authority != "approved":
            raise ValueError("only approved facts may be recorded")
        self._facts[fact.id] = fact


class NullGroundTruthProvider:
    def get_expected(self, subject: str, context: dict[str, Any]) -> GroundTruthFact | None:
        return None

    def validate(self, subject: str, actual: Any, context: dict[str, Any]) -> ValidationReport:
        return ValidationReport(outcome="insufficient", actual=actual, reason_code="gt.provider_null")

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(name="null_gt", backend="null")

    def record_approved_result(self, fact: GroundTruthFact) -> None:
        raise RuntimeError("null provider cannot record GT")