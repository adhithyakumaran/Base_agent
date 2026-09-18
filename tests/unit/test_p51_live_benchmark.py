"""P5.1 — live production embedding benchmark runner tests."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from qa_orchestrator.embedding_config import EmbeddingConfig
from qa_orchestrator.embedding_provider import EmbeddingProviderError, ProductionEmbeddingProvider
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.p51_live_benchmark import (
    BENCHMARK_VERSION,
    run_failure_test,
    run_live_benchmark,
    run_planner_regression,
    verify_exact_id_cases,
)
from qa_orchestrator.qdrant_config import QdrantConfig
from qa_orchestrator.knowledge_indexer import KnowledgeIndexer
from qa_orchestrator.knowledge_retriever import KnowledgeRetriever
from qa_orchestrator.vector_store import InMemoryVectorStore

DISCOVERY_ROOT = "data/discovery-kb"


@pytest.fixture(autouse=True)
def disable_qdrant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QA_QDRANT_ENABLED", "false")
    monkeypatch.setenv("QA_EMBEDDING_PROVIDER", "deterministic")


def _mock_production_config() -> EmbeddingConfig:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        inputs = payload["input"]
        texts = [inputs] if isinstance(inputs, str) else list(inputs)
        vectors = [[0.01 * (i + 1)] * 64 for i, _ in enumerate(texts)]
        data = [{"embedding": vec, "index": i} for i, vec in enumerate(vectors)]
        return httpx.Response(200, json={"data": data})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    cfg = EmbeddingConfig(
        provider="production",
        model="mock-embedding",
        dimensions=64,
        api_key="test-key",
        api_url="https://mock.test/v1/embeddings",
    )
    cfg._test_http_client = client  # type: ignore[attr-defined]
    return cfg


def _build_mock_retriever(graph: FlowKnowledgeGraph, cfg: EmbeddingConfig) -> KnowledgeRetriever:
    from qa_orchestrator.embedding_provider import create_embedding_provider
    from qa_orchestrator.p51_live_benchmark import CountingEmbeddingProvider

    http_client = getattr(cfg, "_test_http_client", None)
    inner = create_embedding_provider(cfg, http_client=http_client)
    counting = CountingEmbeddingProvider(inner)
    qdrant_cfg = QdrantConfig(enabled=False, dense_dimensions=cfg.dimensions)
    store = InMemoryVectorStore(counting)
    indexer = KnowledgeIndexer(
        discovery_root=graph.discovery_root,
        automation_dir=graph.automation_dir,
        config=qdrant_cfg,
        embedding_config=cfg,
        store=store,
        embedding=counting,
    )
    return KnowledgeRetriever(
        graph,
        config=qdrant_cfg,
        store=store,
        embedding=counting,
        embedding_config=cfg,
        indexer=indexer,
    )


def test_failure_test_reports_unavailable_provider():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT, automation_dir="apps/automation")
    result = run_failure_test(graph, dimensions=64)
    assert result["controlled_failure"] is True
    assert result["error_type"] == "EmbeddingProviderError"
    assert result["indexer_embedding_failed"] > 0
    assert result["indexer_errors_recorded"] is True
    assert "api_key" not in result["message"].lower()


def test_verify_exact_id_cases():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT, automation_dir="apps/automation")
    retriever = _build_mock_retriever(graph, EmbeddingConfig(provider="deterministic", model="hash-v1", dimensions=64))
    retriever.indexer.index_all()
    exact = verify_exact_id_cases(retriever)
    assert exact["pass_rate"] == 1.0
    assert all(row["method"] == "EXACT_ID" for row in exact["cases"])


def test_planner_regression_sku_trace():
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT, automation_dir="apps/automation")
    retriever = _build_mock_retriever(graph, EmbeddingConfig(provider="deterministic", model="hash-v1", dimensions=64))
    retriever.indexer.index_all()
    planner = run_planner_regression(graph, retriever)
    assert planner["pass"] is True
    sku_row = next(row for row in planner["cases"] if row["goal"].lower().startswith("search sku"))
    assert sku_row["sku_trace_ok"] is True


def test_run_live_benchmark_with_mock_production(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    output = tmp_path / "p5-1-production-evaluation.json"

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        inputs = payload["input"]
        texts = [inputs] if isinstance(inputs, str) else list(inputs)
        vectors = [[0.01 * (i + 1)] * 64 for i, _ in enumerate(texts)]
        data = [{"embedding": vec, "index": i} for i, vec in enumerate(vectors)]
        return httpx.Response(200, json={"data": data})

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    prod_cfg = EmbeddingConfig(
        provider="production",
        model="mock-embedding",
        dimensions=64,
        api_key="test-key",
        api_url="https://mock.test/v1/embeddings",
    )

    from qa_orchestrator import p51_live_benchmark as mod

    original_build = mod._build_retriever

    def build_with_mock(graph_obj, embedding_config, *, use_qdrant=False):
        if embedding_config.provider == "production":
            inner = ProductionEmbeddingProvider(embedding_config, http_client=mock_client)
            counter = mod.CountingEmbeddingProvider(inner)
            qdrant_cfg = QdrantConfig(enabled=False, dense_dimensions=embedding_config.dimensions)
            store = InMemoryVectorStore(counter)
            indexer = KnowledgeIndexer(
                discovery_root=graph_obj.discovery_root,
                automation_dir=graph_obj.automation_dir,
                config=qdrant_cfg,
                embedding_config=embedding_config,
                store=store,
                embedding=counter,
            )
            retriever = KnowledgeRetriever(
                graph_obj,
                config=qdrant_cfg,
                store=store,
                embedding=counter,
                embedding_config=embedding_config,
                indexer=indexer,
            )
            return retriever, counter
        return original_build(graph_obj, embedding_config, use_qdrant=use_qdrant)

    monkeypatch.setattr(mod, "_build_retriever", build_with_mock)
    report = run_live_benchmark(output_path=output, production_config=prod_cfg)

    assert output.exists()
    raw = output.read_text(encoding="utf-8")
    assert "test-key" not in raw
    assert "QA_EMBEDDING_API_KEY" not in raw
    assert report["benchmark_version"] == BENCHMARK_VERSION
    assert report["query_count"] == 33
    assert report["production_status"] == "success"
    assert set(report["metrics_by_mode"]) >= {
        "lexical",
        "deterministic_dense",
        "deterministic_hybrid",
        "production_dense",
        "production_hybrid",
    }
    assert report["failure_test"]["controlled_failure"] is True
    assert report["exact_id_results"]["pass_rate"] == 1.0
    assert report["planner_regression"]["pass"] is True
    assert report["totals"]["failure_count"] == 0
