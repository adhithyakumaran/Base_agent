"""Ground Truth helpers for Phase B validation."""

from __future__ import annotations

from typing import Any


def goal_matches_gt(goal: str, fact: dict[str, Any]) -> bool:
    subjects = [
        str(fact.get("subject", "")),
        str(fact.get("id", "")),
        " ".join(str(t) for t in fact.get("tags", [])),
    ]
    g = goal.lower()
    return any(s and s.lower() in g for s in subjects)


def evaluate_gt_expectations(
    fact: dict[str, Any],
    execution_ok: bool,
    observation_meta: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """Return (passed, failure_reasons) from structured GT expectations only."""
    expectations = fact.get("expectations") or {}
    failures: list[str] = []

    if expectations.get("execution_ok") is True and not execution_ok:
        failures.append("execution_ok expected true")

    min_passed = expectations.get("min_passed_tests")
    if isinstance(min_passed, int) and min_passed > 0:
        passed = _count_passed_tests(observation_meta)
        if passed < min_passed:
            failures.append(f"min_passed_tests expected >= {min_passed}, got {passed}")

    return (len(failures) == 0, failures)


def _count_passed_tests(observation_meta: list[dict[str, Any]]) -> int:
    total = 0
    for meta in observation_meta:
        report = meta.get("playwright_report") or {}
        stats = report.get("stats") or {}
        expected = stats.get("expected")
        if isinstance(expected, int):
            total += expected
    return total
