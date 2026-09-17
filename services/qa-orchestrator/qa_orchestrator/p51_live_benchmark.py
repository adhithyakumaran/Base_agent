"""P5.1 — live production embedding benchmark runner."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from qa_orchestrator.embedding_config import EmbeddingConfig
from qa_orchestrator.embedding_provider import (
    EmbeddingProvider,
    EmbeddingProviderError,
    create_embedding_provider,
)
from qa_orchestrator.intent_classifier import IntentClassifier
from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph
from qa_orchestrator.knowledge_indexer import KnowledgeIndexer
from qa_orchestrator.knowledge_retriever import KnowledgeRetriever, RetrievalMode
from qa_orchestrator.llm_client import PlannerLlmClient
from qa_orchestrator.param_validator import params_to_env, validate_run_params
from qa_orchestrator.qa_planner import QaPlanner
from qa_orchestrator.qdrant_config import QdrantConfig
from qa_orchestrator.retrieval_eval import (
    BENCHMARK_CASES,
    evaluate_retriever,
    exact_document_hit_rate,
)
from qa_orchestrator.vector_store import CollectionCompatibilityError, InMemoryVectorStore

BENCHMARK_VERSION = "p5.1-v1"
DISCOVERY_ROOT = os.environ.get("QA_DISCOVERY_ROOT", "data/discovery-kb")
AUTOMATION_DIR = os.environ.get("QA_AUTOMATION_DIR", "apps/automation")
DEFAULT_REPORT = Path("reports/retrieval/p5-1-production-evaluation.json")

EXACT_ID_QUERIES = [
    ("BF-PRODUCT-003", "flow:BF-PRODUCT-003"),
    ("TC-BF-PRODUCT-003-P01", "test:TC-BF-PRODUCT-003-P01"),
    ("BF-LOGIN-001", "flow:BF-LOGIN-001"),
    ("TC-BF-LOGIN-001-P01", "test:TC-BF-LOGIN-001-P01"),
]

PLANNER_CASES = [
    "Check login",
    "Test invalid login",
    "Search SKU ABC123",
    "test product search",
    "test a new product filter",
]


class CountingEmbeddingProvider:
    """Thin wrapper — counts API calls without changing provider contract."""

    def __init__(self, inner: EmbeddingProvider) -> None:
        self._inner = inner
        self.document_texts = 0
        self.query_calls = 0

    @property
    def provider_name(self) -> str:
        return self._inner.provider_name

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    @property
    def dimensions(self) -> int:
        return self._inner.dimensions

    @property
    def embedding_version(self) -> str:
        return self._inner.embedding_version

    @property
    def normalize(self) -> bool:
        return self._inner.normalize

    def metadata(self) -> dict[str, str | int | bool]:
        return self._inner.metadata()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_texts += len(texts)
        return self._inner.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        self.query_calls += 1
        return self._inner.embed_query(text)


def _build_retriever(
    graph: FlowKnowledgeGraph,
    embedding_config: EmbeddingConfig,
    *,
    use_qdrant: bool = False,
) -> tuple[KnowledgeRetriever, CountingEmbeddingProvider]:
    inner = create_embedding_provider(embedding_config)
    counting = CountingEmbeddingProvider(inner)
    qdrant_cfg = QdrantConfig.from_env() if use_qdrant else QdrantConfig(
        enabled=False,
        dense_dimensions=embedding_config.dimensions,
    )
    if use_qdrant:
        qdrant_cfg = QdrantConfig(
            enabled=True,
            url=os.environ.get("QA_QDRANT_URL", "http://127.0.0.1:6333"),
            collection=os.environ.get("QA_QDRANT_COLLECTION", "qa_knowledge_p51"),
            dense_dimensions=embedding_config.dimensions,
            hybrid_enabled=True,
        )
    store = InMemoryVectorStore(counting) if not use_qdrant else __import__(
        "qa_orchestrator.vector_store", fromlist=["create_vector_store"]
    ).create_vector_store(qdrant_cfg, counting)
    indexer = KnowledgeIndexer(
        discovery_root=graph.discovery_root,
        automation_dir=graph.automation_dir,
        config=qdrant_cfg,
        embedding_config=embedding_config,
        store=store,
        embedding=counting,
    )
    retriever = KnowledgeRetriever(
        graph,
        config=qdrant_cfg,
        store=store,
        embedding=counting,
        embedding_config=embedding_config,
        indexer=indexer,
    )
    return retriever, counting


def _summarize_report(report: dict) -> dict[str, Any]:
    return {
        "method": report.get("retrieval_mode") or report.get("method"),
        "recall_at_1": report["recall_at_1"],
        "recall_at_3": report["recall_at_3"],
        "recall_at_5": report["recall_at_5"],
        "recall_at_10": report["recall_at_10"],
        "mrr": report["mrr"],
        "exact_id_hit_rate": report["exact_id_hit_rate"],
        "exact_document_hit_rate": report.get("exact_document_hit_rate"),
        "exact_id_benchmark_pass_rate": report.get("exact_id_benchmark_pass_rate"),
        "irrelevant_rate": report["irrelevant_rate"],
        "provider": report.get("provider"),
        "model": report.get("model"),
        "dimensions": report.get("dimensions"),
        "embedding_calls_documents": report.get("embedding_calls_documents", 0),
        "embedding_calls_queries": report.get("embedding_calls_queries", 0),
        "latency_ms": report.get("latency_ms", 0),
        "failures": report.get("failures", []),
    }


def run_mode(
    retriever: KnowledgeRetriever,
    counter: CountingEmbeddingProvider,
    mode: RetrievalMode,
    *,
    k: int = 5,
) -> dict[str, Any]:
    started = time.perf_counter()
    before_doc = counter.document_texts
    before_q = counter.query_calls
    report = evaluate_retriever(retriever, k=k, retrieval_mode=mode)
    report["latency_ms"] = int((time.perf_counter() - started) * 1000)
    report["embedding_calls_documents"] = counter.document_texts - before_doc
    report["embedding_calls_queries"] = counter.query_calls - before_q
    report["failures"] = []
    return report


def verify_exact_id_cases(retriever: KnowledgeRetriever) -> dict[str, Any]:
    rows = []
    for query, expected_doc in EXACT_ID_QUERIES:
        result = retriever.retrieve(query, sme_ready_only=False, approval_only=False, top_k=5, retrieval_mode="hybrid")
        top = result.items[0] if result.items else None
        rows.append(
            {
                "query": query,
                "expected_document_id": expected_doc,
                "top_document_id": top.document.document_id if top else None,
                "method": top.retrieval_method if top else None,
                "pass": top is not None and top.document.document_id == expected_doc and top.retrieval_method == "EXACT_ID",
            }
        )
    pass_rate = sum(1 for r in rows if r["pass"]) / len(rows) if rows else 1.0
    return {"cases": rows, "pass_rate": round(pass_rate, 4)}


def run_planner_regression(graph: FlowKnowledgeGraph, retriever: KnowledgeRetriever) -> dict[str, Any]:
    planner = QaPlanner(graph, PlannerLlmClient(enabled=False), retriever=retriever)
    classifier = IntentClassifier(graph, PlannerLlmClient(enabled=False))
    rows = []
    for goal in PLANNER_CASES:
        intent = classifier.classify(goal)
        planning = planner.plan(intent)
        env_map = {}
        param_error = None
        try:
            validated = validate_run_params(planning.validated_parameters)
            env_map = params_to_env(validated)
        except ValueError as exc:
            param_error = str(exc)
        row = {
            "goal": goal,
            "candidate_flows": planning.candidate_flows[:5],
            "validated_parameters": planning.validated_parameters,
            "validated_env_keys": sorted(env_map.keys()),
            "execution_allowed": planning.execution_allowed,
            "polarity": planning.polarity,
            "param_error": param_error,
        }
        if goal.lower().startswith("search sku"):
            row["sku_trace_ok"] = (
                planning.validated_parameters.get("sku") == "ABC123"
                and "BF-PRODUCT-003" in planning.candidate_flows
                and env_map.get("QA_PARAM_SKU") == "ABC123"
            )
        rows.append(row)
    return {"cases": rows, "pass": all(r.get("sku_trace_ok", True) for r in rows)}


def run_failure_test(graph: FlowKnowledgeGraph, *, dimensions: int) -> dict[str, Any]:
    """Verify production-provider errors surface instead of silent fallback."""
    bad_cfg = EmbeddingConfig(
        provider="production",
        model=os.environ.get("QA_EMBEDDING_MODEL", "text-embedding-3-small"),
        dimensions=dimensions,
        api_key="invalid-key-for-test",
        api_url="http://127.0.0.1:1/v1/embeddings",
    )
    try:
        provider = create_embedding_provider(bad_cfg)
        provider.embed_query("check login")
        return {
            "controlled_failure": False,
            "message": "expected embedding failure did not occur",
            "test": "unavailable_provider",
        }
    except EmbeddingProviderError as exc:
        provider_error = {
            "controlled_failure": True,
            "error_type": "EmbeddingProviderError",
            "message": str(exc),
            "test": "unavailable_provider",
        }
    except Exception as exc:
        return {
            "controlled_failure": True,
            "error_type": exc.__class__.__name__,
            "message": str(exc),
            "test": "unavailable_provider",
        }

    retriever, _ = _build_retriever(graph, bad_cfg)
    stats = retriever.indexer.index_all()
    provider_error["indexer_embedding_failed"] = stats.embedding_failed
    provider_error["indexer_errors_recorded"] = any("embedding batch failed" in err for err in stats.errors)
    return provider_error


def _intent_subset(report: dict) -> dict[str, float]:
    intent_rows = [r for r in report.get("cases", []) if r.get("category") == "intent"]
    if not intent_rows:
        return {"recall_at_5": 0.0, "mrr": 0.0, "count": 0}
    return {
        "recall_at_5": round(sum(r["recall_at_5"] for r in intent_rows) / len(intent_rows), 4),
        "mrr": round(sum(r["mrr"] for r in intent_rows) / len(intent_rows), 4),
        "count": len(intent_rows),
    }


def run_live_benchmark(
    *,
    output_path: Path | None = None,
    use_qdrant: bool = False,
    production_config: EmbeddingConfig | None = None,
) -> dict[str, Any]:
    output_path = output_path or DEFAULT_REPORT
    graph = FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT, automation_dir=AUTOMATION_DIR)
    started = time.perf_counter()
    failures: list[str] = []

    det_cfg = EmbeddingConfig(provider="deterministic", model="hash-v1", dimensions=64)
    det_retriever, det_counter = _build_retriever(graph, det_cfg, use_qdrant=False)
    det_index = det_retriever.indexer.index_all()

    modes: list[tuple[str, KnowledgeRetriever, CountingEmbeddingProvider, RetrievalMode]] = [
        ("lexical", det_retriever, det_counter, "lexical"),
        ("deterministic_dense", det_retriever, det_counter, "dense"),
        ("deterministic_hybrid", det_retriever, det_counter, "hybrid"),
    ]

    prod_cfg = production_config or EmbeddingConfig.from_env()
    prod_retriever: KnowledgeRetriever | None = None
    prod_counter: CountingEmbeddingProvider | None = None
    prod_index_stats = None
    production_status = "not_run"

    if prod_cfg.provider != "production":
        prod_cfg = EmbeddingConfig(
            provider="production",
            model=os.environ.get("QA_EMBEDDING_MODEL", "text-embedding-3-small"),
            dimensions=int(os.environ.get("QA_EMBEDDING_DIMENSIONS", "1536")),
            api_key=os.environ.get("QA_EMBEDDING_API_KEY") or os.environ.get("OPENAI_API_KEY") or "",
            api_url=os.environ.get("QA_EMBEDDING_API_URL", "https://api.openai.com/v1/embeddings"),
            batch_size=int(os.environ.get("QA_EMBEDDING_BATCH_SIZE", "32")),
        )

    try:
        prod_retriever, prod_counter = _build_retriever(graph, prod_cfg, use_qdrant=use_qdrant)
        prod_index_stats = prod_retriever.indexer.index_all()
        modes.extend(
            [
                ("production_dense", prod_retriever, prod_counter, "dense"),
                ("production_hybrid", prod_retriever, prod_counter, "hybrid"),
            ]
        )
        production_status = "success"
    except (EmbeddingProviderError, CollectionCompatibilityError) as exc:
        failures.append(f"production setup failed: {exc}")
        production_status = "failed"
    except Exception as exc:
        failures.append(f"production setup failed: {exc}")
        production_status = "failed"

    mode_reports: dict[str, dict] = {}
    total_doc_calls = det_counter.document_texts + (prod_counter.document_texts if prod_counter else 0)
    total_query_calls = 0
    for label, retr, counter, mode in modes:
        try:
            report = run_mode(retr, counter, mode, k=5)
            mode_reports[label] = report
            total_query_calls += report.get("embedding_calls_queries", 0)
        except Exception as exc:
            failures.append(f"{label} failed: {exc}")
            mode_reports[label] = {"failures": [str(exc)]}

    exact_id = verify_exact_id_cases(det_retriever)
    if prod_retriever is not None:
        prod_exact = verify_exact_id_cases(prod_retriever)
        exact_id["production_hybrid"] = prod_exact
        if prod_exact["pass_rate"] < 1.0:
            failures.append("production exact-ID regression detected")

    planner = run_planner_regression(graph, det_retriever)
    failure_test = run_failure_test(graph, dimensions=prod_cfg.dimensions)
    if not failure_test.get("controlled_failure"):
        failures.append(f"failure test: {failure_test.get('message', 'unknown')}")

    qdrant_validation = {"attempted": use_qdrant, "available": False, "notes": []}
    if use_qdrant:
        store = prod_retriever.store if prod_retriever else det_retriever.store
        qdrant_validation["available"] = bool(getattr(store, "available", False))
        qdrant_validation["init_error"] = getattr(store, "init_error", None)
        if prod_retriever and qdrant_validation["available"]:
            qdrant_validation["notes"].append("collection checked via ensure_collection during indexing")

    comparison_table = []
    for label in [
        "lexical",
        "deterministic_dense",
        "deterministic_hybrid",
        "production_dense",
        "production_hybrid",
    ]:
        if label in mode_reports and "recall_at_1" in mode_reports[label]:
            row = _summarize_report(mode_reports[label])
            row["method"] = label
            comparison_table.append(row)

    det_dense = mode_reports.get("deterministic_dense", {})
    det_hybrid = mode_reports.get("deterministic_hybrid", {})
    prod_dense = mode_reports.get("production_dense", {})
    prod_hybrid = mode_reports.get("production_hybrid", {})

    semantic_analysis = {
        "production_dense_beats_deterministic_dense": (
            prod_dense.get("recall_at_5", 0) > det_dense.get("recall_at_5", 0)
            if prod_dense and det_dense
            else None
        ),
        "production_hybrid_beats_deterministic_hybrid": (
            prod_hybrid.get("recall_at_5", 0) > det_hybrid.get("recall_at_5", 0)
            if prod_hybrid and det_hybrid
            else None
        ),
        "intent_recall_at_5": {
            "deterministic_hybrid": _intent_subset(det_hybrid),
            "production_hybrid": _intent_subset(prod_hybrid) if prod_hybrid else None,
        },
        "exact_id_preserved": exact_id.get("pass_rate") == 1.0,
        "difficult_queries": [
            row["query"]
            for row in (prod_hybrid.get("cases") or det_hybrid.get("cases") or [])
            if row.get("category") not in {"negative"} and row.get("recall_at_5", 1) < 1.0
        ],
    }

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "benchmark_version": BENCHMARK_VERSION,
        "query_count": len(BENCHMARK_CASES),
        "production_status": production_status,
        "provider": prod_cfg.provider if production_status == "success" else det_cfg.provider,
        "model": prod_cfg.model if production_status == "success" else det_cfg.model,
        "dimensions": prod_cfg.dimensions if production_status == "success" else det_cfg.dimensions,
        "embedding_api_url_host": _safe_url_host(prod_cfg.api_url),
        "indexing": {
            "deterministic": det_index.model_dump() if det_index else {},
            "production": prod_index_stats.model_dump() if prod_index_stats else None,
        },
        "metrics_by_mode": {k: _summarize_report(v) for k, v in mode_reports.items() if "recall_at_1" in v},
        "comparison_table": comparison_table,
        "semantic_analysis": semantic_analysis,
        "exact_id_results": exact_id,
        "planner_regression": planner,
        "failure_test": failure_test,
        "qdrant_validation": qdrant_validation,
        "totals": {
            "embedding_calls_documents": total_doc_calls,
            "embedding_calls_queries": total_query_calls,
            "benchmark_latency_ms": int((time.perf_counter() - started) * 1000),
            "failure_count": len(failures),
        },
        "failures": failures,
        "mode_reports": mode_reports,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _safe_url_host(url: str) -> str:
    if not url:
        return ""
    try:
        from urllib.parse import urlparse

        return urlparse(url).netloc or url.split("/")[2]
    except Exception:
        return "unknown"


def main() -> None:
    use_qdrant = os.environ.get("QA_QDRANT_ENABLED", "").lower() in {"1", "true", "yes"}
    report = run_live_benchmark(use_qdrant=use_qdrant)
    print(json.dumps({"report_path": str(DEFAULT_REPORT), "summary": report["comparison_table"]}, indent=2))


if __name__ == "__main__":
    main()
