"""Qdrant and retrieval configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class QdrantConfig:
    enabled: bool = False
    url: str = "http://127.0.0.1:6333"
    collection: str = "qa_knowledge_v1"
    timeout_ms: int = 5000
    top_k: int = 8
    score_threshold: float | None = None
    dense_dimensions: int = 64
    hybrid_enabled: bool = True
    upsert_batch_size: int = 64

    @classmethod
    def from_env(cls) -> QdrantConfig:
        from qa_orchestrator.embedding_config import EmbeddingConfig

        emb = EmbeddingConfig.from_env()
        threshold_raw = os.environ.get("QA_QDRANT_SCORE_THRESHOLD")
        threshold = float(threshold_raw) if threshold_raw else None
        return cls(
            enabled=_env_bool("QA_QDRANT_ENABLED", default=False),
            url=os.environ.get("QA_QDRANT_URL", "http://127.0.0.1:6333").strip(),
            collection=os.environ.get("QA_QDRANT_COLLECTION", "qa_knowledge_v1").strip(),
            timeout_ms=int(os.environ.get("QA_QDRANT_TIMEOUT_MS", "5000")),
            top_k=int(os.environ.get("QA_QDRANT_TOP_K", "8")),
            score_threshold=threshold,
            dense_dimensions=emb.dimensions,
            hybrid_enabled=_env_bool("QA_QDRANT_HYBRID_ENABLED", default=True),
            upsert_batch_size=int(os.environ.get("QA_QDRANT_UPSERT_BATCH_SIZE", "64")),
        )
