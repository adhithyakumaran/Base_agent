from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from qa_orchestrator.flow_kb import YamlFlowKb, _tokenize


def _load_yaml_fenced(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    fence = re.search(r"```ya?ml\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if fence:
        raw = fence.group(1)
    return yaml.safe_load(raw) or {}


class FlowKnowledgeGraph:
    """Capability → Flow → Suite graph for deterministic orchestration."""

    PRIMARY_STATUSES = {"READY"}
    SUPPORTING_STATUSES = {"DRAFT"}

    def __init__(
        self,
        *,
        discovery_root: str | Path,
        automation_dir: str | Path | None = None,
    ) -> None:
        self.discovery_root = Path(discovery_root)
        self.automation_dir = Path(automation_dir or "automation")
        self.flow_kb = YamlFlowKb(self.discovery_root / "flows")
        self.capabilities = self._load_capabilities()
        self.suites = self._load_suites()
        self.catalog = self._load_catalog()
        self._cap_to_flows = self._build_capability_map()

    def _load_capabilities(self) -> dict[str, Any]:
        path = self.discovery_root / "capabilities.yaml"
        if not path.exists():
            return {}
        return _load_yaml_fenced(path)

    def _load_suites(self) -> dict[str, Any]:
        path = self.automation_dir / "suites" / "index.yaml"
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _load_catalog(self) -> dict[str, Any]:
        path = self.automation_dir / "catalog" / "index.yaml"
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _build_capability_map(self) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        for cap_name, meta in (self.capabilities.get("capabilities") or {}).items():
            flows: list[str] = []
            for raw in meta.get("flows") or []:
                fid = str(raw).split("#", 1)[0].strip()
                if fid:
                    flows.append(fid)
            mapping[str(cap_name)] = flows
        return mapping

    def ready_flow_ids(self) -> list[str]:
        return self.flow_kb.ready_flow_ids

    def draft_flow_ids(self) -> list[str]:
        return self.flow_kb.draft_flow_ids

    def flow_meta(self, flow_id: str) -> dict[str, Any] | None:
        return self.flow_kb.get(flow_id)

    def is_automated(self, flow_id: str) -> bool:
        for entry in self.catalog.get("flows") or []:
            if entry.get("flow_id") == flow_id:
                return True
        return False

    def flows_for_capability(self, capability: str) -> list[str]:
        flows = self._cap_to_flows.get(capability, [])
        return [f for f in flows if self._is_primary(f)]

    def capability_for_flow(self, flow_id: str) -> str | None:
        for cap, flows in self._cap_to_flows.items():
            if flow_id in flows:
                return cap
        return None

    def related_flows(self, flow_id: str) -> list[str]:
        meta = self.flow_meta(flow_id)
        if not meta:
            return []
        related: list[str] = []
        parent = meta.get("parent")
        if parent:
            related.append(str(parent))
        for fid, m in self.flow_kb.flows.items():
            if m.get("parent") == flow_id:
                related.append(fid)
        cap = self.capability_for_flow(flow_id)
        if cap:
            related.extend(self.flows_for_capability(cap))
        seen: set[str] = set()
        out: list[str] = []
        for fid in related:
            if fid == flow_id or fid in seen:
                continue
            seen.add(fid)
            if self._is_primary(fid):
                out.append(fid)
        return out

    def search_flows(self, query: str, *, limit: int = 8) -> list[str]:
        hits = self.flow_kb.search(query, limit=limit * 2, include_draft=True)
        primary: list[str] = []
        supporting: list[str] = []
        for hit in hits:
            fid = str(hit["id"])
            if self._is_primary(fid):
                primary.append(fid)
            elif hit.get("status") in self.SUPPORTING_STATUSES:
                supporting.append(fid)
        return (primary + supporting)[:limit]

    def supporting_for_query(self, query: str) -> list[str]:
        return [fid for fid in self.search_flows(query, limit=12) if not self._is_primary(fid)]

    def sanity_suite(self) -> dict[str, Any]:
        return self.suites.get("sanity") or {}

    def regression_suite(self) -> dict[str, Any]:
        return self.suites.get("regression") or {}

    def graph_context(self, query: str, *, limit: int = 10) -> str:
        lines = [
            f"Application: {self.flow_kb.index.get('application', 'Endless Aisle')}",
            f"Primary READY flows ({len(self.ready_flow_ids())}): {', '.join(self.ready_flow_ids()[:12])}…",
            f"Supporting DRAFT flows: {', '.join(self.draft_flow_ids())}",
            "",
            "Capabilities:",
        ]
        for cap, flows in list(self._cap_to_flows.items())[:8]:
            ready = [f for f in flows if self._is_primary(f)]
            if ready:
                lines.append(f"- {cap}: {', '.join(ready[:5])}")
        hits = self.search_flows(query, limit=limit)
        if hits:
            lines.extend(["", f"Query matches: {', '.join(hits)}"])
        return "\n".join(lines)

    def _is_primary(self, flow_id: str) -> bool:
        meta = self.flow_meta(flow_id)
        if not meta:
            return False
        if meta.get("status") in self.PRIMARY_STATUSES:
            return self.is_automated(flow_id)
        return flow_id in set(self.flow_kb.index.get("sme_ready", []))

    def match_capabilities(self, query: str) -> list[str]:
        q = query.lower()
        q_tokens = _tokenize(query)
        matched: list[str] = []
        for cap in self._cap_to_flows:
            cap_tokens = _tokenize(cap)
            if cap.lower() in q or q_tokens & cap_tokens:
                matched.append(cap)
        return matched
