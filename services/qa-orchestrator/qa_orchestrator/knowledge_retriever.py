"""Semantic QA knowledge retrieval with hybrid search and safe lexical fallback."""

from __future__ import annotations

import logging
import re
from typing import Any

from qa_orchestrator.embedding_provider import DeterministicEmbeddingProvider, build_sparse_vector
from qa_orchestrator.intent_classifier import _extract_sku
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.knowledge_indexer import KnowledgeIndexer
from qa_orchestrator.qa_knowledge_models import (
    QaKnowledgeDocument,
    RetrievalDiagnostics,
    RetrievalResult,
    RetrievedKnowledgeItem,
)
from qa_orchestrator.qdrant_config import QdrantConfig
from qa_orchestrator.vector_store import InMemoryVectorStore, VectorStoreBackend, create_vector_store

logger = logging.getLogger(__name__)

FLOW_ID_RE = re.compile(r"\bBF-[A-Z0-9-]+(?:-[A-Z0-9]+)*\b")
TEST_ID_RE = re.compile(r"\bTC-[A-Z0-9-]+(?:-[A-Z0-9]+)*\b")
SKU_RE = re.compile(r"\bSKU\s+([A-Z0-9-]+)\b", re.I)


def extract_exact_identifiers(query: str) -> list[str]:
    ids: list[str] = []
    ids.extend(FLOW_ID_RE.findall(query))
    ids.extend(TEST_ID_RE.findall(query))
    seen: set[str] = set()
    out: list[str] = []
    for item in ids:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _relevance(score: float, *, exact: bool = False) -> str:
    if exact:
        return "EXACT"
    if score >= 0.8:
        return "HIGH"
    if score >= 0.5:
        return "MEDIUM"
    return "LOW"


