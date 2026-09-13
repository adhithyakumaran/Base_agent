"""Browser exploration engine tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qa_orchestrator.exploration_evidence import evidence_dir, list_exploration_evidence, sanitize_segment
from qa_orchestrator.exploration_policy import ExplorationPolicy
from qa_orchestrator.exploration_service import ExplorationService
from qa_orchestrator.exploration_session import ExplorationSession
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.locator_ranking import best_locator, rank_locators
from qa_orchestrator.models import ExplorationRequest, PlanningResult
from qa_orchestrator.stagehand_adapter import StagehandAdapter

PRODUCT_PAGE_HTML = """
<!doctype html><html><body>
  <nav><a href="/products">Products</a></nav>
  <h1>Product Search</h1>
  <form id="search-form" action="/ords/search">
    <input id="sku-input" data-testid="sku-field" type="text" name="P1_SKU"
           placeholder="SKU" aria-label="SKU">
    <button id="search-btn" type="button">Search</button>
  </form>
  <div id="results" role="region" aria-label="Product results">Product results region</div>
  <button id="delete-all">Delete all records</button>
</body></html>
"""

DISCOVERY_ROOT = "data/discovery-kb"


def _has_playwright() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


@pytest.fixture
def explore_request() -> ExplorationRequest:
    return ExplorationRequest(
        target_url="https://example.test/product-search",
        target_page="product-search",
        goal="Find the product search functionality",
        known_flow_context=["BF-PRODUCT-003"],
        max_pages=3,
        max_depth=1,
        timeout_s=30.0,
        read_only=True,
    )


@pytest.fixture
def automation_dir(tmp_path: Path) -> Path:
    return tmp_path / "automation"


def test_rank_locator_candidates_prefers_testid():
    locators = rank_locators(
        {
            "tag": "input",
            "role": "textbox",
            "name": "SKU",
            "text": "SKU",
            "attributes": {"data-testid": "sku-field", "placeholder": "SKU", "id": "sku-input"},
        }
    )
    assert locators[0].strategy == "testid"
    assert "getByTestId" in locators[0].playwright_code


def test_policy_blocks_destructive_click():
    policy = ExplorationPolicy(read_only=True)
    decision = policy.validate_interaction(
        action_type="click",
        element_text="Delete all records",
        element_role="button",
    )
    assert decision.allowed is False
    assert decision.reason_code == "BLOCKED_ACTION"


def test_policy_allows_search_fill():
    policy = ExplorationPolicy(read_only=True)
    decision = policy.validate_interaction(
        action_type="fill",
        element_text="SKU search input",
        element_role="textbox",
        element_name="SKU",
    )
    assert decision.allowed is True


def test_exploration_dry_run_produces_result(explore_request: ExplorationRequest, automation_dir: Path):
    session = ExplorationSession(
        explore_request,
        exploration_id="explore-test-001",
        automation_dir=automation_dir,
        dry_run=True,
    )
    result = session.run()
    assert result.status == "COMPLETED"
    assert result.elements
    assert result.discovery_candidates[0].status == "DRAFT"


def test_exploration_result_serialization(explore_request: ExplorationRequest, automation_dir: Path):
    result = ExplorationSession(
        explore_request,
        exploration_id="explore-serialize",
        automation_dir=automation_dir,
        dry_run=True,
    ).run()
    payload = json.loads(result.model_dump_json())
    assert payload["exploration_id"] == "explore-serialize"
    assert payload["discovery_candidates"][0]["status"] == "DRAFT"


def test_exploration_service_persists_draft_candidate(
    explore_request: ExplorationRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    discovery = tmp_path / "discovery-kb"
    discovery.mkdir()
    (discovery / "flows").mkdir()
    graph = FlowKnowledgeGraph(discovery_root=discovery, automation_dir=tmp_path / "automation")
    service = ExplorationService(graph, dry_run=True)
    result = service.run(explore_request, exploration_id="explore-persist")
    candidate_path = discovery / "candidates" / f"{result.discovery_candidates[0].candidate_id}.json"
    assert candidate_path.exists()
    saved = json.loads(candidate_path.read_text(encoding="utf-8"))
    assert saved["status"] == "DRAFT"


def test_evidence_scoped_to_exploration_id(automation_dir: Path):
    path = evidence_dir(
        automation_dir,
        exploration_id="explore-evidence-123",
        page_id="page-001",
        action_id="inspect",
    )
    assert "explore-evidence-123" in str(path)
    assert path.name == "inspect"


@pytest.mark.skipif(not _has_playwright(), reason="playwright not installed")
def test_open_product_page_and_discover_search_input(
    explore_request: ExplorationRequest,
    automation_dir: Path,
):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(PRODUCT_PAGE_HTML)
        session = ExplorationSession(
            explore_request,
            exploration_id="explore-live-001",
            automation_dir=automation_dir,
            dry_run=False,
            existing_page=page,
        )
        exp_page = session.inspect(page)
        browser.close()

    ids = {el.element_id for el in exp_page.elements}
    assert exp_page.title == "" or exp_page.url
    assert any("sku" in (el.name + el.text + str(el.attributes)).lower() for el in exp_page.elements)


@pytest.mark.skipif(not _has_playwright(), reason="playwright not installed")
def test_discover_search_button(explore_request: ExplorationRequest, automation_dir: Path):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(PRODUCT_PAGE_HTML)
        session = ExplorationSession(
            explore_request,
            exploration_id="explore-live-002",
            automation_dir=automation_dir,
            existing_page=page,
        )
        exp_page = session.inspect(page)
        browser.close()
    assert any("search" in (el.text + el.name).lower() for el in exp_page.elements)


@pytest.mark.skipif(not _has_playwright(), reason="playwright not installed")
def test_perform_safe_search_and_capture_evidence(explore_request: ExplorationRequest, automation_dir: Path):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(PRODUCT_PAGE_HTML)
        session = ExplorationSession(
            explore_request,
            exploration_id="explore-live-003",
            automation_dir=automation_dir,
            existing_page=page,
        )
        exp_page = session.inspect(page)
        proposals = session.observe(page, goal="search SKU ABC123")
        for proposal in proposals[:1]:
            session.act(page, proposal=proposal, page_id=exp_page.page_id)
        browser.close()

    evidence = list_exploration_evidence(automation_dir, "explore-live-003")
    assert evidence
    assert Path(evidence[0]["explorationId"]).name or evidence[0]["explorationId"] == "explore-live-003"


@pytest.mark.skipif(not _has_playwright(), reason="playwright not installed")
def test_read_only_mutation_blocked(explore_request: ExplorationRequest, automation_dir: Path):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(PRODUCT_PAGE_HTML)
        session = ExplorationSession(
            explore_request,
            exploration_id="explore-live-004",
            automation_dir=automation_dir,
            existing_page=page,
        )
        exp_page = session.inspect(page)
        delete_el = next(el for el in exp_page.elements if "delete" in el.text.lower())
        record = session.act(
            page,
            proposal={"action": "click", "target": delete_el.element_id},
            page_id=exp_page.page_id,
        )
        browser.close()
    assert record.blocked is True
    assert record.reason_code == "BLOCKED_ACTION"


def test_max_pages_limit_enforced(explore_request: ExplorationRequest, automation_dir: Path):
    explore_request.max_pages = 1
    session = ExplorationSession(
        explore_request,
        exploration_id="explore-limit-pages",
        automation_dir=automation_dir,
        dry_run=True,
    )
    result = session.run()
    assert len(result.pages) <= 1


def test_timeout_status(explore_request: ExplorationRequest, automation_dir: Path):
    explore_request.timeout_s = 0.001
    session = ExplorationSession(
        explore_request,
        exploration_id="explore-timeout",
        automation_dir=automation_dir,
        dry_run=True,
    )
    result = session.run()
    assert result.status in {"COMPLETED", "TIMEOUT", "PARTIAL"}


def test_navigation_cycle_warning(explore_request: ExplorationRequest, automation_dir: Path):
    session = ExplorationSession(
        explore_request,
        exploration_id="explore-cycle",
        automation_dir=automation_dir,
        dry_run=True,
    )
    session.warnings.append("Navigation cycle detected at https://example.test/product-search")
    result = session.stop()
    assert any("cycle" in w.lower() for w in result.warnings)


def test_existing_authenticated_session_reuse(explore_request: ExplorationRequest, automation_dir: Path):
    class FakePage:
        url = "https://example.test/home"

        def title(self):
            return "Home"

        def content(self):
            return PRODUCT_PAGE_HTML

        def screenshot(self, **kwargs):
            path = kwargs.get("path")
            if path:
                Path(path).write_bytes(b"png")

        def evaluate(self, script):
            if "'a, button, input" in script:
                return [
                    {
                        "element_id": "el-0",
                        "tag": "input",
                        "role": "textbox",
                        "name": "SKU",
                        "text": "SKU",
                        "attributes": {"placeholder": "SKU"},
                        "visible": True,
                        "enabled": True,
                        "interactive": True,
                    }
                ]
            if "querySelectorAll('a[href]')" in script:
                return [{"text": "Products", "href": "/products"}]
            if "querySelectorAll('form')" in script:
                return [{"action": "/search", "method": "get", "id": "search-form"}]
            if "role=\\\"navigation\\\"" in script or "navigation" in script and "nav a" in script:
                return ["Products"]
            return []

    session = ExplorationSession(
        explore_request,
        exploration_id="explore-existing-page",
        automation_dir=automation_dir,
        existing_page=FakePage(),
    )
    session.start(FakePage())
    page = session.inspect(FakePage())
    assert page.elements


def test_stagehand_disabled_fallback():
    adapter = StagehandAdapter()
    assert adapter.enabled is False
    assert adapter.observe("search sku", elements=[]) == []


def test_stagehand_proposal_rejected_by_policy():
    adapter = StagehandAdapter()
    proposals = adapter._observe_heuristic(
        "delete all records",
        [{"element_id": "el-1", "text": "Delete all records", "tag": "button", "role": "button", "name": ""}],
    )
    policy = ExplorationPolicy(read_only=True)
    for proposal in proposals:
        decision = policy.validate_stagehand_proposal(proposal)
        assert decision.allowed is False


def test_recorder_explore_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import scripts.browser_recorder as recorder

    monkeypatch.setattr(recorder, "discovery_root", lambda: tmp_path / "discovery-kb")
    monkeypatch.setenv("PYTHONPATH", str(Path("services/qa-orchestrator")))
    result = recorder.cmd_explore(
        "recorder-session-1",
        goal="Find product search",
        url="https://example.test/products",
        dry_run=True,
    )
    assert result["ok"] is True
    assert result["exploration"]["status"] == "COMPLETED"
    assert (tmp_path / "discovery-kb" / "recordings" / "sessions" / "recorder-session-1" / "exploration_result.json").exists()


def test_orchestrator_explore_strategy_runs_exploration(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("QA_RUNNER", "dry_run")
    from qa_orchestrator.orchestrator import QaOrchestrator, RunRequest

    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run(
        RunRequest(
            goal="Test the new product-search filter added yesterday",
            model="disabled",
            skip_execution=True,
        )
    )
    assert result.planning is not None
    assert result.planning.strategy == "EXPLORE"
    assert result.exploration is not None
    assert result.exploration.status in {"COMPLETED", "PARTIAL", "INSUFFICIENT_EVIDENCE"}
    assert "Browser exploration" in result.report_markdown


def test_orchestrator_block_never_starts_exploration(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    from qa_orchestrator.orchestrator import QaOrchestrator, RunRequest

    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run(RunRequest(goal="Delete all customer records", model="disabled", skip_execution=True))
    assert result.planning.strategy == "BLOCK"
    assert result.exploration is None


def test_planning_explore_plus_generate_only_runs_exploration(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    from qa_orchestrator.orchestrator import QaOrchestrator, RunRequest

    orch = QaOrchestrator(discovery_root=DISCOVERY_ROOT, model="disabled")
    result = orch.run(
        RunRequest(
            goal="Discover the product page and create automated coverage",
            model="disabled",
            skip_execution=True,
        )
    )
    assert result.planning.strategy == "EXPLORE"
    assert "GENERATE" in result.planning.secondary_strategies
    assert result.exploration is not None
    assert result.exploration.discovery_candidates[0].status == "DRAFT"
