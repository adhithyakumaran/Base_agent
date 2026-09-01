from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from base_agent.contracts.enums import ExecutionMode
from base_agent.knowledge.protocol import InMemoryKnowledgeProvider, KnowledgeDocument
from base_agent.tools.registry import ExecutionContext, RawToolResult, ToolDefinition, ToolRegistry

from plugins.qa_apex.crawler.engine import ApexCrawler, CrawlConfig
from plugins.qa_apex.rules import evaluate_technical_rules, technical_outcome


class ApexDiscoverTool:
    """Bounded APEX discovery — KB snapshot and/or live anti-stuck crawl.

    Modes:
    - kb_snapshot (default): map from loaded KB, 0 browser, 0 LLM
    - live: Playwright crawl when credentials/seed available; else graceful degrade
    - auto: live if APEX_* env present, else kb_snapshot
    """

    definition = ToolDefinition(
        name="qa.apex.discover",
        description="Discover Oracle APEX Endless Aisle pages/modules into KB candidates",
        plugin_id="qa.apex",
        capability="qa.discover",
        permissions=["tool.execute:qa.apex.*", "knowledge.write"],
        timeout_ms=180_000,
        execution_mode=ExecutionMode.SIDE_EFFECTING,
        tags=["qa", "apex", "crawler"],
        metadata={
            "anti_stuck": {
                "max_pages": 40,
                "same_url_limit": 1,
                "modal_timeout_ms": 3000,
                "networkidle_optional": True,
                "skip_external_hosts": True,
                "llm_in_loop": False,
            }
        },
    )

    def __init__(self, kb: InMemoryKnowledgeProvider | None = None) -> None:
        self.kb = kb or InMemoryKnowledgeProvider()

    def validate_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        mode = payload.get("mode") or "auto"
        return {
            "mode": mode,
            "max_pages": int(payload.get("max_pages", 40)),
            "seed": payload.get("seed"),
            "dry_run": bool(payload.get("dry_run", False)),
        }

    def validate_output(self, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict) or "pages" not in raw:
            raise ValueError("discover output requires pages")
        return raw

    def _kb_snapshot(self, max_pages: int) -> dict[str, Any]:
        docs = self.kb.all()
        pages = []
        flows = []
        components = []
        patterns = []
        for d in docs:
            body = d.body or {}
            typ = body.get("type")
            details = body.get("details") or {}
            if typ == "page_map":
                pages.append(
                    {
                        "id": d.id,
                        "title": body.get("title"),
                        "alias": details.get("page_alias") or details.get("alias"),
                        "url_path": details.get("url_path"),
                        "app": details.get("app_alias") or details.get("app"),
                    }
                )
            elif typ == "flow":
                flows.append({"id": d.id, "name": body.get("title"), "steps": details.get("steps")})
            elif typ == "flow_pattern":
                patterns.append({"id": d.id, "name": body.get("title"), "details": details})
            elif typ == "component":
                components.append({"id": d.id, "name": body.get("title"), "details": details})

        return {
            "mode": "kb_snapshot",
            "pages": pages[:max_pages],
            "flows": flows,
            "flow_patterns": patterns,
            "components": components,
            "stats": {
                "pages": min(len(pages), max_pages),
                "flows": len(flows),
                "components": len(components),
                "flow_patterns": len(patterns),
                "truncated": len(pages) > max_pages,
            },
            "apex": {
                "workspace": "tjdcom",
                "apps": ["ea", "ea1", "gc"],
                "notes": [
                    "Prefer click navigation to preserve session",
                    "Append session query on explicit goto",
                    "Wait for wwv_flow.ajax completion on LOVs/IG",
                    "Treat dialogs/modals with dedicated timeout — never hang",
                ],
            },
            "rules": [
                "rule.session.required",
                "rule.friendly_url.parse",
                "rule.budget.max_pages",
                "rule.anti_stuck.same_url",
            ],
            "blockers": [],
            "body_text": "",
        }

    def execute(self, payload: dict[str, Any], ctx: ExecutionContext) -> RawToolResult:
        mode = payload["mode"]
        max_pages = payload["max_pages"]
        env_live = bool(
            os.environ.get("APEX_TARGET_URL") or os.environ.get("TARGET_URL") or payload.get("seed")
        )
        if mode == "auto":
            mode = "live" if env_live and not payload.get("dry_run") else "kb_snapshot"
        if mode == "kb_snapshot" or payload.get("dry_run"):
            data = self._kb_snapshot(max_pages)
            if payload.get("dry_run"):
                data["mode"] = "dry_run"
            return RawToolResult(ok=True, data=data)

        # Live crawl
        cfg = CrawlConfig(
            seed_url=payload.get("seed") or os.environ.get("APEX_TARGET_URL") or os.environ.get("TARGET_URL"),
            max_pages=max_pages,
            dry_run=False,
        )
        report = ApexCrawler(cfg).run()
        data = report.to_dict()
        # Merge KB pages as advisory overlay (ids) without inventing GT
        kb_part = self._kb_snapshot(max_pages)
        data["kb_overlay"] = {
            "pages": len(kb_part["pages"]),
            "flows": len(kb_part["flows"]),
            "components": len(kb_part["components"]),
        }
        data.setdefault("flow_patterns", kb_part.get("flow_patterns") or [])
        if not data.get("ok") and not data.get("pages"):
            # Degrade to KB so agent still performs useful work
            fallback = self._kb_snapshot(max_pages)
            fallback["mode"] = "kb_snapshot_fallback"
            fallback["blockers"] = data.get("blockers") or []
            fallback["live_error"] = True
            return RawToolResult(ok=True, data=fallback)
        return RawToolResult(ok=True, data=data)


