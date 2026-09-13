"""P4 — semantic QA knowledge retrieval tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from qa_orchestrator.embedding_provider import DeterministicEmbeddingProvider
from qa_orchestrator.knowledge_document_builder import (
    KnowledgeDocumentBuilder,
    compute_source_hash,
    stable_document_id,
)
from qa_orchestrator.knowledge_indexer import KnowledgeIndexer
from qa_orchestrator.knowledge_retriever import KnowledgeRetriever, extract_exact_identifiers
from qa_orchestrator.models import IntentClassification
from qa_orchestrator.qa_planner import QaPlanner
from qa_orchestrator.qdrant_config import QdrantConfig
from qa_orchestrator.retrieval_eval import evaluate_retriever
from qa_orchestrator.vector_store import (
    InMemoryVectorStore,
    build_stored_point,
    payload_to_document,
)

DISCOVERY_ROOT = "data/discovery-kb"


@pytest.fixture(autouse=True)
def disable_qdrant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QA_QDRANT_ENABLED", "false")


def _graph():
    from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph

    return FlowKnowledgeGraph(discovery_root=DISCOVERY_ROOT)


def _retriever(*, enabled: bool = False, store: InMemoryVectorStore | None = None) -> KnowledgeRetriever:
    graph = _graph()
    config = QdrantConfig(enabled=enabled, dense_dimensions=64, top_k=8)
    embedding = DeterministicEmbeddingProvider(64)
    store = store or InMemoryVectorStore(embedding)
    indexer = KnowledgeIndexer(
        discovery_root=DISCOVERY_ROOT,
        automation_dir="apps/automation",
        config=config,
        store=store,
        embedding=embedding,
    )
    indexer.index_all()
    return KnowledgeRetriever(graph, config=config, store=store, embedding=embedding, indexer=indexer)


def _write_min_kb(root: Path, automation: Path) -> None:
    flows = root / "flows"
    flows.mkdir(parents=True)
    (flows / "index.yaml").write_text(
        yaml.safe_dump(
            {
                "sme_ready": ["BF-LOGIN-001"],
                "flows": [
                    {"id": "BF-LOGIN-001", "file": "BF-LOGIN-001.yaml", "name": "Login", "status": "READY"},
                    {"id": "BF-PRODUCT-003", "file": "BF-PRODUCT-003.yaml", "name": "Search Product", "status": "READY"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (flows / "BF-LOGIN-001.yaml").write_text(
        yaml.safe_dump(
            {
                "flow_id": "BF-LOGIN-001",
                "flow_name": "Login",
                "purpose": "Authenticate user",
                "business_rules": [{"id": "BR-LOGIN-01", "statement": "Invalid credentials must be rejected"}],
                "components": {"submit": {"type": "button", "locator": {"primary": {"value": "#login-btn"}}}},
            }
        ),
        encoding="utf-8",
    )
    (flows / "BF-PRODUCT-003.yaml").write_text(
        yaml.safe_dump(
            {
                "flow_id": "BF-PRODUCT-003",
                "flow_name": "Search Product",
                "purpose": "Search SKU and display stock",
                "components": {"search": {"type": "button", "locator": {"primary": {"value": "#btn_search"}}}},
            }
        ),
        encoding="utf-8",
    )
    for flow_id, status in [("BF-LOGIN-001", "APPROVED"), ("BF-PRODUCT-003", "PENDING_SME_APPROVAL")]:
        design = automation / "test-design" / "flows" / flow_id
        design.mkdir(parents=True, exist_ok=True)
        (design / "test-cases.yaml").write_text(
            yaml.safe_dump(
                {
                    "flow_id": flow_id,
                    "status": status,
                    "test_cases": [{"id": f"TC-{flow_id}-P01", "type": "positive", "title": flow_id}],
                }
            ),
            encoding="utf-8",
        )


def test_document_normalization(tmp_path: Path):
    auto = tmp_path / "automation"
    _write_min_kb(tmp_path / "kb", auto)
    builder = KnowledgeDocumentBuilder(discovery_root=tmp_path / "kb", automation_dir=auto)
    docs = builder.build_all()
    flow_docs = [d for d in docs if d.document_type == "FLOW"]
    assert flow_docs
    assert flow_docs[0].text


def test_stable_document_ids():
    assert stable_document_id("flow", "BF-LOGIN-001") == "flow:BF-LOGIN-001"
    assert stable_document_id("test", "TC-BF-LOGIN-001-P01") == "test:TC-BF-LOGIN-001-P01"
    assert stable_document_id("rule", "BF-LOGIN-001", "BR-LOGIN-01") == "rule:BF-LOGIN-001:BR-LOGIN-01"


def test_source_hashing():
    h1 = compute_source_hash({"a": 1})
    h2 = compute_source_hash({"a": 1})
    h3 = compute_source_hash({"a": 2})
    assert h1 == h2
    assert h1 != h3


def test_idempotent_indexing(tmp_path: Path):
    auto = tmp_path / "automation"
    _write_min_kb(tmp_path / "kb", auto)
    store = InMemoryVectorStore(DeterministicEmbeddingProvider(64))
    indexer = KnowledgeIndexer(discovery_root=tmp_path / "kb", automation_dir=auto, store=store)
    first = indexer.index_all()
    second = indexer.index_all()
    assert first.created > 0
    assert second.unchanged >= first.created
    assert second.created == 0


def test_stale_document_detection(tmp_path: Path):
    auto = tmp_path / "automation"
    _write_min_kb(tmp_path / "kb", auto)
    store = InMemoryVectorStore(DeterministicEmbeddingProvider(64))
    indexer = KnowledgeIndexer(discovery_root=tmp_path / "kb", automation_dir=auto, store=store)
    indexer.index_all()
    assert "flow:BF-PRODUCT-003" in store.list_document_ids()
    index_path = tmp_path / "kb" / "flows" / "index.yaml"
    data = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    data["flows"] = [f for f in data["flows"] if f["id"] != "BF-PRODUCT-003"]
    index_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    stats = indexer.index_all()
    assert stats.deleted >= 1
    assert "flow:BF-PRODUCT-003" not in store.list_document_ids()


def test_payload_metadata():
    from qa_orchestrator.qa_knowledge_models import QaKnowledgeDocument

    doc = QaKnowledgeDocument(
        document_id="flow:BF-LOGIN-001",
        document_type="FLOW",
        flow_id="BF-LOGIN-001",
        title="Login",
        text="login flow",
        source="test",
        status="READY",
        sme_ready=True,
        approval_state="APPROVED",
        polarity="positive",
        source_hash="abc",
    )
    point = build_stored_point(doc, DeterministicEmbeddingProvider(64))
    assert point.payload["flow_id"] == "BF-LOGIN-001"
    assert point.payload["document_type"] == "FLOW"


def test_exact_identifier_retrieval():
    retriever = _retriever()
    result = retriever.retrieve("BF-PRODUCT-003", sme_ready_only=False, approval_only=False)
    assert "BF-PRODUCT-003" in result.flow_ids
    assert "BF-PRODUCT-003" in result.diagnostics.exact_id_hits


def test_semantic_retrieval_dense():
    retriever = _retriever()
    result = retriever.retrieve("check login", sme_ready_only=False, approval_only=False)
    assert "BF-LOGIN-001" in result.flow_ids


def test_hybrid_retrieval():
    embedding = DeterministicEmbeddingProvider(64)
    store = InMemoryVectorStore(embedding)
    retriever = _retriever(store=store)
    result = retriever.retrieve("product search SKU", sme_ready_only=False, approval_only=False)
    assert result.items
    assert result.diagnostics.retrieval_used is True


def test_metadata_filters(tmp_path: Path):
    auto = tmp_path / "automation"
    _write_min_kb(tmp_path / "kb", auto)
    store = InMemoryVectorStore(DeterministicEmbeddingProvider(64))
    indexer = KnowledgeIndexer(discovery_root=tmp_path / "kb", automation_dir=auto, store=store)
    indexer.index_all()
    from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph

    graph = FlowKnowledgeGraph(discovery_root=tmp_path / "kb", automation_dir=auto)
    retriever = KnowledgeRetriever(graph, store=store, config=QdrantConfig(enabled=False))
    result = retriever.retrieve("login", sme_ready_only=True, approval_only=True, top_k=5)
    assert all(item.document.sme_ready for item in result.items)


def test_qdrant_disabled_fallback():
    graph = _graph()
    config = QdrantConfig(enabled=False)
    retriever = KnowledgeRetriever(graph, config=config)
    result = retriever.retrieve("Search SKU ABC123", sme_ready_only=False, approval_only=False)
    assert result.diagnostics.method == "LEXICAL_FALLBACK"
    assert "BF-PRODUCT-003" in result.flow_ids


def test_qdrant_unavailable_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QA_QDRANT_ENABLED", "true")
    monkeypatch.setenv("QA_QDRANT_URL", "http://127.0.0.1:1")
    graph = _graph()
    config = QdrantConfig.from_env()
    retriever = KnowledgeRetriever(graph, config=config)
    result = retriever.retrieve("check login", sme_ready_only=False, approval_only=False)
    assert result.diagnostics.method == "LEXICAL_FALLBACK"
    assert result.diagnostics.fallback_reason
    assert "BF-LOGIN-001" in result.flow_ids


def test_pending_approval_excluded_from_approval_filter(tmp_path: Path):
    auto = tmp_path / "automation"
    _write_min_kb(tmp_path / "kb", auto)
    store = InMemoryVectorStore(DeterministicEmbeddingProvider(64))
    indexer = KnowledgeIndexer(discovery_root=tmp_path / "kb", automation_dir=auto, store=store)
    indexer.index_all()
    from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph

    graph = FlowKnowledgeGraph(discovery_root=tmp_path / "kb", automation_dir=auto)
    retriever = KnowledgeRetriever(graph, store=store, config=QdrantConfig(enabled=False))
    result = retriever.retrieve("Search Product", approval_only=True, sme_ready_only=False, top_k=10)
    for item in result.items:
        if item.document.flow_id == "BF-PRODUCT-003":
            assert item.document.approval_state == "APPROVED"


def test_rejected_approval_excluded(tmp_path: Path):
    auto = tmp_path / "automation"
    _write_min_kb(tmp_path / "kb", auto)
    rejected = auto / "test-design" / "flows" / "BF-PRODUCT-003" / "test-cases.yaml"
    rejected.write_text(
        yaml.safe_dump({"flow_id": "BF-PRODUCT-003", "status": "REJECTED", "test_cases": []}),
        encoding="utf-8",
    )
    store = InMemoryVectorStore(DeterministicEmbeddingProvider(64))
    indexer = KnowledgeIndexer(discovery_root=tmp_path / "kb", automation_dir=auto, store=store)
    indexer.index_all()
    from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph

    graph = FlowKnowledgeGraph(discovery_root=tmp_path / "kb", automation_dir=auto)
    retriever = KnowledgeRetriever(graph, store=store, config=QdrantConfig(enabled=False))
    result = retriever.retrieve("Search Product", approval_only=True, sme_ready_only=False)
    assert "BF-PRODUCT-003" not in result.flow_ids


def test_non_sme_ready_excluded_when_requested(tmp_path: Path):
    auto = tmp_path / "automation"
    _write_min_kb(tmp_path / "kb", auto)
    store = InMemoryVectorStore(DeterministicEmbeddingProvider(64))
    indexer = KnowledgeIndexer(discovery_root=tmp_path / "kb", automation_dir=auto, store=store)
    indexer.index_all()
    from qa_orchestrator.knowledge_graph import FlowKnowledgeGraph

    graph = FlowKnowledgeGraph(discovery_root=tmp_path / "kb", automation_dir=auto)
    retriever = KnowledgeRetriever(graph, store=store, config=QdrantConfig(enabled=False))
    result = retriever.retrieve("Search Product", sme_ready_only=True, approval_only=False)
    assert "BF-PRODUCT-003" not in result.flow_ids


def test_retrieval_cannot_bypass_execution_gate():
    graph = _graph()
    retriever = _retriever()
    intent = IntentClassification(goal="check login", flow_ids=[])
    planner = QaPlanner(graph, retriever=retriever)
    planning = planner.plan(intent)
    assert planning.execution_allowed is False
    if planning.selected_flows:
        assert all(g.executable for g in planning.execution_gates if g.flow_id in planning.selected_flows)


def test_parameter_traceability_remains_intact():
    from qa_orchestrator.intent_classifier import IntentClassifier
    from qa_orchestrator.llm_client import PlannerLlmClient

    graph = _graph()
    retriever = _retriever()
    intent = IntentClassifier(graph, PlannerLlmClient(enabled=False)).classify("Search SKU ABC123")
    planner = QaPlanner(graph, retriever=retriever)
    planning = planner.plan(intent)
    assert planning.validated_parameters.get("sku") == "ABC123"
    assert "BF-PRODUCT-003" in planning.candidate_flows


def test_diagnostics_reporting():
    retriever = _retriever()
    result = retriever.retrieve("BF-LOGIN-001", sme_ready_only=False, approval_only=False)
    diag = result.diagnostics
    assert diag.retrieval_used is True
    assert diag.query == "BF-LOGIN-001"
    assert isinstance(diag.candidates, list)


def test_corrupted_payload_handling():
    bad = {"document_id": "", "document_type": "FLOW"}
    assert payload_to_document(bad) is None
    good = payload_to_document(
        {
            "document_id": "flow:BF-LOGIN-001",
            "document_type": "FLOW",
            "flow_id": "BF-LOGIN-001",
            "title": "Login",
            "text": "login",
            "source": "test",
            "status": "READY",
            "sme_ready": True,
            "approval_state": "APPROVED",
            "polarity": "positive",
            "tags": [],
            "metadata": {},
            "source_path": "",
            "source_hash": "x",
            "indexed_at": "",
            "version": 1,
        }
    )
    assert good is not None


def test_deterministic_evaluation_metrics():
    retriever = _retriever()
    report = evaluate_retriever(retriever, k=5)
    assert report["case_count"] == 10
    assert report["recall_at_k"] >= 0.0
    assert "mrr" in report
    assert "exact_id_hit_rate" in report


def test_extract_exact_identifiers():
    ids = extract_exact_identifiers("Run TC-BF-PRODUCT-003-P01 on BF-PRODUCT-003")
    assert "TC-BF-PRODUCT-003-P01" in ids
    assert "BF-PRODUCT-003" in ids


def test_healing_pending_not_indexed(tmp_path: Path):
    auto = tmp_path / "automation"
    _write_min_kb(tmp_path / "kb", auto)
    proposals = auto / "healing" / "proposals"
    proposals.mkdir(parents=True)
    (proposals / "heal-pending.json").write_text(
        json.dumps(
            {
                "healing_id": "heal-pending",
                "flow_id": "BF-LOGIN-001",
                "status": "PENDING_SME_APPROVAL",
                "locator_label": "submit",
                "new_locator": "page.locator('#login-btn')",
            }
        ),
        encoding="utf-8",
    )
    builder = KnowledgeDocumentBuilder(discovery_root=tmp_path / "kb", automation_dir=auto)
    healing_docs = builder.build_healing_documents()
    assert all(d.document_id != "healing:heal-pending" for d in healing_docs)