class KnowledgeRetriever:
    """Hybrid retrieval layer — Qdrant when enabled, deterministic fallback otherwise."""

    def __init__(
        self,
        graph: FlowKnowledgeGraph,
        *,
        config: QdrantConfig | None = None,
        store: VectorStoreBackend | None = None,
        embedding: DeterministicEmbeddingProvider | None = None,
        indexer: KnowledgeIndexer | None = None,
    ) -> None:
        self.graph = graph
        self.config = config or QdrantConfig.from_env()
        self.embedding = embedding or DeterministicEmbeddingProvider(self.config.dense_dimensions)
        self.store = store or create_vector_store(self.config, self.embedding)
        self.indexer = indexer or KnowledgeIndexer(
            discovery_root=graph.discovery_root,
            automation_dir=graph.automation_dir,
            config=self.config,
            store=self.store,
            embedding=self.embedding,
        )
        self._indexed = False

    def ensure_index(self) -> None:
        if self._indexed:
            return
        if isinstance(self.store, InMemoryVectorStore) and not self.store.list_document_ids():
            self.indexer.index_all()
        self._indexed = True

    def _can_use_vector_search(self) -> bool:
        if isinstance(self.store, InMemoryVectorStore):
            return bool(self.store.list_document_ids())
        if not self.config.enabled:
            return False
        return bool(getattr(self.store, "available", False))

    def retrieve(
        self,
        query: str,
        *,
        flow_id: str | None = None,
        document_types: list[str] | None = None,
        polarity: str | None = None,
        sme_ready_only: bool = True,
        approval_only: bool = True,
        top_k: int | None = None,
    ) -> RetrievalResult:
        limit = top_k or self.config.top_k
        diagnostics = RetrievalDiagnostics(
            query=query,
            qdrant_enabled=self.config.enabled,
            qdrant_available=getattr(self.store, "available", True),
            top_k=limit,
        )

        if not self._can_use_vector_search():
            diagnostics.method = "LEXICAL_FALLBACK"
            diagnostics.fallback_reason = (
                "QA_QDRANT_ENABLED=false"
                if not self.config.enabled
                else getattr(self.store, "init_error", None) or "vector store unavailable"
            )
            return self._lexical_fallback(query, diagnostics, limit=limit)

        try:
            self.ensure_index()
        except Exception as exc:
            diagnostics.method = "LEXICAL_FALLBACK"
            diagnostics.fallback_reason = f"index failed: {exc}"
            return self._lexical_fallback(query, diagnostics, limit=limit)

        if not getattr(self.store, "available", True):
            diagnostics.method = "LEXICAL_FALLBACK"
            init_error = getattr(self.store, "init_error", None)
            diagnostics.fallback_reason = init_error or "qdrant unavailable"
            return self._lexical_fallback(query, diagnostics, limit=limit)

        filters: dict[str, Any] = {}
        if flow_id:
            filters["flow_id"] = flow_id
        if document_types:
            filters["document_type"] = document_types
        if polarity:
            filters["polarity"] = polarity
        if sme_ready_only:
            filters["sme_ready_only"] = True
        if approval_only:
            filters["approval_only"] = True

        exact_ids = extract_exact_identifiers(query)
        diagnostics.exact_id_hits = exact_ids
        exact_items = self._exact_id_lookup(query, exact_ids, filters)

        query_dense = self.embedding.embed_query(query)
        query_sparse = build_sparse_vector(query)
        try:
            hits = self.store.search(
                query_dense=query_dense,
                query_sparse=query_sparse,
                limit=limit,
                filters=filters or None,
                score_threshold=self.config.score_threshold,
            )
        except Exception as exc:
            diagnostics.method = "LEXICAL_FALLBACK"
            diagnostics.fallback_reason = f"search failed: {exc}"
            return self._lexical_fallback(query, diagnostics, limit=limit)

        merged: dict[str, RetrievedKnowledgeItem] = {}
        for item in exact_items:
            merged[item.document.document_id] = item

        for doc, score, method in hits:
            if doc.document_id in merged:
                continue
            merged[doc.document_id] = RetrievedKnowledgeItem(
                document=doc,
                score=score,
                retrieval_method=method,  # type: ignore[arg-type]
                matched_metadata={"flow_id": doc.flow_id, "document_type": doc.document_type},
                source_reference=doc.source_path or doc.source,
                relevance=_relevance(score),  # type: ignore[arg-type]
            )

        items = sorted(merged.values(), key=lambda x: x.score, reverse=True)[:limit]
        filtered, selected = self._post_filter(items, diagnostics)
        diagnostics.retrieval_used = True
        diagnostics.method = hits[0][2] if hits else ("EXACT_ID" if exact_items else "HYBRID_RRF")  # type: ignore[assignment]
        diagnostics.candidates = [
            {
                "document_id": item.document.document_id,
                "score": round(item.score, 4),
                "document_type": item.document.document_type,
                "flow_id": item.document.flow_id,
            }
            for item in items
        ]
        diagnostics.selected = selected
        diagnostics.filtered = filtered

        flow_ids = self._flow_ids_from_items(items)
        return RetrievalResult(query=query, items=items, flow_ids=flow_ids, diagnostics=diagnostics)

    def _exact_id_lookup(
        self,
        query: str,
        exact_ids: list[str],
        filters: dict[str, Any],
    ) -> list[RetrievedKnowledgeItem]:
        items: list[RetrievedKnowledgeItem] = []
        for ident in exact_ids:
            if ident.startswith("BF-"):
                meta = self.graph.flow_meta(ident)
                if not meta:
                    continue
                doc = QaKnowledgeDocument(
                    document_id=f"flow:{ident}",
                    document_type="FLOW",
                    flow_id=ident,
                    title=str(meta.get("name") or ident),
                    text=query,
                    source="knowledge_graph",
                    status=str(meta.get("status") or ""),
                    sme_ready=ident in set(self.graph.flow_kb.index.get("sme_ready") or []),
                    approval_state=self._approval_state(ident),
                )
            elif ident.startswith("TC-"):
                doc = QaKnowledgeDocument(
                    document_id=f"test:{ident}",
                    document_type="TEST_CASE",
                    test_id=ident,
                    flow_id=self._flow_for_test(ident),
                    title=ident,
                    text=query,
                    source="test-design",
                    status="UNKNOWN",
                    approval_state=self._approval_state(self._flow_for_test(ident)),
                )
            else:
                continue
            if not self._passes_filters(doc, filters):
                continue
            items.append(
                RetrievedKnowledgeItem(
                    document=doc,
                    score=1.0,
                    retrieval_method="EXACT_ID",
                    matched_metadata={"exact_id": ident},
                    source_reference=doc.source,
                    relevance="EXACT",
                )
            )
        return items

    def _approval_state(self, flow_id: str) -> str:
        if not flow_id:
            return "UNKNOWN"
        decision = self.graph.evaluate_execution(flow_id)
        return decision.approval_status or "UNKNOWN"

    def _flow_for_test(self, test_id: str) -> str:
        parts = test_id.split("-")
        if len(parts) >= 3:
            return "-".join(parts[1:-1])
        return ""

    def _passes_filters(self, doc: QaKnowledgeDocument, filters: dict[str, Any]) -> bool:
        if filters.get("flow_id") and doc.flow_id != filters["flow_id"]:
            return False
        if filters.get("document_type"):
            allowed = filters["document_type"]
            if isinstance(allowed, str):
                allowed = [allowed]
            if doc.document_type not in allowed:
                return False
        if filters.get("sme_ready_only") and not doc.sme_ready:
            return False
        if filters.get("approval_only") and doc.approval_state != "APPROVED":
            return False
        if filters.get("polarity") and doc.polarity and doc.polarity != filters["polarity"]:
            return False
        return True

    def _post_filter(
        self,
        items: list[RetrievedKnowledgeItem],
        diagnostics: RetrievalDiagnostics,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        filtered: list[dict[str, Any]] = []
        selected: list[str] = []
        seen: set[str] = set()
        for item in items:
            fid = item.document.flow_id
            if not fid:
                continue
            meta = self.graph.flow_meta(fid)
            if not meta:
                filtered.append({"flow_id": fid, "reason": "flow not in knowledge graph"})
                continue
            if fid in seen:
                continue
            seen.add(fid)
            selected.append(fid)
        return filtered, selected

    def _flow_ids_from_items(self, items: list[RetrievedKnowledgeItem]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in items:
            fid = item.document.flow_id
            if fid and fid not in seen and self.graph.flow_meta(fid):
                seen.add(fid)
                out.append(fid)
        return out

    def _lexical_fallback(
        self,
        query: str,
        diagnostics: RetrievalDiagnostics,
        *,
        limit: int,
    ) -> RetrievalResult:
        diagnostics.retrieval_used = True
        flow_ids = self.graph.flows_for_query_semantic(query, limit=limit)
        if not flow_ids:
            flow_ids = self.graph.search_flows(query, limit=limit)

        exact_ids = extract_exact_identifiers(query)
        for ident in exact_ids:
            if ident.startswith("BF-") and ident not in flow_ids and self.graph.flow_meta(ident):
                flow_ids.insert(0, ident)

        sku_match = SKU_RE.search(query)
        extracted_sku = _extract_sku(query)
        if sku_match or extracted_sku:
            for fid in ["BF-PRODUCT-003", "BF-HOME-010-01"]:
                if self.graph.flow_meta(fid) and fid not in flow_ids:
                    flow_ids.insert(0, fid)

        g_lower = query.lower()
        if "login" in g_lower and "logout" not in g_lower:
            for fid in ["BF-LOGIN-001"]:
                if self.graph.flow_meta(fid) and fid not in flow_ids:
                    flow_ids.insert(0, fid)

        items: list[RetrievedKnowledgeItem] = []
        for idx, fid in enumerate(flow_ids[:limit]):
            meta = self.graph.flow_meta(fid) or {}
            doc = QaKnowledgeDocument(
                document_id=f"flow:{fid}",
                document_type="FLOW",
                flow_id=fid,
                title=str(meta.get("name") or fid),
                text=query,
                source="lexical_fallback",
                status=str(meta.get("status") or ""),
                sme_ready=fid in set(self.graph.flow_kb.index.get("sme_ready") or []),
                approval_state=self._approval_state(fid),
            )
            score = 1.0 - (idx * 0.05)
            items.append(
                RetrievedKnowledgeItem(
                    document=doc,
                    score=score,
                    retrieval_method="LEXICAL_FALLBACK",
                    matched_metadata={"flow_id": fid},
                    source_reference=str(meta.get("file") or ""),
                    relevance="HIGH" if idx == 0 else "MEDIUM",
                )
            )

        filtered, selected = self._post_filter(items, diagnostics)
        diagnostics.candidates = [
            {
                "document_id": item.document.document_id,
                "score": round(item.score, 4),
                "document_type": item.document.document_type,
                "flow_id": item.document.flow_id,
            }
            for item in items
        ]
        diagnostics.selected = selected
        diagnostics.filtered = filtered
        return RetrievalResult(query=query, items=items, flow_ids=selected, diagnostics=diagnostics)