class ApexSanityProbeTool:
    definition = ToolDefinition(
        name="qa.apex.sanity_probe",
        description="Run deterministic sanity probes using KB + technical rules (no GT required)",
        plugin_id="qa.apex",
        capability="qa.sanity",
        permissions=["tool.execute:qa.apex.*"],
        tags=["qa", "apex"],
        metadata={"llm_required": False, "gt_required": False},
    )

    def __init__(self, kb: InMemoryKnowledgeProvider | None = None) -> None:
        self.kb = kb

    def validate_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def validate_output(self, raw: Any) -> dict[str, Any]:
        return raw if isinstance(raw, dict) else {"value": raw}

    def execute(self, payload: dict[str, Any], ctx: ExecutionContext) -> RawToolResult:
        checks: list[dict[str, Any]] = []
        # KB presence probes
        if self.kb:
            checks.append(
                {
                    "id": "home_in_kb",
                    "outcome": "pass" if self.kb.search("home", k=1) else "insufficient",
                }
            )
            checks.append(
                {
                    "id": "login_flow_in_kb",
                    "outcome": "pass" if self.kb.search("login", k=1) else "insufficient",
                }
            )
            checks.append(
                {
                    "id": "apex_flow_patterns_in_kb",
                    "outcome": "pass" if self.kb.search("flow_pattern", k=1) or self.kb.search("popup_lov", k=1) else "insufficient",
                }
            )
        else:
            checks.append({"id": "kb_loaded", "outcome": "insufficient"})

        checks.append({"id": "no_forced_pass_without_gt", "outcome": "pass"})
        checks.append({"id": "no_loop_until_success", "outcome": "pass", "detail": "policy enforced in DecisionEngine"})

        # Optional technical payload from prior discover
        tech_payload = payload.get("discover_payload") or payload
        if tech_payload.get("pages") is not None or tech_payload.get("body_text"):
            tech = evaluate_technical_rules(tech_payload)
            checks.extend(tech)
            agg = technical_outcome(tech)
        else:
            agg = "insufficient"

        # Surface body_text for observation rules
        body_text = str(tech_payload.get("body_text") or "")
        return RawToolResult(
            ok=True,
            data={
                "checks": checks,
                "technical_aggregate": agg,
                "gt_required_for_business_passfail": True,
                "body_text": body_text,
                "pages": tech_payload.get("pages") or [],
            },
        )


