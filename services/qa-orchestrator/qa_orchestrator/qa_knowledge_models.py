"""QA knowledge retrieval document and result models — P4 semantic layer."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

QaDocumentType = Literal["FLOW", "TEST_CASE", "BUSINESS_RULE", "STEP", "EXPLORATION", "HEALING"]
RetrievalMethod = Literal[
    "LEXICAL_FALLBACK",
    "DENSE",
    "SPARSE",
    "HYBRID_RRF",
    "EXACT_ID",
    "DISABLED",
]
RelevanceClass = Literal["EXACT", "HIGH", "MEDIUM", "LOW"]


class QaKnowledgeDocument(BaseModel):
    document_id: str
    document_type: QaDocumentType
    flow_id: str = ""
    test_id: str = ""
    step_id: str = ""
    title: str = ""
    text: str = ""
    source: str = ""
    status: str = ""
    sme_ready: bool = False
    approval_state: str = ""
    polarity: str = ""
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_path: str = ""
    source_hash: str = ""
    indexed_at: str = ""
    version: int = 1
    embedding_provider: str = ""
    embedding_model: str = ""
    embedding_dimensions: int = 0
    embedding_version: str = ""


class RetrievedKnowledgeItem(BaseModel):
    document: QaKnowledgeDocument
    score: float = 0.0
    retrieval_method: RetrievalMethod = "LEXICAL_FALLBACK"
    matched_metadata: dict[str, Any] = Field(default_factory=dict)
    source_reference: str = ""
    relevance: RelevanceClass = "MEDIUM"


class RetrievalDiagnostics(BaseModel):
    retrieval_used: bool = False
    method: RetrievalMethod = "DISABLED"
    qdrant_enabled: bool = False
    qdrant_available: bool = False
    fallback_reason: str | None = None
    query: str = ""
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    filtered: list[dict[str, Any]] = Field(default_factory=list)
    selected: list[str] = Field(default_factory=list)
    top_k: int = 0
    exact_id_hits: list[str] = Field(default_factory=list)
    original_query: str = ""
    preprocessed_query: str = ""
    embedding_provider: str = ""
    embedding_model: str = ""
    embedding_dimensions: int = 0
    embedding_version: str = ""
    latency_ms: int = 0


class RetrievalResult(BaseModel):
    query: str
    items: list[RetrievedKnowledgeItem] = Field(default_factory=list)
    flow_ids: list[str] = Field(default_factory=list)
    diagnostics: RetrievalDiagnostics = Field(default_factory=RetrievalDiagnostics)


class IndexingStats(BaseModel):
    flows: int = 0
    test_cases: int = 0
    business_rules: int = 0
    steps: int = 0
    exploration: int = 0
    healing: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)
    documents_seen: int = 0
    embedded: int = 0
    upserted: int = 0
    embedding_failed: int = 0
    batches: int = 0
