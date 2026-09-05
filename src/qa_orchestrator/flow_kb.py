from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) > 2}


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    return yaml.safe_load(raw) or {}


class YamlFlowKb:
    """Flow-centric KB reader over discovery/uat_ea/flows/*.yaml."""

    def __init__(self, flows_dir: str | Path) -> None:
        self.flows_dir = Path(flows_dir)
        self.index_path = self.flows_dir / "index.yaml"
        self.flows: dict[str, dict[str, Any]] = {}
        self.index: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not self.index_path.exists():
            return
        self.index = _load_yaml(self.index_path)
        for entry in self.index.get("flows", []):
            flow_id = str(entry.get("id") or "")
            file_name = entry.get("file")
            if not flow_id or not file_name:
                continue
            path = self.flows_dir / str(file_name)
            if not path.exists():
                continue
            doc = _load_yaml(path)
            self.flows[flow_id] = {
                "id": flow_id,
                "name": entry.get("name") or doc.get("flow_name") or flow_id,
                "status": entry.get("status") or "DRAFT",
                "parent": entry.get("parent"),
                "superseded_by": entry.get("superseded_by"),
                "file": str(file_name),
                "doc": doc,
            }

    @property
    def ready_flow_ids(self) -> list[str]:
        ready = set(self.index.get("sme_ready", []))
        return sorted(
            fid
            for fid, meta in self.flows.items()
            if meta.get("status") == "READY" or fid in ready
        )

    @property
    def draft_flow_ids(self) -> list[str]:
        return sorted(fid for fid, meta in self.flows.items() if meta.get("status") == "DRAFT")

    def get(self, flow_id: str) -> dict[str, Any] | None:
        return self.flows.get(flow_id)

    def search(self, query: str, *, limit: int = 8, include_draft: bool = True) -> list[dict[str, Any]]:
        q_tokens = _tokenize(query)
        if not q_tokens:
            candidates = list(self.flows.values())
        else:
            scored: list[tuple[int, dict[str, Any]]] = []
            for meta in self.flows.values():
                if not include_draft and meta.get("status") == "DRAFT":
                    continue
                doc = meta.get("doc", {})
                hay = " ".join(
                    [
                        str(meta.get("id", "")),
                        str(meta.get("name", "")),
                        str(doc.get("purpose", "")),
                        " ".join(str(p) for p in doc.get("pages", [])),
                        str(doc.get("entry_point", {})),
                    ]
                ).lower()
                doc_tokens = _tokenize(hay)
                score = len(q_tokens & doc_tokens)
                if meta.get("status") == "READY":
                    score += 1
                if score > 0:
                    scored.append((score, meta))
            scored.sort(key=lambda x: x[0], reverse=True)
            candidates = [m for _, m in scored]

        return candidates[:limit]

    def context_block(self, query: str, *, limit: int = 6) -> tuple[str, list[str]]:
        hits = self.search(query, limit=limit, include_draft=True)
        lines: list[str] = []
        refs: list[str] = []
        for hit in hits:
            fid = str(hit["id"])
            refs.append(fid)
            doc = hit.get("doc", {})
            snippet = {
                "flow_id": fid,
                "name": hit.get("name"),
                "status": hit.get("status"),
                "purpose": doc.get("purpose"),
                "pages": doc.get("pages", [])[:8],
                "entry_point": doc.get("entry_point"),
            }
            lines.append(yaml.safe_dump(snippet, default_flow_style=False).strip())
        return "\n\n".join(lines), refs

    def app_overview(self) -> dict[str, Any]:
        login = self.get("BF-LOGIN-001")
        home = self.get("BF-HOME-010")
        overview: dict[str, Any] = {"application": self.index.get("application", "Endless Aisle")}
        if login:
            ep = login.get("doc", {}).get("entry_point", {})
            overview["login_url"] = ep.get("route", "/ords/r/tjdcom/ea/login")
        if home:
            ep = home.get("doc", {}).get("entry_point", {})
            overview["home_url"] = ep.get("route", "/ords/r/tjdcom/ea/home")
        return overview