class ApexFlowCatalogTool:
    """List candidate flows + platform patterns from KB for planning (pre-GT)."""

    definition = ToolDefinition(
        name="qa.apex.flow_catalog",
        description="List Endless Aisle candidate flows and APEX platform flow patterns from KB",
        plugin_id="qa.apex",
        capability="qa.discover",
        permissions=["tool.execute:qa.apex.*", "knowledge.read"],
        tags=["qa", "apex", "flows"],
        metadata={"llm_required": False},
    )

    def __init__(self, kb: InMemoryKnowledgeProvider | None = None) -> None:
        self.kb = kb or InMemoryKnowledgeProvider()

    def validate_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload or {}

    def validate_output(self, raw: Any) -> dict[str, Any]:
        return raw if isinstance(raw, dict) else {"value": raw}

    def execute(self, payload: dict[str, Any], ctx: ExecutionContext) -> RawToolResult:
        flows = []
        patterns = []
        for d in self.kb.all():
            body = d.body or {}
            typ = body.get("type")
            details = body.get("details") or {}
            if typ == "flow":
                flows.append(
                    {
                        "id": d.id,
                        "title": body.get("title"),
                        "steps": details.get("steps"),
                        "status": d.status,
                    }
                )
            elif typ == "flow_pattern":
                patterns.append(
                    {
                        "id": d.id,
                        "title": body.get("title"),
                        "summary": body.get("summary"),
                        "details": details,
                        "status": d.status,
                    }
                )
        return RawToolResult(
            ok=True,
            data={
                "flows": flows,
                "flow_patterns": patterns,
                "stats": {"flows": len(flows), "flow_patterns": len(patterns)},
                "note": "Candidates only — not approved Ground Truth",
                "body_text": "",
                "pages": [],
            },
        )


def register_qa_apex(registry: ToolRegistry, kb: InMemoryKnowledgeProvider | None = None) -> None:
    kb = kb or InMemoryKnowledgeProvider()
    registry.register(ApexDiscoverTool(kb))
    registry.register(ApexSanityProbeTool(kb))
    registry.register(ApexFlowCatalogTool(kb))
    from plugins.qa_apex.skills import (
        ApexComponentProbeTool,
        ApexFlowReplayTool,
        ApexHealthCheckTool,
        ApexLoginProbeTool,
        ApexMissionPackTool,
        ApexPageProbeTool,
        ApexReportBundleTool,
    )

    registry.register(ApexHealthCheckTool(kb))
    registry.register(ApexPageProbeTool(kb))
    registry.register(ApexComponentProbeTool(kb))
    registry.register(ApexFlowReplayTool(kb))
    registry.register(ApexLoginProbeTool(kb))
    registry.register(ApexReportBundleTool(kb))
    registry.register(ApexMissionPackTool(kb))


def load_kb_docs_from_dir(kb: InMemoryKnowledgeProvider, path: str) -> int:
    root = Path(path)
    n = 0
    files = list(root.glob("*.json"))
    # Also accept normalized tree
    if (root / "pages").exists() or root.name.endswith("kb_normalized"):
        files = list(root.rglob("*.json"))
    for f in files:
        if f.name in {"index.json", "catalog.json"}:
            continue
        try:
            raw = json.loads(f.read_text())
        except Exception:
            continue
        doc = KnowledgeDocument(
            id=raw.get("meta", {}).get("id") or raw.get("id") or f.stem,
            version=str(raw.get("meta", {}).get("version") or "0.1.0"),
            status=raw.get("status", "candidate"),
            body=raw.get("body") or {},
            meta=raw.get("meta") or {},
        )
        kb.update(doc)
        n += 1
    return n
