"""Embedding provider abstraction — replaceable, no vendor lock-in for tests."""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import Any, Protocol

import httpx

from qa_orchestrator.embedding_config import EmbeddingConfig

logger = logging.getLogger(__name__)


class EmbeddingProviderError(Exception):
    """Controlled embedding failure — never includes secrets."""


class EmbeddingDimensionError(EmbeddingProviderError):
    pass


class EmbeddingProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    @property
    def embedding_version(self) -> str: ...

    @property
    def normalize(self) -> bool: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...

    def metadata(self) -> dict[str, str | int | bool]: ...


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) > 1]


def compute_embedding_version(provider: str, model: str, dimensions: int, *, normalize: bool = True) -> str:
    payload = f"{provider}:{model}:{dimensions}:{normalize}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _normalize_vector(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def validate_vector_dimensions(vec: list[float], expected: int, *, context: str = "") -> None:
    if len(vec) != expected:
        raise EmbeddingDimensionError(
            f"embedding dimension mismatch {len(vec)} != {expected}" + (f" ({context})" if context else "")
        )


class DeterministicEmbeddingProvider:
    """Hash-seeded dense vectors — stable, offline, no external API."""

    def __init__(self, dimensions: int = 64, *, normalize: bool = True, model: str = "hash-v1") -> None:
        self._dimensions = max(8, dimensions)
        self._normalize = normalize
        self._model = model
        self._version = compute_embedding_version("deterministic", model, self._dimensions, normalize=normalize)

    @property
    def provider_name(self) -> str:
        return "deterministic"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def embedding_version(self) -> str:
        return self._version

    @property
    def normalize(self) -> bool:
        return self._normalize

    def metadata(self) -> dict[str, str | int | bool]:
        return {
            "embedding_provider": self.provider_name,
            "embedding_model": self.model_name,
            "embedding_dimensions": self.dimensions,
            "embedding_version": self.embedding_version,
            "embedding_normalize": self.normalize,
        }

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        tokens = _tokenize(text)
        vec = [0.0] * self._dimensions
        if not tokens:
            return vec
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(self._dimensions):
                byte = digest[i % len(digest)]
                vec[i] += ((byte / 255.0) * 2.0 - 1.0) / len(tokens)
        if self._normalize:
            vec = _normalize_vector(vec)
        return vec


class ProductionEmbeddingProvider:
    """OpenAI-compatible embeddings API via httpx — credentials from environment only."""

    def __init__(
        self,
        config: EmbeddingConfig,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        if config.provider != "production":
            raise EmbeddingProviderError("ProductionEmbeddingProvider requires provider=production")
        if not config.api_key:
            raise EmbeddingProviderError("production embedding requires QA_EMBEDDING_API_KEY or OPENAI_API_KEY")
        self._config = config
        self._dimensions = config.dimensions
        self._normalize = config.normalize
        self._version = config.embedding_version()
        timeout = max(1.0, config.timeout_ms / 1000.0)
        self._client = http_client or httpx.Client(timeout=timeout)

    @property
    def provider_name(self) -> str:
        return "production"

    @property
    def model_name(self) -> str:
        return self._config.model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def embedding_version(self) -> str:
        return self._version

    @property
    def normalize(self) -> bool:
        return self._normalize

    def metadata(self) -> dict[str, str | int | bool]:
        return self._config.metadata_dict()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        batch_size = max(1, self._config.batch_size)
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            out.extend(self._request_embeddings(batch))
        return out

    def embed_query(self, text: str) -> list[float]:
        vectors = self._request_embeddings([text])
        if not vectors:
            raise EmbeddingProviderError("empty embedding response for query")
        return vectors[0]

    def _request_embeddings(self, texts: list[str]) -> list[list[float]]:
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self._config.model, "input": texts}
        if self._dimensions:
            payload["dimensions"] = self._dimensions
        try:
            response = self._client.post(self._config.api_url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise EmbeddingProviderError("embedding request timed out") from exc
        except httpx.HTTPError as exc:
            raise EmbeddingProviderError(f"embedding request failed: {exc.__class__.__name__}") from exc

        if response.status_code == 401:
            raise EmbeddingProviderError("embedding authentication failed")
        if response.status_code == 429:
            raise EmbeddingProviderError("embedding rate limit exceeded")
        if response.status_code >= 400:
            raise EmbeddingProviderError(f"embedding API error status={response.status_code}")

        try:
            data = response.json()
        except ValueError as exc:
            raise EmbeddingProviderError("malformed embedding API response") from exc

        entries = data.get("data")
        if not isinstance(entries, list):
            raise EmbeddingProviderError("malformed embedding API response: missing data")

        vectors: list[list[float]] = []
        for idx, entry in enumerate(entries):
            embedding = entry.get("embedding") if isinstance(entry, dict) else None
            if not isinstance(embedding, list):
                raise EmbeddingProviderError(f"malformed embedding at index {idx}")
            vec = [float(x) for x in embedding]
            validate_vector_dimensions(vec, self._dimensions, context=f"batch index {idx}")
            if self._normalize:
                vec = _normalize_vector(vec)
            vectors.append(vec)
        if len(vectors) != len(texts):
            raise EmbeddingProviderError("embedding batch size mismatch")
        return vectors


def create_embedding_provider(
    config: EmbeddingConfig | None = None,
    *,
    http_client: httpx.Client | None = None,
) -> DeterministicEmbeddingProvider | ProductionEmbeddingProvider:
    cfg = config or EmbeddingConfig.from_env()
    if cfg.provider == "production":
        return ProductionEmbeddingProvider(cfg, http_client=http_client)
    if cfg.provider != "deterministic":
        raise EmbeddingProviderError(f"unsupported embedding provider: {cfg.provider}")
    return DeterministicEmbeddingProvider(cfg.dimensions, normalize=cfg.normalize, model=cfg.model)


def build_sparse_vector(text: str) -> dict[int, float]:
    """Simple token-hash sparse vector for lexical hybrid retrieval."""
    sparse: dict[int, float] = {}
    for token in _tokenize(text):
        idx = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16) % 1_000_003
        sparse[idx] = sparse.get(idx, 0.0) + 1.0
    if not sparse:
        return sparse
    norm = math.sqrt(sum(v * v for v in sparse.values())) or 1.0
    return {k: v / norm for k, v in sparse.items()}


def sparse_dot(a: dict[int, float], b: dict[int, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(weight * b.get(idx, 0.0) for idx, weight in a.items())
