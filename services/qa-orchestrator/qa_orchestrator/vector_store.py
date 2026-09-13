"""Vector store backends — in-memory for tests, Qdrant for production retrieval."""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from qa_orchestrator.embedding_provider import (
    DeterministicEmbeddingProvider,
    build_sparse_vector,
    sparse_dot,
)
from qa_orchestrator.qa_knowledge_models import QaKnowledgeDocument
from qa_orchestrator.qdrant_config import QdrantConfig

logger = logging.getLogger(__name__)


@dataclass
class StoredPoint:
    document: QaKnowledgeDocument
    dense: list[float]
    sparse: dict[int, float]
    payload: dict[str, Any] = field(default_factory=dict)


def document_point_uuid(document_id: str) -> str:
    digest = hashlib.md5(document_id.encode("utf-8")).hexdigest()
    return str(uuid.UUID(digest))


def document_payload(doc: QaKnowledgeDocument) -> dict[str, Any]:
    return {
        "document_id": doc.document_id,
        "document_type": doc.document_type,
        "flow_id": doc.flow_id,
        "test_id": doc.test_id,
        "step_id": doc.step_id,
        "title": doc.title,
        "text": doc.text,
        "source": doc.source,
        "status": doc.status,
        "sme_ready": doc.sme_ready,
        "approval_state": doc.approval_state,
        "polarity": doc.polarity,
        "tags": doc.tags,
        "metadata": doc.metadata,
        "source_path": doc.source_path,
        "source_hash": doc.source_hash,
        "indexed_at": doc.indexed_at,
        "version": doc.version,
    }


def payload_to_document(payload: dict[str, Any]) -> QaKnowledgeDocument | None:
    try:
        document_id = str(payload.get("document_id") or "")
        if not document_id:
            return None
        return QaKnowledgeDocument(
            document_id=document_id,
            document_type=payload.get("document_type") or "FLOW",
            flow_id=str(payload.get("flow_id") or ""),
            test_id=str(payload.get("test_id") or ""),
            step_id=str(payload.get("step_id") or ""),
            title=str(payload.get("title") or ""),
            text=str(payload.get("text") or ""),
            source=str(payload.get("source") or ""),
            status=str(payload.get("status") or ""),
            sme_ready=bool(payload.get("sme_ready")),
            approval_state=str(payload.get("approval_state") or ""),
            polarity=str(payload.get("polarity") or ""),
            tags=list(payload.get("tags") or []),
            metadata=dict(payload.get("metadata") or {}),
            source_path=str(payload.get("source_path") or ""),
            source_hash=str(payload.get("source_hash") or ""),
            indexed_at=str(payload.get("indexed_at") or ""),
            version=int(payload.get("version") or 1),
        )
    except Exception as exc:
        logger.warning("invalid qdrant payload ignored: %s", exc)
        return None


