"""Controlled browser exploration session."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from qa_orchestrator.exploration_evidence import capture_evidence
from qa_orchestrator.exploration_policy import ExplorationPolicy
from qa_orchestrator.locator_ranking import best_locator, rank_locators
from qa_orchestrator.models import (
    DiscoveredElement,
    DiscoveryCandidate,
    ExplorationActionRecord,
    ExplorationEvidenceItem,
    ExplorationPage,
    ExplorationRequest,
    ExplorationResult,
    ExplorationStatus,
    LocatorCandidate,
)
from qa_orchestrator.stagehand_adapter import StagehandAdapter

_EXTRACT_ELEMENTS_JS = """
() => {
  const out = [];
  const nodes = document.querySelectorAll(
    'a, button, input, select, textarea, [role], form, table, nav, [data-testid]'
  );
  let idx = 0;
  for (const el of nodes) {
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') continue;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) continue;
    const tag = el.tagName ? el.tagName.toLowerCase() : 'node';
    const role = el.getAttribute('role')
      || (tag === 'a' ? 'link' : tag === 'button' ? 'button' : tag === 'input' ? 'textbox' : tag);
    const attrs = {};
    for (const name of ['id','name','type','placeholder','aria-label','title','data-testid','href','action']) {
      const v = el.getAttribute(name);
      if (v) attrs[name] = v;
    }
    out.push({
      element_id: `el-${idx++}`,
      tag,
      role,
      name: el.getAttribute('aria-label') || el.getAttribute('name') || el.getAttribute('placeholder') || '',
      text: (el.innerText || el.textContent || '').trim().slice(0, 160),
      attributes: attrs,
      visible: true,
      enabled: !el.disabled,
      interactive: ['a','button','input','select','textarea'].includes(tag) || !!el.getAttribute('role'),
    });
  }
  return out;
}
"""


class ExplorationSession:
    """Browser exploration lifecycle — does not generate Playwright specs."""

    def __init__(
        self,
        request: ExplorationRequest,
        *,
        exploration_id: str,
        automation_dir: Path,
        dry_run: bool = False,
        existing_page: Any | None = None,
        stagehand: StagehandAdapter | None = None,
    ) -> None:
        self.request = request
        self.exploration_id = exploration_id
        self.automation_dir = automation_dir
        self.dry_run = dry_run
        self.existing_page = existing_page
        self.stagehand = stagehand or StagehandAdapter()
        self.policy = ExplorationPolicy(
            read_only=request.read_only,
            allowed_actions=request.allowed_actions,
        )
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.deadline = time.monotonic() + request.timeout_s
        self.pages: list[ExplorationPage] = []
        self.elements: list[DiscoveredElement] = []
        self.actions: list[ExplorationActionRecord] = []
        self.evidence: list[ExplorationEvidenceItem] = []
        self.console_events: list[dict[str, Any]] = []
        self.network_events: list[dict[str, Any]] = []
        self.warnings: list[str] = []
        self.observations: list[str] = []
        self.business_signals: list[str] = []
        self.visited_urls: set[str] = set()
        self.page_signatures: set[str] = set()
        self.action_signatures: set[str] = set()
        self._page_counter = 0
        self._action_counter = 0
        self._console_buffer: list[dict[str, Any]] = []
        self._network_buffer: list[dict[str, Any]] = []

    def run(self) -> ExplorationResult:
        if self.dry_run:
            return self._dry_run_result()

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            return self._failed_result(f"playwright not installed: {exc}")

        status: ExplorationStatus = "COMPLETED"
        message = "Exploration completed"

        with sync_playwright() as pw:
            page = self.existing_page
            browser = None
            context = None
            if page is None:
                import os

                browser = pw.chromium.launch(
                    headless=os.environ.get("EA_HEADLESS", "true").lower() == "true"
                )
                context = browser.new_context()
                page = context.new_page()
                self._wire_listeners(page)

            try:
                self.start(page)
                if self._timed_out():
                    status = "TIMEOUT"
                    message = "Exploration timed out"
                else:
                    status = self._explore(page)
                    message = self._status_message(status)
            finally:
                if context is not None:
                    context.close()
                if browser is not None:
                    browser.close()

        return self._build_result(status=status, message=message)

    def start(self, page: Any) -> None:
        target = self.request.target_url
        if not target:
            raise ValueError("ExplorationRequest.target_url is required for live exploration")
        if self.existing_page is None:
            session = self._maybe_login(page)
            if session and not session.get("ok") and "login" in str(session.get("reason", "")):
                self.warnings.append(f"APEX login skipped/failed: {session.get('reason')}")
            if "login" not in target.lower() and page.url != target:
                page.goto(target, wait_until="domcontentloaded", timeout=60_000)
        self._record_navigation(page, depth=0)

    def inspect(self, page: Any, *, depth: int = 0) -> ExplorationPage:
        raw_elements = page.evaluate(_EXTRACT_ELEMENTS_JS)
        discovered: list[DiscoveredElement] = []
        for raw in raw_elements:
            locators = rank_locators(raw)
            el = DiscoveredElement(
                element_id=str(raw.get("element_id")),
                role=str(raw.get("role") or ""),
                name=str(raw.get("name") or ""),
                text=str(raw.get("text") or ""),
                tag=str(raw.get("tag") or ""),
                attributes={str(k): str(v) for k, v in (raw.get("attributes") or {}).items()},
                locator_candidates=locators,
                visible=bool(raw.get("visible", True)),
                enabled=bool(raw.get("enabled", True)),
                interactive=bool(raw.get("interactive", False)),
            )
            discovered.append(el)
            self.elements.append(el)

        links = page.evaluate(
            """() => Array.from(document.querySelectorAll('a[href]')).slice(0, 40).map(a => ({
              text: (a.innerText || a.textContent || '').trim().slice(0, 80),
              href: a.href
            }))"""
        )
        forms = page.evaluate(
            """() => Array.from(document.querySelectorAll('form')).slice(0, 10).map(f => ({
              action: f.getAttribute('action') || '',
              method: f.getAttribute('method') || 'get',
              id: f.id || ''
            }))"""
        )
        nav = page.evaluate(
            """() => Array.from(document.querySelectorAll('nav a, [role=\"navigation\"] a')).slice(0, 20)
              .map(a => (a.innerText || a.textContent || '').trim()).filter(Boolean)"""
        )

        self._page_counter += 1
        page_id = f"page-{self._page_counter:03d}"
        exp_page = ExplorationPage(
            page_id=page_id,
            url=page.url,
            title=page.title(),
            depth=depth,
            elements=discovered,
            forms=[dict(x) for x in forms],
            links=[dict(x) for x in links],
            navigation=[str(x) for x in nav],
        )
        self.pages.append(exp_page)
        self.observations.append(
            f"Inspected {len(discovered)} elements on {exp_page.title or exp_page.url}"
        )
        self.capture(page, page_id=page_id, action_id="inspect", label="inspect")
        return exp_page

    def observe(self, page: Any, *, goal: str) -> list[dict[str, Any]]:
        relevant = self._match_goal_elements(goal)
        proposals = [
            {
                "action": self._default_action_for(el),
                "target": el.element_id,
                "description": el.text or el.name or el.role,
                "source": "deterministic",
            }
            for el in relevant[:8]
        ]
        raw = [el.model_dump() for el in self.elements[-80:]]
        proposals.extend(self.stagehand.observe(goal, elements=raw))
        validated: list[dict[str, Any]] = []
        for proposal in proposals:
            decision = self.policy.validate_stagehand_proposal(proposal)
            if decision.allowed:
                validated.append(proposal)
            else:
                self.warnings.append(decision.message)
        return validated

    def act(self, page: Any, *, proposal: dict[str, Any], page_id: str) -> ExplorationActionRecord:
        self._action_counter += 1
        action_id = f"act-{self._action_counter:03d}"
        action_type = str(proposal.get("action") or "click")
        target_id = str(proposal.get("target") or "")
        element = self._element_by_id(target_id)
        element_text = (element.text if element else "") + " " + (element.name if element else "")
        element_role = element.role if element else ""
        decision = self.policy.validate_interaction(
            action_type=action_type,
            element_text=element_text,
            element_role=element_role,
            element_name=element.name if element else "",
            value=str(proposal.get("value") or ""),
        )
        if not decision.allowed:
            record = ExplorationActionRecord(
                action_id=action_id,
                action_type=action_type,
                target_element_id=target_id or None,
                ok=False,
                blocked=True,
                reason_code=decision.reason_code,
                message=decision.message,
            )
            self.actions.append(record)
            return record

        signature = f"{action_type}:{target_id}:{proposal.get('value') or ''}"
        if signature in self.action_signatures:
            record = ExplorationActionRecord(
                action_id=action_id,
                action_type=action_type,
                target_element_id=target_id or None,
                ok=False,
                blocked=True,
                reason_code="exploration.cycle",
                message="Repeated identical action blocked",
            )
            self.actions.append(record)
            return record
        self.action_signatures.add(signature)

        locator = best_locator(element.locator_candidates) if element else None
        ok = True
        message = "Action performed"
        try:
            if element and locator:
                loc = self._resolve_locator(page, locator)
                if action_type == "fill":
                    loc.fill(str(proposal.get("value") or "TEST-SKU-001"))
                elif action_type in {"click", "press"}:
                    loc.click(timeout=5000)
            elif action_type == "scroll":
                page.mouse.wheel(0, 400)
        except Exception as exc:  # noqa: BLE001
            ok = False
            message = f"{type(exc).__name__}: {exc}"

        evidence = self.capture(page, page_id=page_id, action_id=action_id, label=action_type)
        record = ExplorationActionRecord(
            action_id=action_id,
            action_type=action_type,
            target_element_id=target_id or None,
            locator=locator.playwright_code if locator else None,
            value=str(proposal.get("value") or "") or None,
            ok=ok,
            blocked=False,
            message=message,
            evidence_paths=[p for p in [evidence.screenshot_path, evidence.dom_path] if p],
        )
        self.actions.append(record)
        return record

    def capture(
        self,
        page: Any,
        *,
        page_id: str,
        action_id: str,
        label: str,
    ) -> ExplorationEvidenceItem:
        item = capture_evidence(
            page,
            automation_dir=self.automation_dir,
            exploration_id=self.exploration_id,
            page_id=page_id,
            action_id=action_id,
            label=label,
            console_events=self._console_buffer[-20:],
            network_events=self._network_buffer[-20:],
        )
        self.evidence.append(item)
        self._console_buffer.clear()
        self._network_buffer.clear()
        return item

    def stop(self) -> ExplorationResult:
        return self._build_result(status="COMPLETED", message="Exploration stopped")

    def _explore(self, page: Any) -> ExplorationStatus:
        goal = self.request.goal.lower()
        exp_page = self.inspect(page, depth=0)
        proposals = self.observe(page, goal=self.request.goal)

        if any(k in goal for k in ("search", "sku", "product", "filter")):
            self._identify_search_controls(exp_page)

        performed = 0
        for proposal in proposals[:3]:
            if self._timed_out() or len(self.pages) >= self.request.max_pages:
                return "PARTIAL"
            record = self.act(page, proposal=proposal, page_id=exp_page.page_id)
            if record.blocked:
                continue
            performed += 1
            if record.ok and any(k in goal for k in ("search", "sku", "filter")):
                self.business_signals.append("Search/filter interaction observed")
                break

        if self.request.evidence_required and not self.evidence:
            return "INSUFFICIENT_EVIDENCE"
        if performed == 0 and proposals and all(a.blocked for a in self.actions):
            return "BLOCKED"
        if self._timed_out():
            return "TIMEOUT"
        if len(self.pages) >= self.request.max_pages:
            return "PARTIAL"
        return "COMPLETED"

    def _identify_search_controls(self, exp_page: ExplorationPage) -> None:
        for el in exp_page.elements:
            hay = f"{el.name} {el.text} {el.role} {el.tag}".lower()
            if any(k in hay for k in ("search", "sku", "find", "filter", "product")):
                self.business_signals.append(
                    f"Identified control: {el.tag} {el.name or el.text} → {best_locator(el.locator_candidates).playwright_code if el.locator_candidates else 'n/a'}"
                )

    def _match_goal_elements(self, goal: str) -> list[DiscoveredElement]:
        tokens = {t for t in goal.lower().replace("-", " ").split() if len(t) > 2}
        scored: list[tuple[int, DiscoveredElement]] = []
        for el in self.elements:
            hay = f"{el.name} {el.text} {el.role} {el.tag}".lower()
            score = sum(1 for t in tokens if t in hay)
            if el.tag in {"input", "button", "a"}:
                score += 1
            if score:
                scored.append((score, el))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [el for _, el in scored]

    def _default_action_for(self, el: DiscoveredElement) -> str:
        if el.tag == "input" or el.role == "textbox":
            return "fill"
        return "click"

    def _element_by_id(self, element_id: str) -> DiscoveredElement | None:
        for el in self.elements:
            if el.element_id == element_id:
                return el
        return None

    def _resolve_locator(self, page: Any, locator: LocatorCandidate) -> Any:
        if locator.strategy == "testid":
            test_id = locator.expression.split('"')[1]
            return page.get_by_test_id(test_id)
        if locator.strategy == "role":
            role = locator.expression.split("=")[1].split("[")[0]
            name = locator.expression.split("name=")[-1].rstrip("]")
            return page.get_by_role(role, name=name)
        if locator.strategy == "placeholder":
            ph = locator.expression.split("=", 1)[1]
            return page.get_by_placeholder(ph)
        if locator.strategy == "text":
            txt = locator.expression.split("=", 1)[1]
            return page.get_by_text(txt)
        return page.locator(locator.expression)

    def _record_navigation(self, page: Any, *, depth: int) -> None:
        url = page.url
        signature = hashlib.sha1(f"{url}|{page.title()}".encode()).hexdigest()
        if url in self.visited_urls or signature in self.page_signatures:
            self.warnings.append(f"Navigation cycle detected at {url}")
            return
        self.visited_urls.add(url)
        self.page_signatures.add(signature)

    def _wire_listeners(self, page: Any) -> None:
        page.on(
            "console",
            lambda msg: self._console_buffer.append({"level": msg.type, "text": msg.text[:500]}),
        )
        page.on(
            "request",
            lambda req: self._network_buffer.append(
                {"phase": "request", "url": req.url[:200], "method": req.method}
            ),
        )
        page.on(
            "response",
            lambda res: self._network_buffer.append(
                {"phase": "response", "url": res.url[:200], "status": res.status}
            ),
        )
        self.console_events.extend(self._console_buffer)
        self.network_events.extend(self._network_buffer)

    def _maybe_login(self, page: Any) -> dict[str, Any] | None:
        try:
            from plugins.qa_apex.crawler.session import login_apex, session_from_env

            cfg = session_from_env()
            if cfg is None:
                return None
            return login_apex(page, cfg)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "reason": str(exc)}

    def _timed_out(self) -> bool:
        return time.monotonic() >= self.deadline

    def _status_message(self, status: ExplorationStatus) -> str:
        return {
            "COMPLETED": "Exploration completed successfully",
            "PARTIAL": "Exploration stopped at page/depth limit",
            "BLOCKED": "Exploration blocked by read-only policy",
            "TIMEOUT": "Exploration timed out",
            "FAILED": "Exploration failed",
            "INSUFFICIENT_EVIDENCE": "Required evidence was not captured",
        }.get(status, status)

    def _build_result(self, *, status: ExplorationStatus, message: str) -> ExplorationResult:
        locators = []
        for el in self.elements:
            locators.extend(el.locator_candidates)
        candidate = DiscoveryCandidate(
            candidate_id=f"candidate-{self.exploration_id}",
            candidate_flow=self.request.known_flow_context[0] if self.request.known_flow_context else None,
            observed_page=self.request.target_page or (self.pages[0].title if self.pages else ""),
            elements=self.elements[:40],
            locators=locators[:40],
            actions=self.actions,
            possible_business_behavior=self.business_signals,
            evidence=self.evidence,
            confidence=0.75 if status == "COMPLETED" else 0.4,
            status="DRAFT",
        )
        return ExplorationResult(
            request_id=self.exploration_id,
            exploration_id=self.exploration_id,
            status=status,
            target_url=self.request.target_url,
            target_page=self.request.target_page,
            goal=self.request.goal,
            pages=self.pages,
            elements=self.elements,
            actions=self.actions,
            navigation=[{"url": p.url, "title": p.title} for p in self.pages],
            observations=self.observations,
            locators=locators[:50],
            screenshots=[e.screenshot_path for e in self.evidence if e.screenshot_path],
            dom_snapshots=[e.dom_path for e in self.evidence if e.dom_path],
            console_events=self.console_events,
            network_events=self.network_events,
            business_signals=self.business_signals,
            discovered_flows=list(self.request.known_flow_context),
            warnings=self.warnings,
            evidence=self.evidence,
            discovery_candidates=[candidate],
            started_at=self.started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            dry_run=self.dry_run,
            message=message,
        )

    def _dry_run_result(self) -> ExplorationResult:
        sample_element = DiscoveredElement(
            element_id="el-0",
            role="textbox",
            name="SKU",
            text="SKU",
            tag="input",
            attributes={"placeholder": "SKU", "name": "P1_SKU"},
            locator_candidates=rank_locators(
                {
                    "tag": "input",
                    "role": "textbox",
                    "name": "SKU",
                    "text": "SKU",
                    "attributes": {"placeholder": "SKU", "name": "P1_SKU"},
                }
            ),
            interactive=True,
        )
        page = ExplorationPage(
            page_id="page-001",
            url=self.request.target_url or "dry-run://product-search",
            title="Product Search (dry run)",
            elements=[sample_element],
            navigation=["Search", "Products"],
        )
        candidate = DiscoveryCandidate(
            candidate_id=f"candidate-{self.exploration_id}",
            candidate_flow=self.request.known_flow_context[0] if self.request.known_flow_context else None,
            observed_page=self.request.target_page or "product-search",
            elements=[sample_element],
            locators=sample_element.locator_candidates,
            possible_business_behavior=["Search input identified", "Search button identified"],
            confidence=0.5,
            status="DRAFT",
        )
        return ExplorationResult(
            request_id=self.exploration_id,
            exploration_id=self.exploration_id,
            status="COMPLETED",
            target_url=self.request.target_url,
            target_page=self.request.target_page,
            goal=self.request.goal,
            pages=[page],
            elements=[sample_element],
            observations=["Dry-run exploration — no browser launched"],
            locators=sample_element.locator_candidates,
            business_signals=["SKU search field", "Search button"],
            discovered_flows=list(self.request.known_flow_context),
            discovery_candidates=[candidate],
            started_at=self.started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            dry_run=True,
            message="Dry-run exploration completed",
        )

    def _failed_result(self, message: str) -> ExplorationResult:
        return ExplorationResult(
            request_id=self.exploration_id,
            exploration_id=self.exploration_id,
            status="FAILED",
            target_url=self.request.target_url,
            target_page=self.request.target_page,
            goal=self.request.goal,
            warnings=[message],
            started_at=self.started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            message=message,
        )
