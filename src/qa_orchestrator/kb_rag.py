from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) > 2}


class KbRag:
    """Lightweight KB retrieval — keyword overlap over indexed JSON docs."""

    def __init__(self, kb_dir: str | Path) -> None:
        self.kb_dir = Path(kb_dir)
        self.index_path = self.kb_dir / "index.json"
        self.documents: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.index_path.exists():
            return
        index = json.loads(self.index_path.read_text(encoding="utf-8"))
        for entry in index.get("documents", []):
            file_name = entry.get("file")
            if not file_name:
                continue
            path = self.kb_dir / file_name
            if not path.exists():
                continue
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            self.documents.append(
                {
                    "id": entry.get("id") or doc.get("meta", {}).get("id", file_name),
                    "type": entry.get("type") or doc.get("body", {}).get("type", "unknown"),
                    "title": entry.get("title") or doc.get("body", {}).get("title", file_name),
                    "status": entry.get("status") or doc.get("status", "candidate"),
                    "file": file_name,
                    "raw": doc,
                }
            )

    def search(self, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
        q_tokens = _tokenize(query)
        if not q_tokens:
            return self.documents[:limit]

        scored: list[tuple[int, dict[str, Any]]] = []
        for doc in self.documents:
            hay = " ".join(
                [
                    str(doc.get("id", "")),
                    str(doc.get("title", "")),
                    str(doc.get("type", "")),
                    json.dumps(doc.get("raw", {}), default=str),
                ]
            ).lower()
            doc_tokens = _tokenize(hay)
            score = len(q_tokens & doc_tokens)
            if "flow" in query.lower() and doc.get("type") == "flow":
                score += 2
            if "login" in query.lower() and "login" in hay:
                score += 3
            if "sanity" in query.lower() and doc.get("type") in {"flow", "business_note"}:
                score += 1
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:limit]]

    def context_block(self, query: str, *, limit: int = 8) -> tuple[str, list[str]]:
        hits = self.search(query, limit=limit)
        lines: list[str] = []
        refs: list[str] = []
        for hit in hits:
            refs.append(str(hit["id"]))
            body = hit.get("raw", {}).get("body", {})
            details = body.get("details", {})
            snippet = {
                "id": hit["id"],
                "type": hit.get("type"),
                "title": hit.get("title"),
                "summary": body.get("summary"),
                "details": details,
            }
            lines.append(json.dumps(snippet, indent=2, default=str))
        return "\n\n".join(lines), refs

    def app_overview(self) -> dict[str, Any]:
        for doc in self.documents:
            if doc.get("id") == "kb.app.endless_aisle.overview":
                return doc.get("raw", {}).get("body", {}).get("details", {})
        return {}
