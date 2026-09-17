"""QA retrieval benchmark, metrics, and strategy comparison — P5 evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from qa_orchestrator.knowledge_retriever import KnowledgeRetriever, RetrievalMode
from qa_orchestrator.qa_knowledge_models import RetrievalResult

QaDocumentType = Literal["FLOW", "TEST_CASE", "BUSINESS_RULE", "STEP", "EXPLORATION", "HEALING"]


@dataclass(frozen=True)
class RetrievalEvalCase:
    query: str
    expected_document_ids: list[str] = field(default_factory=list)
    expected_flow_ids: list[str] = field(default_factory=list)
    acceptable_document_types: list[str] = field(default_factory=lambda: ["FLOW", "TEST_CASE"])
    forbidden_document_ids: list[str] = field(default_factory=list)
    exact_id_required: bool = False
    category: str = "general"


BENCHMARK_CASES: list[RetrievalEvalCase] = [
    # Exact identifiers
    RetrievalEvalCase("BF-PRODUCT-003", ["flow:BF-PRODUCT-003"], ["BF-PRODUCT-003"], exact_id_required=True, category="exact_id"),
    RetrievalEvalCase("TC-BF-PRODUCT-003-P01", ["test:TC-BF-PRODUCT-003-P01"], ["BF-PRODUCT-003"], exact_id_required=True, category="exact_id"),
    RetrievalEvalCase("BF-LOGIN-001", ["flow:BF-LOGIN-001"], ["BF-LOGIN-001"], exact_id_required=True, category="exact_id"),
    RetrievalEvalCase("TC-BF-LOGIN-001-P01", ["test:TC-BF-LOGIN-001-P01"], ["BF-LOGIN-001"], exact_id_required=True, category="exact_id"),
    # Natural-language intent
    RetrievalEvalCase("check login", ["flow:BF-LOGIN-001"], ["BF-LOGIN-001"], category="intent"),
    RetrievalEvalCase("invalid login", ["flow:BF-LOGIN-001"], ["BF-LOGIN-001"], category="intent"),
    RetrievalEvalCase("search product", ["flow:BF-PRODUCT-003"], ["BF-PRODUCT-003"], category="intent"),
    RetrievalEvalCase("find a product by SKU", ["flow:BF-PRODUCT-003"], ["BF-PRODUCT-003"], category="intent"),
    RetrievalEvalCase("product stock visibility", ["flow:BF-PRODUCT-STOCK-VISIBILITY-009"], ["BF-PRODUCT-STOCK-VISIBILITY-009"], category="intent"),
    RetrievalEvalCase("logout user", ["flow:BF-LOGOUT-002"], ["BF-LOGOUT-002"], category="intent"),
    RetrievalEvalCase("home navigation", ["flow:BF-HOME-010"], ["BF-HOME-010"], category="intent"),
    RetrievalEvalCase("manual invoice", ["flow:BF-MANUAL-INVOICE-009"], ["BF-MANUAL-INVOICE-009"], category="intent"),
    # Synonyms
    RetrievalEvalCase("sign in", ["flow:BF-LOGIN-001"], ["BF-LOGIN-001"], category="synonym"),
    RetrievalEvalCase("product lookup", ["flow:BF-PRODUCT-003"], ["BF-PRODUCT-003"], category="synonym"),
    RetrievalEvalCase("item search", ["flow:BF-PRODUCT-003"], ["BF-PRODUCT-003"], category="synonym"),
    # Parameter-aware
    RetrievalEvalCase("Search SKU ABC123", ["flow:BF-PRODUCT-003"], ["BF-PRODUCT-003"], category="parameterized"),
    RetrievalEvalCase("Search product using item code ABC123", ["flow:BF-PRODUCT-003"], ["BF-PRODUCT-003"], category="parameterized"),
    # Exploration-oriented
    RetrievalEvalCase("discover product search", ["flow:BF-PRODUCT-003"], ["BF-PRODUCT-003"], category="exploration"),
    RetrievalEvalCase("explore login page", ["flow:BF-LOGIN-001"], ["BF-LOGIN-001"], category="exploration"),
    RetrievalEvalCase("find the search control", [], ["BF-PRODUCT-003"], ["STEP"], category="exploration"),
    RetrievalEvalCase("search button", [], ["BF-PRODUCT-003"], ["STEP"], category="exploration"),
    # Negative / unrelated
    RetrievalEvalCase(
        "generate quarterly tax report for martian colony",
        [],
        [],
        forbidden_document_ids=["flow:BF-LOGIN-001", "flow:BF-PRODUCT-003"],
        category="negative",
    ),
    RetrievalEvalCase("test a new product filter", [], [], category="negative"),
    RetrievalEvalCase("checkout martian payment gateway", [], [], category="negative"),
    RetrievalEvalCase("autonomous agent swarm migration", [], [], category="negative"),
    # Additional realistic coverage
    RetrievalEvalCase("run negative login", ["flow:BF-LOGIN-001"], ["BF-LOGIN-001"], category="intent"),
    RetrievalEvalCase("product search", ["flow:BF-PRODUCT-003"], ["BF-PRODUCT-003"], category="intent"),
    RetrievalEvalCase("rivaah wedding wishlist", ["flow:BF-RIVAAH-005"], ["BF-RIVAAH-005"], category="intent"),
    RetrievalEvalCase("best deal browse", ["flow:BF-BEST-DEAL-008"], ["BF-BEST-DEAL-008"], category="intent"),
    RetrievalEvalCase("reports dashboard", ["flow:BF-REPORTS-007"], ["BF-REPORTS-007"], category="intent"),
    RetrievalEvalCase("administration settings", ["flow:BF-ADMINISTRATION-009"], ["BF-ADMINISTRATION-009"], category="intent"),
    RetrievalEvalCase("product catalogue browse", ["flow:BF-PRODUCT-CATALOGUE-006"], ["BF-PRODUCT-CATALOGUE-006"], category="intent"),
    RetrievalEvalCase("stock visibility for SKU", ["flow:BF-PRODUCT-STOCK-VISIBILITY-009"], ["BF-PRODUCT-STOCK-VISIBILITY-009"], category="parameterized"),
]

# Backward-compatible alias
EVAL_CASES = BENCHMARK_CASES


def recall_at_k(result: RetrievalResult, expected_ids: list[str], k: int) -> float:
    if not expected_ids:
        return 1.0
    retrieved = [item.document.document_id for item in result.items[:k]]
    hits = sum(1 for eid in expected_ids if eid in retrieved)
    return hits / len(expected_ids)


def mrr(result: RetrievalResult, expected_ids: list[str]) -> float:
    if not expected_ids:
        return 1.0
    for rank, item in enumerate(result.items, start=1):
        if item.document.document_id in expected_ids:
            return 1.0 / rank
    return 0.0


def exact_id_hit_rate(result: RetrievalResult, expected_flow_ids: list[str]) -> float:
    if not expected_flow_ids:
        return 1.0
    hits = sum(1 for fid in expected_flow_ids if fid in result.flow_ids)
    return hits / len(expected_flow_ids)


def exact_document_hit_rate(result: RetrievalResult, expected_ids: list[str]) -> float:
    if not expected_ids:
        return 1.0
    retrieved = [item.document.document_id for item in result.items]
    hits = sum(1 for eid in expected_ids if eid in retrieved)
    return hits / len(expected_ids)


def irrelevant_retrieval_rate(result: RetrievalResult, forbidden_ids: list[str], *, k: int = 5) -> float:
    if not forbidden_ids:
        return 0.0
    retrieved = [item.document.document_id for item in result.items[:k]]
    hits = sum(1 for fid in forbidden_ids if fid in retrieved)
    return hits / len(forbidden_ids)


def evaluate_retriever(
    retriever: KnowledgeRetriever,
    *,
    k: int = 5,
    retrieval_mode: RetrievalMode = "hybrid",
    cases: list[RetrievalEvalCase] | None = None,
) -> dict:
    retriever.ensure_index()
    rows: list[dict] = []
    metrics = {1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0}
    mrr_sum = 0.0
    exact_flow_sum = 0.0
    exact_doc_sum = 0.0
    irrelevant_sum = 0.0
    eval_cases = cases or BENCHMARK_CASES

    for case in eval_cases:
        top_k = max(k, 10)
        result = retriever.retrieve(
            case.query,
            sme_ready_only=False,
            approval_only=False,
            top_k=top_k,
            retrieval_mode=retrieval_mode,
        )
        row = {
            "query": case.query,
            "category": case.category,
            "recall_at_1": round(recall_at_k(result, case.expected_document_ids, 1), 4),
            "recall_at_3": round(recall_at_k(result, case.expected_document_ids, 3), 4),
            "recall_at_5": round(recall_at_k(result, case.expected_document_ids, 5), 4),
            "recall_at_10": round(recall_at_k(result, case.expected_document_ids, 10), 4),
            "mrr": round(mrr(result, case.expected_document_ids), 4),
            "exact_id_hit_rate": round(exact_id_hit_rate(result, case.expected_flow_ids), 4),
            "exact_document_hit_rate": round(exact_document_hit_rate(result, case.expected_document_ids), 4),
            "irrelevant_rate": round(irrelevant_retrieval_rate(result, case.forbidden_document_ids, k=5), 4),
            "method": result.diagnostics.method,
            "selected": result.diagnostics.selected,
        }
        if case.exact_id_required:
            row["exact_id_required_pass"] = row["exact_document_hit_rate"] == 1.0
        rows.append(row)
        for kk in metrics:
            metrics[kk] += recall_at_k(result, case.expected_document_ids, kk)
        mrr_sum += row["mrr"]
        exact_flow_sum += row["exact_id_hit_rate"]
        exact_doc_sum += row["exact_document_hit_rate"]
        irrelevant_sum += row["irrelevant_rate"]

    n = len(eval_cases)
    exact_id_cases = [c for c in eval_cases if c.exact_id_required]
    exact_id_pass = sum(
        1
        for row, case in zip(rows, eval_cases)
        if case.exact_id_required and row.get("exact_document_hit_rate", 0) == 1.0
    )
    return {
        "provider": retriever.embedding.provider_name,
        "model": retriever.embedding.model_name,
        "dimensions": retriever.embedding.dimensions,
        "embedding_version": retriever.embedding.embedding_version,
        "retrieval_mode": retrieval_mode,
        "queries": n,
        "recall_at_1": round(metrics[1] / n, 4),
        "recall_at_3": round(metrics[3] / n, 4),
        "recall_at_5": round(metrics[5] / n, 4),
        "recall_at_10": round(metrics[10] / n, 4),
        "mrr": round(mrr_sum / n, 4),
        "exact_id_hit_rate": round(exact_flow_sum / n, 4),
        "exact_document_hit_rate": round(exact_doc_sum / n, 4),
        "exact_id_benchmark_pass_rate": round(exact_id_pass / len(exact_id_cases), 4) if exact_id_cases else 1.0,
        "irrelevant_rate": round(irrelevant_sum / n, 4),
        "cases": rows,
        "case_count": n,
        "k": k,
        # legacy field
        "recall_at_k": round(metrics[k if k in metrics else 5] / n, 4),
    }


def compare_retrieval_strategies(retriever: KnowledgeRetriever, *, k: int = 5) -> dict:
    modes: list[RetrievalMode] = ["lexical", "dense", "hybrid"]
    reports = {mode: evaluate_retriever(retriever, k=k, retrieval_mode=mode) for mode in modes}
    table = []
    for mode in modes:
        report = reports[mode]
        table.append(
            {
                "method": mode,
                "recall_at_1": report["recall_at_1"],
                "recall_at_5": report["recall_at_5"],
                "mrr": report["mrr"],
                "exact_id_hit_rate": report["exact_id_hit_rate"],
                "irrelevant_rate": report["irrelevant_rate"],
            }
        )
    return {"comparison": table, "reports": reports}


def compare_embedding_providers(
    graph,
    *,
    providers: list,
    k: int = 5,
) -> dict:
    from qa_orchestrator.embedding_config import EmbeddingConfig
    from qa_orchestrator.embedding_provider import create_embedding_provider
    from qa_orchestrator.knowledge_indexer import KnowledgeIndexer
    from qa_orchestrator.qdrant_config import QdrantConfig
    from qa_orchestrator.vector_store import InMemoryVectorStore

    rows = []
    for provider_cfg in providers:
        emb = create_embedding_provider(provider_cfg)
        store = InMemoryVectorStore(emb)
        config = QdrantConfig(enabled=False, dense_dimensions=emb.dimensions)
        indexer = KnowledgeIndexer(
            discovery_root=graph.discovery_root,
            automation_dir=graph.automation_dir,
            config=config,
            embedding_config=provider_cfg,
            store=store,
            embedding=emb,
        )
        indexer.index_all()
        retriever = KnowledgeRetriever(
            graph,
            config=config,
            store=store,
            embedding=emb,
            embedding_config=provider_cfg,
            indexer=indexer,
        )
        report = evaluate_retriever(retriever, k=k, retrieval_mode="hybrid")
        rows.append(
            {
                "provider": report["provider"],
                "model": report["model"],
                "recall_at_1": report["recall_at_1"],
                "recall_at_5": report["recall_at_5"],
                "mrr": report["mrr"],
                "exact_id_hit_rate": report["exact_id_hit_rate"],
            }
        )
    return {"embedding_comparison": rows}
