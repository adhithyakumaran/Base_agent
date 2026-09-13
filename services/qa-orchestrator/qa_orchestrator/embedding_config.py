"""Embedding provider configuration — vendor-neutral, env-driven."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str = "deterministic"
    model: str = "hash-v1"
    dimensions: int = 64
    batch_size: int = 32
    timeout_ms: int = 30000
    normalize: bool = True
    api_url: str = ""
    api_key: str = ""
    allow_collection_recreate: bool = False

    @classmethod
    def from_env(cls) -> EmbeddingConfig:
        provider = os.environ.get("QA_EMBEDDING_PROVIDER", "deterministic").strip().lower()
        model = os.environ.get("QA_EMBEDDING_MODEL", "").strip()
        if not model:
            model = "text-embedding-3-small" if provider == "production" else "hash-v1"
        api_key = os.environ.get("QA_EMBEDDING_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        api_url = os.environ.get("QA_EMBEDDING_API_URL", "").strip()
        if not api_url and provider == "production":
            api_url = "https://api.openai.com/v1/embeddings"
        return cls(
            provider=provider,
            model=model,
            dimensions=int(os.environ.get("QA_EMBEDDING_DIMENSIONS", "64")),
            batch_size=int(os.environ.get("QA_EMBEDDING_BATCH_SIZE", "32")),
            timeout_ms=int(os.environ.get("QA_EMBEDDING_TIMEOUT_MS", "30000")),
            normalize=_env_bool("QA_EMBEDDING_NORMALIZE", default=True),
            api_url=api_url,
            api_key=api_key.strip(),
            allow_collection_recreate=_env_bool("QA_QDRANT_ALLOW_RECREATE", default=False),
        )

    def embedding_version(self) -> str:
        payload = f"{self.provider}:{self.model}:{self.dimensions}:{self.normalize}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def metadata_dict(self) -> dict[str, str | int | bool]:
        return {
            "embedding_provider": self.provider,
            "embedding_model": self.model,
            "embedding_dimensions": self.dimensions,
            "embedding_version": self.embedding_version(),
            "embedding_normalize": self.normalize,
        }
