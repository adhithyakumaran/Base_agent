"""P5 — production embeddings, versioning, benchmark, and failure handling tests."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import yaml

from qa_orchestrator.embedding_config import EmbeddingConfig
from qa_orchestrator.embedding_provider import (
    DeterministicEmbeddingProvider,
    EmbeddingDimensionError,
    EmbeddingProviderError,
    ProductionEmbeddingProvider,
    create_embedding_provider,
    validate_vector_dimensions,
)
from qa_orchestrator.intent_classifier import IntentClassifier
from qa_orchestrator.knowledge_indexer import KnowledgeIndexer
from qa_orchestrator.knowledge_retriever import KnowledgeRetriever
from qa_orchestrator.llm_client import PlannerLlmClient
from qa_orchestrator.qa_planner import QaPlanner
from qa_orchestrator.qdrant_config import QdrantConfig
from qa_orchestrator.query_preprocessing import preprocess_query
from qa_orchestrator.retrieval_eval import BENCHMARK_CASES, compare_retrieval_strategies, evaluate_retriever
from qa_orchestrator.vector_store import (
    CollectionCompatibilityError,
    InMemoryVectorStore,
    build_stored_point,
)

DISCOVERY_ROOT = "data/discovery-kb"


@pytest.fixture(autouse=True)
def disable_qdrant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QA_QDRANT_ENABLED", "false")
    monkeypatch.setenv("QA_EMBEDDING_PROVIDER", "deterministic")


def _graph():
    from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph

    return FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)


def _retriever(store: InMemoryVectorStore | None = None) -> KnowledgeRetriever:
    graph = _graph()
    emb = DeterministicEmbeddingProvider(64)
    store = store or InMemoryVectorStore(emb)
    cfg = EmbeddingConfig(provider="deterministic", model="hash-v1", dimensions=64)
    indexer = KnowledgeIndexer(
        discovery_root=DISCOVERY_ROOT,
        automation_dir="apps/automation",
        config=QdrantConfig(enabled=False, dense_dimensions=64),
        embedding_config=cfg,
        store=store,
        embedding=emb,
    )
    indexer.index_all()
    return KnowledgeRetriever(
        graph,
        config=QdrantConfig(enabled=False, dense_dimensions=64),
        store=store,
        embedding=emb,
        embedding_config=cfg,
        indexer=indexer,
    )


def test_invalid_provider_configuration():
    cfg = EmbeddingConfig(provider="unknown-provider", model="x", dimensions=64)
    with pytest.raises(EmbeddingProviderError):
        create_embedding_provider(cfg)


def test_production_provider_requires_api_key():
    cfg = EmbeddingConfig(provider="production", model="text-embedding-3-small", dimensions=64, api_key="")
    with pytest.raises(EmbeddingProviderError):
        ProductionEmbeddingProvider(cfg)


def test_production_provider_mock_success():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        vectors = [[0.1] * 64 for _ in payload["input"]]
        data = [{"embedding": v, "index": i} for i, v in enumerate(vectors)]
        return httpx.Response(200, json={"data": data})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    cfg = EmbeddingConfig(
        provider="production",
        model="text-embedding-3-small",
        dimensions=64,
        api_key="test-key",
        api_url="https://example.test/v1/embeddings",
    )
    provider = ProductionEmbeddingProvider(cfg, http_client=client)
    vec = provider.embed_query("check login")
    assert len(vec) == 64
    assert provider.provider_name == "production"
    assert provider.embedding_version


def test_production_provider_auth_failure():
    transport = httpx.MockTransport(lambda req: httpx.Response(401, json={"error": "bad key"}))
    cfg = EmbeddingConfig(
        provider="production",
        model="m",
        dimensions=8,
        api_key="bad",
        api_url="https://example.test/v1/embeddings",
    )
    provider = ProductionEmbeddingProvider(cfg, http_client=httpx.Client(transport=transport))
    with pytest.raises(EmbeddingProviderError, match="authentication"):
        provider.embed_query("x")


def test_production_provider_rate_limit():
    transport = httpx.MockTransport(lambda req: httpx.Response(429, json={"error": "rate"}))
    cfg = EmbeddingConfig(provider="production", model="m", dimensions=8, api_key="k", api_url="https://x/v1/embeddings")
    provider = ProductionEmbeddingProvider(cfg, http_client=httpx.Client(transport=transport))
    with pytest.raises(EmbeddingProviderError, match="rate limit"):
        provider.embed_query("x")


def test_production_provider_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    cfg = EmbeddingConfig(provider="production", model="m", dimensions=8, api_key="k", api_url="https://x/v1/embeddings")
    provider = ProductionEmbeddingProvider(cfg, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(EmbeddingProviderError, match="timed out"):
        provider.embed_query("x")


def test_malformed_provider_response():
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"data": [{"bad": True}]}))
    cfg = EmbeddingConfig(provider="production", model="m", dimensions=8, api_key="k", api_url="https://x/v1/embeddings")
    provider = ProductionEmbeddingProvider(cfg, http_client=httpx.Client(transport=transport))
    with pytest.raises(EmbeddingProviderError, match="malformed"):
        provider.embed_query("x")


def test_wrong_vector_dimensions():
    with pytest.raises(EmbeddingDimensionError):
        validate_vector_dimensions([0.1, 0.2], 8)


def test_embedding_metadata_on_document():
    from qa_orchestrator.qa_knowledge_models import QaKnowledgeDocument

    emb = DeterministicEmbeddingProvider(64, model="hash-v1")
    doc = QaKnowledgeDocument(
        document_id="flow:BF-LOGIN-001",
        document_type="FLOW",
        flow_id="BF-LOGIN-001",
        title="Login",
        text="login",
        source="test",
        status="READY",
        source_hash="abc",
    )
    point = build_stored_point(doc, emb)
    assert point.payload["embedding_provider"] == "deterministic"
    assert point.payload["embedding_model"] == "hash-v1"
    assert point.payload["embedding_dimensions"] == 64
    assert point.payload["embedding_version"]


def test_batch_indexing_skips_unchanged(tmp_path: Path):
    kb = tmp_path / "kb"
    auto = tmp_path / "auto"
    flows = kb / "flows"
    flows.mkdir(parents=True)
    (flows / "index.yaml").write_text(
        yaml.safe_dump({"sme_ready": ["BF-LOGIN-001"], "flows": [{"id": "BF-LOGIN-001", "file": "BF-LOGIN-001.yaml", "name": "Login", "status": "READY"}]}),
        encoding="utf-8",
    )
    (flows / "BF-LOGIN-001.yaml").write_text(yaml.safe_dump({"flow_id": "BF-LOGIN-001", "purpose": "login"}), encoding="utf-8")
    emb = DeterministicEmbeddingProvider(64)
    store = InMemoryVectorStore(emb)
    indexer = KnowledgeIndexer(discovery_root=kb, automation_dir=auto, store=store, embedding=emb)
    first = indexer.index_all()
    second = indexer.index_all()
    assert first.embedded >= 1
    assert second.unchanged >= first.embedded
    assert second.embedded == 0


def test_partial_batch_embedding_failure_continues(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    kb = tmp_path / "kb"
    auto = tmp_path / "auto"
    flows = kb / "flows"
    flows.mkdir(parents=True)
    (flows / "index.yaml").write_text(
        yaml.safe_dump(
            {
                "sme_ready": ["BF-LOGIN-001", "BF-PRODUCT-003"],
                "flows": [
                    {"id": "BF-LOGIN-001", "file": "BF-LOGIN-001.yaml", "name": "Login", "status": "READY"},
                    {"id": "BF-PRODUCT-003", "file": "BF-PRODUCT-003.yaml", "name": "Search", "status": "READY"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (flows / "BF-LOGIN-001.yaml").write_text(yaml.safe_dump({"flow_id": "BF-LOGIN-001", "purpose": "login"}), encoding="utf-8")
    (flows / "BF-PRODUCT-003.yaml").write_text(yaml.safe_dump({"flow_id": "BF-PRODUCT-003", "purpose": "search sku"}), encoding="utf-8")

    class FlakyEmbedding(DeterministicEmbeddingProvider):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            if any("search sku" in t for t in texts):
                raise EmbeddingProviderError("simulated batch failure")
            return super().embed_documents(texts)

    emb = FlakyEmbedding(64)
    store = InMemoryVectorStore(emb)
    indexer = KnowledgeIndexer(discovery_root=kb, automation_dir=auto, store=store, embedding=emb, embedding_config=EmbeddingConfig(batch_size=1))
    stats = indexer.index_all()
    assert stats.embedding_failed >= 1
    assert stats.upserted >= 1


    def test_collection_embedding_metadata_mismatch():
        qdrant = __import__("qa_orchestrator.vector_store", fromlist=["QdrantVectorStore"]).QdrantVectorStore

        class Info:
            class config:
                class params:
                    vectors = {"dense": type("V", (), {"size": 32})()}

        emb = DeterministicEmbeddingProvider(64, model="hash-v2")
        qstore = object.__new__(qdrant)
        qstore.embedding = emb
        with pytest.raises(CollectionCompatibilityError, match="dimension mismatch"):
            qstore._validate_existing_collection(Info(), emb.metadata())


def test_query_preprocessing_preserves_original():
    normalized, meta = preprocess_query("  Search   SKU  ABC123  ")
    assert "Search" in str(meta["original_query"])
    assert meta["extracted_sku"] == "ABC123"


def test_exact_id_regression_flow():
    retriever = _retriever()
    result = retriever.retrieve("BF-PRODUCT-003", sme_ready_only=False, approval_only=False, top_k=5)
    assert result.items[0].document.document_id == "flow:BF-PRODUCT-003"
    assert result.items[0].retrieval_method == "EXACT_ID"


def test_exact_id_regression_test_case():
    retriever = _retriever()
    result = retriever.retrieve("TC-BF-PRODUCT-003-P01", sme_ready_only=False, approval_only=False, top_k=5)
    ids = [item.document.document_id for item in result.items]
    assert "test:TC-BF-PRODUCT-003-P01" in ids


def test_benchmark_size():
    assert 25 <= len(BENCHMARK_CASES) <= 40


def test_evaluate_retriever_metrics():
    report = evaluate_retriever(_retriever(), k=5, retrieval_mode="hybrid")
    assert report["queries"] == len(BENCHMARK_CASES)
    assert "recall_at_1" in report
    assert "recall_at_10" in report
    assert "exact_id_benchmark_pass_rate" in report
    assert report["exact_id_benchmark_pass_rate"] == 1.0


def test_compare_retrieval_strategies():
    comparison = compare_retrieval_strategies(_retriever(), k=5)
    assert len(comparison["comparison"]) == 3
    methods = {row["method"] for row in comparison["comparison"]}
    assert methods == {"lexical", "dense", "hybrid"}


def test_retrieval_diagnostics_observability():
    result = _retriever().retrieve("check login", sme_ready_only=False, approval_only=False)
    diag = result.diagnostics
    assert diag.embedding_provider == "deterministic"
    assert diag.embedding_model
    assert diag.embedding_dimensions == 64
    assert diag.embedding_version
    assert diag.original_query == "check login"
    assert diag.preprocessed_query


@pytest.mark.parametrize(
    "goal",
    [
        "Check login",
        "Test invalid login",
        "Search SKU ABC123",
        "test product search",
        "test a new product filter",
    ],
)
def test_planner_regression_with_retrieval(goal: str):
    graph = _graph()
    retriever = _retriever()
    intent = IntentClassifier(graph, PlannerLlmClient(enabled=False)).classify(goal)
    planning = QaPlanner(graph, retriever=retriever).plan(intent)
    assert planning.execution_allowed is False
    if goal.lower().startswith("search sku"):
        assert planning.validated_parameters.get("sku") == "ABC123"
        assert "BF-PRODUCT-003" in planning.candidate_flows
    if "login" in goal.lower() and "invalid" not in goal.lower():
        assert "BF-LOGIN-001" in planning.candidate_flows
