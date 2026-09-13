"""Deterministic retrieval evaluation dataset and metrics — P4 quality gate."""

from __future__ import annotations

from dataclasses import dataclass

from qa_orchestrator.knowledge_retriever import KnowledgeRetriever
from qa_orchestrator.qa_knowledge_models import RetrievalResult


@dataclass(frozen=True)
class RetrievalEvalCase:
    query: str
    expected_document_ids: list[str]
    expected_flow_ids: list[str] = None  # type: ignore[assignment]
    exact_id_required: bool = False

    def __post_init__(self) -> None:
        if self.expected_flow_ids is None:
            object.__setattr__(self, "expected_flow_ids", [])


EVAL_CASES: list[RetrievalEvalCase] = [
    RetrievalEvalCase("Check login", expected_document_ids=["flow:BF-LOGIN-001"], expected_flow_ids=["BF-LOGIN-001"]),
    RetrievalEvalCase(
        "Test invalid login",
        expected_document_ids=["flow:BF-LOGIN-001"],
        expected_flow_ids=["BF-LOGIN-001"],
    ),
    RetrievalEvalCase(
        "Search SKU ABC123",
        expected_document_ids=["flow:BF-PRODUCT-003"],
        expected_flow_ids=["BF-PRODUCT-003"],
    ),
    RetrievalEvalCase(
        "product search",
        expected_document_ids=["flow:BF-PRODUCT-003"],
        expected_flow_ids=["BF-PRODUCT-003"],
    ),
    RetrievalEvalCase(
        "search button",
        expected_document_ids=[],
        expected_flow_ids=["BF-PRODUCT-003"],
    ),
    RetrievalEvalCase(
        "test a new product filter",
        expected_document_ids=[],
        expected_flow_ids=[],
    ),
    RetrievalEvalCase(
        "checkout",
        expected_document_ids=[],
        expected_flow_ids=[],
    ),
    RetrievalEvalCase(
        "BF-PRODUCT-003",
        expected_document_ids=["flow:BF-PRODUCT-003"],
        expected_flow_ids=["BF-PRODUCT-003"],
        exact_id_required=True,
    ),
    RetrievalEvalCase(
        "TC-BF-PRODUCT-003-P01",
        expected_document_ids=["test:TC-BF-PRODUCT-003-P01"],
        expected_flow_ids=["BF-PRODUCT-003"],
        exact_id_required=True,
    ),
    RetrievalEvalCase(
        "generate quarterly tax report for martian colony",
        expected_document_ids=[],
        expected_flow_ids=[],
    ),
]


def recall_at_k(result: RetrievalResult, expected_ids: list[str], k: int = 5) -> float:
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


def evaluate_retriever(retriever: KnowledgeRetriever, *, k: int = 5) -> dict:
    retriever.ensure_index()
    rows: list[dict] = []
    recall_sum = 0.0
    mrr_sum = 0.0
    exact_sum = 0.0
    for case in EVAL_CASES:
        result = retriever.retrieve(case.query, sme_ready_only=False, approval_only=False, top_k=k)
        rec = recall_at_k(result, case.expected_document_ids, k=k)
        rr = mrr(result, case.expected_document_ids)
        exact = exact_id_hit_rate(result, case.expected_flow_ids)
        recall_sum += rec
        mrr_sum += rr
        exact_sum += exact
        rows.append(
            {
                "query": case.query,
                "recall_at_k": round(rec, 4),
                "mrr": round(rr, 4),
                "exact_id_hit_rate": round(exact, 4),
                "method": result.diagnostics.method,
                "selected": result.diagnostics.selected,
            }
        )
    n = len(EVAL_CASES)
    return {
        "cases": rows,
        "recall_at_k": round(recall_sum / n, 4),
        "mrr": round(mrr_sum / n, 4),
        "exact_id_hit_rate": round(exact_sum / n, 4),
        "case_count": n,
        "k": k,
    }
