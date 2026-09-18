"""Lightweight deterministic query preprocessing for QA retrieval."""

from __future__ import annotations

import re

from qa_orchestrator.intent_classifier import _extract_sku

FLOW_ID_RE = re.compile(r"\b(BF-[A-Z0-9-]+(?:-[A-Z0-9]+)*)\b")
TEST_ID_RE = re.compile(r"\b(TC-[A-Z0-9-]+(?:-[A-Z0-9]+)*)\b")
STEP_ID_RE = re.compile(r"\b(step[:\s]+([a-z0-9_\-]+))\b", re.I)
PUNCT_RE = re.compile(r"[^\w\s\-:/]")


def preprocess_query(query: str) -> tuple[str, dict[str, object]]:
    original = query or ""
    normalized = " ".join(original.split()).strip()
    normalized = PUNCT_RE.sub(" ", normalized)
    normalized = " ".join(normalized.split())

    flow_ids = FLOW_ID_RE.findall(normalized)
    test_ids = TEST_ID_RE.findall(normalized)
    step_ids = [m.group(1) for m in STEP_ID_RE.finditer(normalized)]
    sku = _extract_sku(normalized)

    meta: dict[str, object] = {
        "original_query": original,
        "extracted_flow_ids": flow_ids,
        "extracted_test_ids": test_ids,
        "extracted_step_ids": step_ids,
        "extracted_sku": sku,
    }
    return normalized, meta
