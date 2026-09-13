"""Deterministic QA knowledge indexing pipeline — idempotent upsert into vector store."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from qa_orchestrator.embedding_provider import DeterministicEmbeddingProvider
from qa_orchestrator.knowledge_document_builder import KnowledgeDocumentBuilder
from qa_orchestrator.qa_knowledge_models import IndexingStats, QaKnowledgeDocument
from qa_orchestrator.qdrant_config import QdrantConfig
from qa_orchestrator.vector_store import (
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
        store: VectorStoreBackend | None = None,
        embedding: DeterministicEmbeddingProvider | None = None,
    ) -> None:
        self.discovery_root = Path(discovery_root)
        self.automation_dir = Path(automation_dir)
        self.config = config or QdrantConfig.from_env()
        self.embedding = embedding or DeterministicEmbeddingProvider(self.config.dense_dimensions)
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
            self.store.ensure_collection()
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

        to_upsert: list = []
        for doc in docs:
            prior_hash = existing_hashes.get(doc.document_id)
            if prior_hash == doc.source_hash and doc.document_id in existing_ids:
                stats.unchanged += 1
                continue
            doc.indexed_at = datetime.now(timezone.utc).isoformat()
            to_upsert.append(build_stored_point(doc, self.embedding))
            if doc.document_id in existing_ids:
                stats.updated += 1
            else:
                stats.created += 1

        if to_upsert:
            try:
                self.store.upsert(to_upsert)
            except Exception as exc:
                stats.failed += len(to_upsert)
                stats.errors.append(f"upsert failed: {exc}")
                logger.warning("index upsert failed: %s", exc)

        return stats

    def seed_in_memory(self) -> IndexingStats:
        """Force in-memory store — used by unit tests."""
        self.store = InMemoryVectorStore(self.embedding)
        return self.index_all()