class VectorStoreBackend(Protocol):
    @property
    def available(self) -> bool: ...

    def ensure_collection(self) -> None: ...

    def upsert(self, points: list[StoredPoint]) -> None: ...

    def delete_by_document_ids(self, document_ids: list[str]) -> None: ...

    def list_document_ids(self) -> set[str]: ...

    def source_hashes(self) -> dict[str, str]: ...

    def search(
        self,
        *,
        query_dense: list[float],
        query_sparse: dict[int, float],
        limit: int,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[tuple[QaKnowledgeDocument, float, str]]: ...


class InMemoryVectorStore:
    """Deterministic hybrid store used by unit tests and Qdrant fallback."""

    def __init__(self, embedding: DeterministicEmbeddingProvider | None = None) -> None:
        self.embedding = embedding or DeterministicEmbeddingProvider()
        self._points: dict[str, StoredPoint] = {}
        self.available = True

    def ensure_collection(self) -> None:
        return None

    def upsert(self, points: list[StoredPoint]) -> None:
        for point in points:
            self._points[point.document.document_id] = point

    def delete_by_document_ids(self, document_ids: list[str]) -> None:
        for doc_id in document_ids:
            self._points.pop(doc_id, None)

    def list_document_ids(self) -> set[str]:
        return set(self._points.keys())

    def source_hashes(self) -> dict[str, str]:
        return {
            doc_id: point.document.source_hash
            for doc_id, point in self._points.items()
            if point.document.source_hash
        }

    def _passes_filters(self, doc: QaKnowledgeDocument, filters: dict[str, Any] | None) -> bool:
        if not filters:
            return True
        if filters.get("flow_id") and doc.flow_id != filters["flow_id"]:
            return False
        if filters.get("document_type"):
            allowed = filters["document_type"]
            if isinstance(allowed, str):
                allowed = [allowed]
            if doc.document_type not in allowed:
                return False
        if filters.get("status") and doc.status != filters["status"]:
            return False
        if filters.get("sme_ready_only") and not doc.sme_ready:
            return False
        if filters.get("approval_only") and doc.approval_state != "APPROVED":
            return False
        if filters.get("polarity") and doc.polarity and doc.polarity != filters["polarity"]:
            return False
        return True

    def search(
        self,
        *,
        query_dense: list[float],
        query_sparse: dict[int, float],
        limit: int,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[tuple[QaKnowledgeDocument, float, str]]:
        dense_scores: dict[str, float] = {}
        sparse_scores: dict[str, float] = {}
        for doc_id, point in self._points.items():
            if not self._passes_filters(point.document, filters):
                continue
            dense = sum(a * b for a, b in zip(query_dense, point.dense))
            sparse = sparse_dot(query_sparse, point.sparse)
            dense_scores[doc_id] = dense
            sparse_scores[doc_id] = sparse

        fused = _rrf_fuse([dense_scores, sparse_scores], k=60)
        ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)
        out: list[tuple[QaKnowledgeDocument, float, str]] = []
        for doc_id, score in ranked[:limit]:
            if score_threshold is not None and score < score_threshold:
                continue
            point = self._points[doc_id]
            method = "HYBRID_RRF"
            if dense_scores.get(doc_id, 0) >= sparse_scores.get(doc_id, 0):
                method = "DENSE"
            else:
                method = "SPARSE"
            out.append((point.document, score, method))
        return out


def _rrf_fuse(rankings: list[dict[str, float]], *, k: int = 60) -> dict[str, float]:
    fused: dict[str, float] = {}
    for ranking in rankings:
        ordered = sorted(ranking.items(), key=lambda x: x[1], reverse=True)
        for rank, (doc_id, _) in enumerate(ordered, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
    return fused


class QdrantVectorStore:
    """Production Qdrant backend with named dense + sparse vectors and RRF fusion."""

    DENSE_NAME = "dense"
    SPARSE_NAME = "sparse"

    def __init__(self, config: QdrantConfig, embedding: DeterministicEmbeddingProvider) -> None:
        self.config = config
        self.embedding = embedding
        self._client = None
        self._available = False
        self._init_error: str | None = None
        self._connect()

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> str | None:
        return self._init_error

    def _connect(self) -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http.exceptions import UnexpectedResponse

            timeout = max(1.0, self.config.timeout_ms / 1000.0)
            self._client = QdrantClient(url=self.config.url, timeout=timeout)
            self._client.get_collections()
            self._available = True
        except Exception as exc:
            self._available = False
            self._init_error = str(exc)
            logger.warning("qdrant unavailable, fallback enabled: %s", exc)

    def ensure_collection(self) -> None:
        if not self._available or self._client is None:
            return
        from qdrant_client.http import models

        exists = False
        try:
            self._client.get_collection(self.config.collection)
            exists = True
        except Exception:
            exists = False
        if exists:
            return
        self._client.create_collection(
            collection_name=self.config.collection,
            vectors_config={
                self.DENSE_NAME: models.VectorParams(
                    size=self.embedding.dimensions,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                self.SPARSE_NAME: models.SparseVectorParams()
            },
        )

    def upsert(self, points: list[StoredPoint]) -> None:
        if not self._available or self._client is None:
            raise RuntimeError("qdrant unavailable")
        from qdrant_client.http import models

        qdrant_points = []
        for point in points:
            qdrant_points.append(
                models.PointStruct(
                    id=document_point_uuid(point.document.document_id),
                    vector={
                        self.DENSE_NAME: point.dense,
                        self.SPARSE_NAME: models.SparseVector(
                            indices=list(point.sparse.keys()),
                            values=list(point.sparse.values()),
                        ),
                    },
                    payload=point.payload,
                )
            )
        self._client.upsert(collection_name=self.config.collection, points=qdrant_points, wait=True)

    def delete_by_document_ids(self, document_ids: list[str]) -> None:
        if not self._available or self._client is None or not document_ids:
            return
        from qdrant_client.http import models

        ids = [document_point_uuid(doc_id) for doc_id in document_ids]
        self._client.delete(
            collection_name=self.config.collection,
            points_selector=models.PointIdsList(points=ids),
            wait=True,
        )

    def list_document_ids(self) -> set[str]:
        return set(self.source_hashes().keys())

    def source_hashes(self) -> dict[str, str]:
        if not self._available or self._client is None:
            return {}
        hashes: dict[str, str] = {}
        offset = None
        while True:
            records, offset = self._client.scroll(
                collection_name=self.config.collection,
                limit=256,
                offset=offset,
                with_payload=["document_id", "source_hash"],
                with_vectors=False,
            )
            for record in records:
                payload = record.payload or {}
                doc_id = payload.get("document_id")
                if doc_id:
                    hashes[str(doc_id)] = str(payload.get("source_hash") or "")
            if offset is None:
                break
        return hashes

    def _build_filter(self, filters: dict[str, Any] | None):
        if not filters:
            return None
        from qdrant_client.http import models

        must: list[Any] = []
        if filters.get("flow_id"):
            must.append(
                models.FieldCondition(
                    key="flow_id",
                    match=models.MatchValue(value=str(filters["flow_id"])),
                )
            )
        if filters.get("document_type"):
            allowed = filters["document_type"]
            if isinstance(allowed, str):
                allowed = [allowed]
            must.append(
                models.FieldCondition(
                    key="document_type",
                    match=models.MatchAny(any=[str(x) for x in allowed]),
                )
            )
        if filters.get("status"):
            must.append(
                models.FieldCondition(
                    key="status",
                    match=models.MatchValue(value=str(filters["status"])),
                )
            )
        if filters.get("sme_ready_only"):
            must.append(
                models.FieldCondition(
                    key="sme_ready",
                    match=models.MatchValue(value=True),
                )
            )
        if filters.get("approval_only"):
            must.append(
                models.FieldCondition(
                    key="approval_state",
                    match=models.MatchValue(value="APPROVED"),
                )
            )
        if filters.get("polarity"):
            must.append(
                models.FieldCondition(
                    key="polarity",
                    match=models.MatchValue(value=str(filters["polarity"])),
                )
            )
        return models.Filter(must=must) if must else None

    def search(
        self,
        *,
        query_dense: list[float],
        query_sparse: dict[int, float],
        limit: int,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[tuple[QaKnowledgeDocument, float, str]]:
        if not self._available or self._client is None:
            return []
        from qdrant_client.http import models

        q_filter = self._build_filter(filters)
        if self.config.hybrid_enabled:
            response = self._client.query_points(
                collection_name=self.config.collection,
                prefetch=[
                    models.Prefetch(query=query_dense, using=self.DENSE_NAME, limit=limit * 2),
                    models.Prefetch(
                        query=models.SparseVector(
                            indices=list(query_sparse.keys()),
                            values=list(query_sparse.values()),
                        ),
                        using=self.SPARSE_NAME,
                        limit=limit * 2,
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                query_filter=q_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
            )
            method = "HYBRID_RRF"
        else:
            response = self._client.query_points(
                collection_name=self.config.collection,
                query=query_dense,
                using=self.DENSE_NAME,
                query_filter=q_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
            )
            method = "DENSE"

        out: list[tuple[QaKnowledgeDocument, float, str]] = []
        for point in response.points:
            payload = point.payload or {}
            doc = payload_to_document(payload)
            if doc is None:
                continue
            out.append((doc, float(point.score or 0.0), method))
        return out


def build_stored_point(
    doc: QaKnowledgeDocument,
    embedding: DeterministicEmbeddingProvider,
) -> StoredPoint:
    dense = embedding.embed_query(doc.text)
    sparse = build_sparse_vector(doc.text)
    return StoredPoint(document=doc, dense=dense, sparse=sparse, payload=document_payload(doc))


def create_vector_store(
    config: QdrantConfig,
    embedding: DeterministicEmbeddingProvider | None = None,
) -> VectorStoreBackend:
    emb = embedding or DeterministicEmbeddingProvider(config.dense_dimensions)
    if config.enabled:
        qdrant = QdrantVectorStore(config, emb)
        if qdrant.available:
            return qdrant
    return InMemoryVectorStore(emb)
