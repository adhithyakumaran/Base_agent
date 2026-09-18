"""Deterministic QA knowledge indexing pipeline — idempotent upsert into vector store."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from qa_orchestrator.embedding_config import EmbeddingConfig
from qa_orchestrator.embedding_provider import (
    EmbeddingProvider,
    EmbeddingProviderError,
    create_embedding_provider,
)
from qa_orchestrator.knowledge_document_builder import KnowledgeDocumentBuilder
from qa_orchestrator.qa_knowledge_models import IndexingStats, QaKnowledgeDocument
from qa_orchestrator.qdrant_config import QdrantConfig
from qa_orchestrator.vector_store import (
    CollectionCompatibilityError,
    InMemoryVectorStore,
    VectorStoreBackend,
    build_stored_point,
    create_vector_store,
)

logger = logging.getLogger(__name__)


class KnowledgeIndexer:
    """Load authoritative sources, normalize, hash, and upsert changed documents."""

    def __init__(
        self,
        *,
        discovery_root: str | Path,
        automation_dir: str | Path,
        config: QdrantConfig | None = None,
        embedding_config: EmbeddingConfig | None = None,
        store: VectorStoreBackend | None = None,
        embedding: EmbeddingProvider | None = None,
    ) -> None:
        self.discovery_root = Path(discovery_root)
        self.automation_dir = Path(automation_dir)
        self.embedding_config = embedding_config or EmbeddingConfig.from_env()
        self.config = config or QdrantConfig.from_env()
        self.embedding = embedding or create_embedding_provider(self.embedding_config)
        self.store = store or create_vector_store(self.config, self.embedding)
        self.builder = KnowledgeDocumentBuilder(
            discovery_root=self.discovery_root,
            automation_dir=self.automation_dir,
        )

    def build_documents(self) -> list[QaKnowledgeDocument]:
        return self.builder.build_all()

    def index_all(self) -> IndexingStats:
        stats = IndexingStats()
        docs = self.build_documents()
        stats.documents_seen = len(docs)
        for doc in docs:
            if doc.document_type == "FLOW":
                stats.flows += 1
            elif doc.document_type == "TEST_CASE":
                stats.test_cases += 1
            elif doc.document_type == "BUSINESS_RULE":
                stats.business_rules += 1
            elif doc.document_type == "STEP":
                stats.steps += 1
            elif doc.document_type == "EXPLORATION":
                stats.exploration += 1
            elif doc.document_type == "HEALING":
                stats.healing += 1

        try:
            self.store.ensure_collection(embedding=self.embedding)
        except CollectionCompatibilityError as exc:
            stats.failed += 1
            stats.errors.append(str(exc))
            logger.warning("index collection compatibility failed: %s", exc)
            return stats
        except Exception as exc:
            stats.failed += 1
            stats.errors.append(f"ensure_collection failed: {exc}")
            logger.warning("index ensure_collection failed: %s", exc)

        existing_hashes = self.store.source_hashes()
        existing_ids = set(existing_hashes.keys())
        incoming_ids = {doc.document_id for doc in docs}
        stale_ids = sorted(existing_ids - incoming_ids)
        if stale_ids:
            try:
                self.store.delete_by_document_ids(stale_ids)
                stats.deleted = len(stale_ids)
            except Exception as exc:
                stats.failed += 1
                stats.errors.append(f"delete stale failed: {exc}")

        changed_docs: list[QaKnowledgeDocument] = []
        for doc in docs:
            prior_hash = existing_hashes.get(doc.document_id)
            if prior_hash == doc.source_hash and doc.document_id in existing_ids:
                stats.unchanged += 1
                continue
            doc.indexed_at = datetime.now(timezone.utc).isoformat()
            changed_docs.append(doc)
            if doc.document_id in existing_ids:
                stats.updated += 1
            else:
                stats.created += 1

        if not changed_docs:
            return stats

        batch_size = max(1, self.embedding_config.batch_size)
        upsert_batch_size = max(1, self.config.upsert_batch_size)
        points_buffer: list = []

        for start in range(0, len(changed_docs), batch_size):
            batch_docs = changed_docs[start : start + batch_size]
            texts = [doc.text for doc in batch_docs]
            stats.batches += 1
            try:
                vectors = self.embedding.embed_documents(texts)
                stats.embedded += len(batch_docs)
            except EmbeddingProviderError as exc:
                stats.embedding_failed += len(batch_docs)
                stats.errors.append(f"embedding batch failed: {exc}")
                logger.warning("embedding batch failed: %s", exc)
                continue
            except Exception as exc:
                stats.embedding_failed += len(batch_docs)
                stats.errors.append(f"embedding batch failed: {exc}")
                continue

            for doc, vector in zip(batch_docs, vectors):
                try:
                    points_buffer.append(build_stored_point(doc, self.embedding, dense=vector))
                except Exception as exc:
                    stats.embedding_failed += 1
                    stats.errors.append(f"point build failed for {doc.document_id}: {exc}")

            while len(points_buffer) >= upsert_batch_size:
                chunk = points_buffer[:upsert_batch_size]
                points_buffer = points_buffer[upsert_batch_size:]
                if self._upsert_chunk(chunk, stats):
                    stats.upserted += len(chunk)

        if points_buffer:
            if self._upsert_chunk(points_buffer, stats):
                stats.upserted += len(points_buffer)

        return stats

    def _upsert_chunk(self, chunk: list, stats: IndexingStats) -> bool:
        try:
            self.store.upsert(chunk, batch_size=len(chunk))
            return True
        except Exception as exc:
            stats.failed += len(chunk)
            stats.errors.append(f"upsert failed: {exc}")
            logger.warning("index upsert failed: %s", exc)
            return False

    def seed_in_memory(self) -> IndexingStats:
        """Force in-memory store — used by unit tests."""
        self.store = InMemoryVectorStore(self.embedding)
        return self.index_all()
