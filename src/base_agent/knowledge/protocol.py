from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class KnowledgeHit(BaseModel):
    id: str
    version: str = "0.1.0"
    score: float = 1.0
    title: str
    snippet: str
    source: str = "memory"
    stale: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocument(BaseModel):
    id: str
    version: str = "0.1.0"
    status: str = "candidate"  # candidate|active|stale|superseded|rejected
    kind: str = "knowledge"
    body: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)


class ProviderMetadata(BaseModel):
    name: str
    version: str = "0.1.0"
    backend: str = "memory"


class KnowledgeProvider(Protocol):
    def search(self, query: str, *, filters: dict[str, Any] | None = None, k: int = 5) -> list[KnowledgeHit]: ...

    def retrieve(self, id: str, version: str | None = None) -> KnowledgeDocument: ...

    def update(self, doc: KnowledgeDocument) -> None: ...

    def metadata(self) -> ProviderMetadata: ...


class InMemoryKnowledgeProvider:
    def __init__(self) -> None:
        self._docs: dict[str, KnowledgeDocument] = {}

    def load_many(self, docs: list[KnowledgeDocument]) -> None:
        for d in docs:
            self._docs[d.id] = d

    def search(self, query: str, *, filters: dict[str, Any] | None = None, k: int = 5) -> list[KnowledgeHit]:
        q = query.lower()
        hits: list[KnowledgeHit] = []
        for doc in self._docs.values():
            if filters:
                status = filters.get("status")
                if status and doc.status != status:
                    continue
            blob = (doc.id + " " + str(doc.body) + " " + str(doc.meta)).lower()
            if q in blob or any(tok and tok in blob for tok in q.split()):
                title = str(doc.body.get("title") or doc.id)
                snippet = str(doc.body.get("summary") or "")[:240]
                hits.append(
                    KnowledgeHit(
                        id=doc.id,
                        version=doc.version,
                        score=1.0,
                        title=title,
                        snippet=snippet,
                        source="memory",
                        stale=doc.status == "stale",
                    )
                )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    def retrieve(self, id: str, version: str | None = None) -> KnowledgeDocument:
        if id not in self._docs:
            raise KeyError(id)
        return self._docs[id]

    def update(self, doc: KnowledgeDocument) -> None:
        self._docs[doc.id] = doc

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(name="in_memory_kb", backend="memory")

    def all(self) -> list[KnowledgeDocument]:
        return list(self._docs.values())


class NullKnowledgeProvider:
    def search(self, query: str, *, filters: dict[str, Any] | None = None, k: int = 5) -> list[KnowledgeHit]:
        return []

    def retrieve(self, id: str, version: str | None = None) -> KnowledgeDocument:
        raise KeyError(id)

    def update(self, doc: KnowledgeDocument) -> None:
        return None

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(name="null_kb", backend="null")