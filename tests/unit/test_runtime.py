from base_agent.api import build_default_runtime
from base_agent.contracts.enums import Conclusion
from base_agent.contracts.models import RunBudget
from base_agent.ground_truth.protocol import GroundTruthFact
from base_agent.tools.registry import ExecutionContext


def test_echo_zero_llm(runtime):
    result = runtime.run("echo hello world")
    assert result.conclusion == Conclusion.UNKNOWN or result.conclusion == Conclusion.PASS or result.tool_calls >= 1
    # Echo has no GT — should not invent PASS; observation insufficient → UNKNOWN
    assert result.conclusion in {Conclusion.UNKNOWN, Conclusion.INSUFFICIENT_EVIDENCE}
    assert result.llm_calls == 0
    assert result.tool_calls == 1


def test_banner_expected_absence_pass(runtime):
    # Direct tool + GT path via goal that maps? Use runtime executor path through custom goal entities
    # Invoke banner tool by capability hint using raw API state is heavy; call observation via tool registry
    from base_agent.contracts.models import Goal
    from base_agent.routing.hybrid import HybridRouter

    # Manually execute banner tool through executor used by runtime
    tool = runtime.registry.get("mock.demo.banner_observe")
    raw = tool.execute({"visible": False}, ExecutionContext(run_id="t", permissions=runtime.permissions))
    report = runtime.gt.validate(
        "promo.banner.visibility",
        raw.data,
        {"local_time": "21:00"},
    )
    assert report.outcome == "pass"
    assert report.reason_code == "expected_absence"


def test_no_loop_until_success_budget():
    from base_agent.api import AgentRuntime
    from plugins.mock_demo.tools import register_mock_demo
    from base_agent.tools.registry import ToolRegistry

    reg = ToolRegistry()
    register_mock_demo(reg)
    rt = AgentRuntime(registry=reg, budget=RunBudget(max_steps=3, max_tool_calls=2, max_llm_calls=0))
    result = rt.run("do something completely unknown and vague please")
    assert result.conclusion in {
        Conclusion.UNKNOWN,
        Conclusion.INSUFFICIENT_EVIDENCE,
        Conclusion.BLOCKED,
    }
    assert result.steps <= 5
    assert result.llm_calls == 0


def test_discover_uses_kb(runtime):
    result = runtime.run("discover the application map")
    assert result.tool_calls >= 1
    assert result.llm_calls == 0
    # Without business GT, discovery completes honestly
    assert result.conclusion in {Conclusion.UNKNOWN, Conclusion.INSUFFICIENT_EVIDENCE, Conclusion.PASS}


def test_tool_registry_rejects_duplicate():
    from base_agent.tools.registry import ToolRegistry
    from plugins.mock_demo.tools import EchoTool

    reg = ToolRegistry()
    reg.register(EchoTool())
    try:
        reg.register(EchoTool())
        assert False, "expected duplicate error"
    except ValueError:
        pass


def test_gt_record_requires_approved():
    from base_agent.ground_truth.protocol import InMemoryGroundTruthProvider

    gt = InMemoryGroundTruthProvider()
    try:
        gt.record_approved_result(
            GroundTruthFact(
                id="x",
                subject="s",
                predicate="equals",
                expected=1,
                authority="candidate",
            )
        )
        assert False
    except ValueError:
        pass