"""Unit tests for APEX crawler helpers and QA tools (no live UAT)."""

from plugins.qa_apex.crawler.engine import ApexCrawler, CrawlConfig
from plugins.qa_apex.crawler.selectors import normalize_page_key, parse_apex_url, with_session
from plugins.qa_apex.rules import evaluate_technical_rules, technical_outcome
from plugins.qa_apex.tools import ApexDiscoverTool, ApexFlowCatalogTool, load_kb_docs_from_dir, register_qa_apex
from base_agent.knowledge.protocol import InMemoryKnowledgeProvider
from base_agent.tools.registry import ExecutionContext, ToolRegistry


def test_parse_friendly_url_session():
    url = "https://dev-ea.example.com/ords/r/tjdcom/ea/home?session=12345&cs=abc"
    p = parse_apex_url(url)
    assert p.workspace == "tjdcom"
    assert p.app_alias == "ea"
    assert p.page_alias == "home"
    assert p.session == "12345"
    assert normalize_page_key(url) == "ea/home"
    assert "session=12345" in with_session("https://dev-ea.example.com/ords/r/tjdcom/ea/find-price", "12345")


def test_crawler_dry_run_no_browser():
    report = ApexCrawler(CrawlConfig(dry_run=True)).run()
    assert report.ok
    assert report.mode == "dry_run"
    assert report.stats.get("pages") == 0
    assert "rule.anti_stuck.same_url" in report.rules


def test_technical_rules_error_page():
    checks = evaluate_technical_rules({"body_text": "ORA-01403 no data found", "pages": [], "stats": {}})
    assert technical_outcome(checks) == "fail"
    assert any(c["id"] == "rule.apex.error_page" and c["outcome"] == "fail" for c in checks)


def test_discover_kb_snapshot_includes_patterns():
    kb = InMemoryKnowledgeProvider()
    n = load_kb_docs_from_dir(kb, "discovery/uat_ea/kb")
    assert n >= 10
    tool = ApexDiscoverTool(kb)
    raw = tool.execute({"mode": "kb_snapshot", "max_pages": 40}, ExecutionContext(run_id="t", permissions=[]))
    assert raw.ok
    assert raw.data["mode"] == "kb_snapshot"
    assert raw.data["stats"]["pages"] >= 1
    assert raw.data["stats"]["flow_patterns"] >= 1


def test_flow_catalog_tool():
    kb = InMemoryKnowledgeProvider()
    load_kb_docs_from_dir(kb, "discovery/uat_ea/kb")
    tool = ApexFlowCatalogTool(kb)
    raw = tool.execute({}, ExecutionContext(run_id="t", permissions=[]))
    assert raw.ok
    assert raw.data["stats"]["flows"] >= 1
    assert raw.data["stats"]["flow_patterns"] >= 1


def test_register_qa_apex_tools():
    reg = ToolRegistry()
    register_qa_apex(reg)
    names = {t.name for t in reg.list()}
    assert "qa.apex.discover" in names
    assert "qa.apex.sanity_probe" in names
    assert "qa.apex.flow_catalog" in names


def test_runtime_flow_catalog(runtime):
    result = runtime.run("list application flows")
    assert result.llm_calls == 0
    assert result.tool_calls >= 1
    assert result.conclusion.value in {"UNKNOWN", "INSUFFICIENT_EVIDENCE", "PASS", "FAIL", "BLOCKED"}
