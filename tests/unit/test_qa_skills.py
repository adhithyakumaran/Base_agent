"""Tests for enterprise QA skill tools."""

from base_agent.api import build_default_runtime
from base_agent.contracts.enums import Conclusion
from base_agent.tools.registry import ExecutionContext
from plugins.qa_apex.tools import load_kb_docs_from_dir, register_qa_apex
from base_agent.knowledge.protocol import InMemoryKnowledgeProvider
from base_agent.tools.registry import ToolRegistry


def test_health_check_skill(runtime):
    result = runtime.run("health check endless aisle")
    assert result.llm_calls == 0
    assert result.tool_calls >= 1
    assert result.conclusion in {
        Conclusion.UNKNOWN,
        Conclusion.INSUFFICIENT_EVIDENCE,
        Conclusion.FAIL,
        Conclusion.PASS,
    }


def test_component_probe_p6(runtime):
    result = runtime.run("component probe P6_SKU")
    assert result.llm_calls == 0
    assert result.tool_calls == 1


def test_flow_replay_find_price(runtime):
    result = runtime.run("replay flow find_price")
    assert result.llm_calls == 0
    assert result.tool_calls == 1


def test_login_probe(runtime):
    result = runtime.run("login probe")
    assert result.llm_calls == 0


def test_report_bundle(runtime):
    result = runtime.run("assemble report bundle")
    assert result.llm_calls == 0


def test_all_qa_skills_registered():
    kb = InMemoryKnowledgeProvider()
    load_kb_docs_from_dir(kb, "discovery/uat_ea/kb")
    reg = ToolRegistry()
    register_qa_apex(reg, kb)
    names = {t.name for t in reg.list()}
    for required in {
        "qa.apex.discover",
        "qa.apex.sanity_probe",
        "qa.apex.flow_catalog",
        "qa.apex.health_check",
        "qa.apex.page_probe",
        "qa.apex.component_probe",
        "qa.apex.flow_replay",
        "qa.apex.login_probe",
        "qa.apex.report_bundle",
    }:
        assert required in names


def test_page_probe_tool_direct():
    kb = InMemoryKnowledgeProvider()
    load_kb_docs_from_dir(kb, "discovery/uat_ea/kb")
    reg = ToolRegistry()
    register_qa_apex(reg, kb)
    tool = reg.get("qa.apex.page_probe")
    raw = tool.execute({"page": "home"}, ExecutionContext(run_id="t", permissions=["tool.execute:qa.apex.*"]))
    assert raw.ok
    assert raw.data["found"] is True
