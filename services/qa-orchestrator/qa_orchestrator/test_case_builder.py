"""Build deterministic GeneratedTestCase from scenario and exploration evidence."""

from __future__ import annotations

from qa_orchestrator.models import GeneratedTestCase, TestCaseStep, TestScenario


def build_test_case(scenario: TestScenario) -> GeneratedTestCase:
    suffix = {"positive": "P", "negative": "N", "parameterized": "P", "mixed": "P"}.get(
        scenario.polarity, "P"
    )
    test_case_id = f"TC-{scenario.flow_id}-{suffix}01-GEN"
    if scenario.polarity == "parameterized" and "sku" in scenario.test_data:
        test_case_id = f"TC-PARAM-SKU-GEN"

    steps = _build_steps(scenario)
    expected = scenario.expected_outcomes[0] if scenario.expected_outcomes else scenario.objective

    return GeneratedTestCase(
        test_case_id=test_case_id,
        flow_id=scenario.flow_id,
        scenario_id=scenario.scenario_id,
        title=scenario.title,
        polarity=scenario.polarity,
        preconditions=scenario.preconditions,
        test_data=scenario.test_data,
        steps=steps,
        expected=expected,
        status="DRAFT",
    )


def _build_steps(scenario: TestScenario) -> list[TestCaseStep]:
    steps: list[TestCaseStep] = []
    if any("authenticated" in p.lower() for p in scenario.preconditions):
        steps.append(
            TestCaseStep(
                step_id="step-001",
                action="authenticate",
                target="authenticated session",
                expected="User reaches home page",
                evidence_required=True,
            )
        )
        idx = 2
    else:
        idx = 1

    if scenario.flow_id != "BF-LOGIN-001":
        steps.append(
            TestCaseStep(
                step_id=f"step-{idx:03d}",
                action="navigate",
                target=f"{scenario.flow_id} entry page",
                expected="Target page loads",
                evidence_required=True,
            )
        )
        idx += 1

    if "sku" in scenario.test_data or scenario.polarity == "parameterized":
        steps.extend(
            [
                TestCaseStep(
                    step_id=f"step-{idx:03d}",
                    action="fill",
                    target="SKU input",
                    input=scenario.test_data.get("sku", "QA_PARAM_SKU"),
                    expected="SKU value accepted",
                    evidence_required=True,
                ),
                TestCaseStep(
                    step_id=f"step-{idx + 1:03d}",
                    action="click",
                    target="Search button",
                    expected="Search submitted",
                    evidence_required=True,
                ),
                TestCaseStep(
                    step_id=f"step-{idx + 2:03d}",
                    action="assert",
                    target="Product results region",
                    expected="Matching product result is displayed",
                    evidence_required=True,
                ),
            ]
        )
    elif "filter" in scenario.objective.lower() or any("filter" in a.lower() for a in scenario.actions):
        steps.extend(
            [
                TestCaseStep(
                    step_id=f"step-{idx:03d}",
                    action="inspect",
                    target="Product search filter controls",
                    expected="Filter controls are visible",
                    evidence_required=True,
                ),
                TestCaseStep(
                    step_id=f"step-{idx + 1:03d}",
                    action="click",
                    target="Filter control",
                    expected="Filter applies without data mutation",
                    evidence_required=True,
                ),
                TestCaseStep(
                    step_id=f"step-{idx + 2:03d}",
                    action="assert",
                    target="Filtered product results",
                    expected="Filtered results region reflects applied filter",
                    evidence_required=True,
                ),
            ]
        )
    else:
        steps.append(
            TestCaseStep(
                step_id=f"step-{idx:03d}",
                action="assert",
                target=scenario.flow_id,
                expected=scenario.expected_outcomes[0] if scenario.expected_outcomes else scenario.objective,
                evidence_required=True,
            )
        )
    return steps
