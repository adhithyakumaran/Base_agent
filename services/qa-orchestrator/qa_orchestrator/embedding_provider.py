"""Embedding provider abstraction — replaceable, no vendor lock-in for tests."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol


class EmbeddingProvider(Protocol):
    @property
    def dimensions(self) -> int: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) > 1]


class DeterministicEmbeddingProvider:
    """Hash-seeded dense vectors — stable, offline, no external API."""

    def __init__(self, dimensions: int = 64) -> None:
        self._dimensions = max(8, dimensions)

    @property
    def dimensions(self) -> int:
        return self._dimensions

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
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


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
