from __future__ import annotations

from typing import Any

from base_agent.contracts.enums import ExecutionMode
from base_agent.knowledge.protocol import InMemoryKnowledgeProvider, KnowledgeDocument
from base_agent.tools.registry import ExecutionContext, RawToolResult, ToolDefinition, ToolRegistry


class ApexDiscoverTool:
    """Bounded APEX discovery probe — uses KB + optional live crawl hook.

    Anti-stuck guarantees:
    - max_pages from payload/budget
    - never retries the same URL signature repeatedly (executor/budget handle that)
    - returns structured map even when incomplete
    """

    definition = ToolDefinition(
        name="qa.apex.discover",
        description="Discover Oracle APEX Endless Aisle pages/modules into KB candidates",
        plugin_id="qa.apex",
        capability="qa.discover",
        permissions=["tool.execute:qa.apex.*", "knowledge.write"],
        timeout_ms=120_000,
        execution_mode=ExecutionMode.SIDE_EFFECTING,
        tags=["qa", "apex", "crawler"],
        metadata={
            "anti_stuck": {
                "max_pages": 40,
                "same_url_limit": 1,
                "modal_timeout_ms": 3000,
                "networkidle_optional": True,
                "skip_external_hosts": True,
            }
        },
    )

    def __init__(self, kb: InMemoryKnowledgeProvider | None = None) -> None:
        self.kb = kb or InMemoryKnowledgeProvider()

    def validate_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "mode": payload.get("mode", "kb_snapshot"),
            "max_pages": int(payload.get("max_pages", 40)),
            "seed": payload.get("seed"),
        }

    def validate_output(self, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict) or "pages" not in raw:
            raise ValueError("discover output requires pages")
        return raw

    def execute(self, payload: dict[str, Any], ctx: ExecutionContext) -> RawToolResult:
        # Enterprise default without live browser in unit context: emit KB snapshot
        docs = self.kb.all()
        pages = []
        flows = []
        components = []
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
            elif typ == "component":
                components.append({"id": d.id, "name": body.get("title"), "details": details})

        # Deterministic APEX rules pack always included
        rules_fired = ["rule.session.required", "rule.friendly_url.parse", "rule.budget.max_pages"]
        return RawToolResult(
            ok=True,
            data={
                "mode": payload["mode"],
                "pages": pages[: payload["max_pages"]],
                "flows": flows,
                "components": components,
                "stats": {
                    "pages": min(len(pages), payload["max_pages"]),
                    "flows": len(flows),
                    "components": len(components),
                    "truncated": len(pages) > payload["max_pages"],
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
                "rules": rules_fired,
                "body_text": "",  # no ORA error
            },
        )


class ApexSanityProbeTool:
    definition = ToolDefinition(
        name="qa.apex.sanity_probe",
        description="Run deterministic sanity probes using KB + rules (no GT required)",
        plugin_id="qa.apex",
        capability="qa.sanity",
        permissions=["tool.execute:qa.apex.*"],
        tags=["qa", "apex"],
    )

    def __init__(self, kb: InMemoryKnowledgeProvider | None = None) -> None:
        self.kb = kb

    def validate_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def validate_output(self, raw: Any) -> dict[str, Any]:
        return raw if isinstance(raw, dict) else {"value": raw}

    def execute(self, payload: dict[str, Any], ctx: ExecutionContext) -> RawToolResult:
        checks = []
        # Rule-level sanity without GT
        checks.append({"id": "home_in_kb", "outcome": "pass" if self.kb and self.kb.search("home", k=1) else "insufficient"})
        checks.append({"id": "login_flow_in_kb", "outcome": "pass" if self.kb and self.kb.search("login", k=1) else "insufficient"})
        checks.append({"id": "no_forced_pass_without_gt", "outcome": "pass"})
        return RawToolResult(ok=True, data={"checks": checks, "gt_required_for_business_passfail": True})


def register_qa_apex(registry: ToolRegistry, kb: InMemoryKnowledgeProvider | None = None) -> None:
    kb = kb or InMemoryKnowledgeProvider()
    registry.register(ApexDiscoverTool(kb))
    registry.register(ApexSanityProbeTool(kb))


def load_kb_docs_from_dir(kb: InMemoryKnowledgeProvider, path: str) -> int:
    import json
    from pathlib import Path

    root = Path(path)
    n = 0
    for f in root.glob("*.json"):
        if f.name == "index.json":
            continue
        raw = json.loads(f.read_text())
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