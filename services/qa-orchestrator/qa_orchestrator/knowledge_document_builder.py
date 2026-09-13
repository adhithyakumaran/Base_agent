"""Normalize authoritative QA sources into QaKnowledgeDocument records."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from qa_orchestrator.knowledge_sanitize import sanitize_for_index, sanitize_metadata
from qa_orchestrator.qa_knowledge_models import QaKnowledgeDocument

FLOW_ID_RE = re.compile(r"BF-[A-Z0-9-]+")
TEST_ID_RE = re.compile(r"TC-[A-Z0-9-]+")


def stable_document_id(document_type: str, *parts: str) -> str:
    slug = ":".join(p for p in parts if p)
    return f"{document_type.lower()}:{slug}"


def compute_source_hash(payload: dict[str, Any] | str) -> str:
    if isinstance(payload, str):
        raw = payload
    else:
        raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _polarity_from_test_type(test_type: str) -> str:
    t = test_type.lower()
    if t in {"negative", "edge"}:
        return "negative"
    if t == "parameterized":
        return "parameterized"
    return "positive"


class KnowledgeDocumentBuilder:
    """Build retrieval documents from YAML KB, automation artifacts, and healing store."""

    def __init__(
        self,
        *,
        discovery_root: Path,
        automation_dir: Path,
    ) -> None:
        self.discovery_root = Path(discovery_root)
        self.automation_dir = Path(automation_dir)
        self.flows_dir = self.discovery_root / "flows"
        self.candidates_dir = self.discovery_root / "candidates"

    def build_all(self) -> list[QaKnowledgeDocument]:
        docs: list[QaKnowledgeDocument] = []
        docs.extend(self.build_flow_documents())
        docs.extend(self.build_test_case_documents())
        docs.extend(self.build_business_rule_documents())
        docs.extend(self.build_step_documents())
        docs.extend(self.build_exploration_documents())
        docs.extend(self.build_healing_documents())
        return docs

    def _load_flow_index(self) -> dict[str, Any]:
        index_path = self.flows_dir / "index.yaml"
        if not index_path.exists():
            return {}
        return yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}

    def build_flow_documents(self) -> list[QaKnowledgeDocument]:
        index = self._load_flow_index()
        sme_ready = set(index.get("sme_ready") or [])
        docs: list[QaKnowledgeDocument] = []
        for entry in index.get("flows") or []:
            flow_id = str(entry.get("id") or "")
            file_name = entry.get("file")
            if not flow_id or not file_name:
                continue
            path = self.flows_dir / str(file_name)
            if not path.exists():
                continue
            doc_yaml = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            status = str(entry.get("status") or doc_yaml.get("status", {}).get("overall") or "DRAFT")
            purpose = sanitize_for_index(str(doc_yaml.get("purpose") or entry.get("name") or ""))
            preconditions = doc_yaml.get("preconditions") or []
            pages = doc_yaml.get("pages") or []
            business_flow_raw = doc_yaml.get("business_flow") or []
            if isinstance(business_flow_raw, dict):
                business_flow = list(business_flow_raw.values())
            elif isinstance(business_flow_raw, list):
                business_flow = business_flow_raw
            else:
                business_flow = [business_flow_raw]
            expected_raw = doc_yaml.get("expected_success") or []
            if isinstance(expected_raw, dict):
                expected = list(expected_raw.values())
            elif isinstance(expected_raw, list):
                expected = expected_raw
            else:
                expected = [expected_raw]
            tags = [str(t) for t in doc_yaml.get("tags") or []]
            polarity_notes = []
            if doc_yaml.get("observed_invalid_inputs"):
                polarity_notes.append("negative scenarios documented")
            if doc_yaml.get("test_data"):
                polarity_notes.append("parameterized test data available")
            text_parts = [
                flow_id,
                str(entry.get("name") or doc_yaml.get("flow_name") or ""),
                purpose,
                " ".join(str(p) for p in pages),
                " ".join(str(p) for p in preconditions),
                " ".join(str(x) for x in business_flow[:8]),
                " ".join(str(x) for x in expected[:6]),
                " ".join(polarity_notes),
            ]
            text = sanitize_for_index("\n".join(p for p in text_parts if p))
            payload = {"flow_id": flow_id, "status": status, "purpose": purpose, "pages": pages}
            docs.append(
                QaKnowledgeDocument(
                    document_id=stable_document_id("flow", flow_id),
                    document_type="FLOW",
                    flow_id=flow_id,
                    title=str(entry.get("name") or doc_yaml.get("flow_name") or flow_id),
                    text=text,
                    source="discovery-kb/flows",
                    status=status,
                    sme_ready=flow_id in sme_ready,
                    approval_state=self._flow_approval_state(flow_id),
                    polarity="mixed" if polarity_notes else "positive",
                    tags=tags,
                    metadata=sanitize_metadata(
                        {
                            "pages": pages[:12],
                            "entry_point": doc_yaml.get("entry_point"),
                            "parent": entry.get("parent"),
                            "superseded_by": entry.get("superseded_by"),
                        }
                    ),
                    source_path=str(path),
                    source_hash=compute_source_hash(payload),
                    indexed_at=_now_iso(),
                    version=1,
                )
            )
        return docs

    def _flow_approval_state(self, flow_id: str) -> str:
        design = self.automation_dir / "test-design" / "flows" / flow_id / "test-cases.yaml"
        if not design.exists():
            return "MISSING"
        data = yaml.safe_load(design.read_text(encoding="utf-8")) or {}
        return str(data.get("status") or "UNKNOWN")

    def build_test_case_documents(self) -> list[QaKnowledgeDocument]:
        docs: list[QaKnowledgeDocument] = []
        design_root = self.automation_dir / "test-design" / "flows"
        if not design_root.exists():
            return docs
        for flow_dir in sorted(design_root.iterdir()):
            if not flow_dir.is_dir():
                continue
            path = flow_dir / "test-cases.yaml"
            if not path.exists():
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            flow_id = str(data.get("flow_id") or flow_dir.name)
            approval = str(data.get("status") or "UNKNOWN")
            for tc in data.get("test_cases") or []:
                test_id = str(tc.get("id") or "")
                if not test_id:
                    continue
                test_type = str(tc.get("type") or "positive")
                title = sanitize_for_index(str(tc.get("title") or test_id))
                preconditions = tc.get("preconditions") or []
                steps_summary = sanitize_for_index(str(tc.get("steps_summary") or ""))
                expected = tc.get("expected_result") or tc.get("expected") or ""
                text = sanitize_for_index(
                    "\n".join(
                        [
                            test_id,
                            flow_id,
                            title,
                            steps_summary,
                            " ".join(str(p) for p in preconditions),
                            json.dumps(expected, default=str) if expected else "",
                        ]
                    )
                )
                payload = {"test_id": test_id, "flow_id": flow_id, "type": test_type, "title": title}
                docs.append(
                    QaKnowledgeDocument(
                        document_id=stable_document_id("test", test_id),
                        document_type="TEST_CASE",
                        flow_id=flow_id,
                        test_id=test_id,
                        title=title,
                        text=text,
                        source="automation/test-design",
                        status=test_type.upper(),
                        sme_ready=approval == "APPROVED",
                        approval_state=approval,
                        polarity=_polarity_from_test_type(test_type),
                        tags=[str(t) for t in tc.get("tags") or []],
                        metadata=sanitize_metadata({"linked_scenario": tc.get("linked_scenario")}),
                        source_path=str(path),
                        source_hash=compute_source_hash(payload),
                        indexed_at=_now_iso(),
                        version=1,
                    )
                )
        return docs

    def build_business_rule_documents(self) -> list[QaKnowledgeDocument]:
        docs: list[QaKnowledgeDocument] = []
        index = self._load_flow_index()
        for entry in index.get("flows") or []:
            flow_id = str(entry.get("id") or "")
            file_name = entry.get("file")
            if not flow_id or not file_name:
                continue
            path = self.flows_dir / str(file_name)
            if not path.exists():
                continue
            doc_yaml = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            rules_raw = doc_yaml.get("business_rules") or []
            if isinstance(rules_raw, dict):
                rules_iter = [
                    {"id": rule_id, **(rule if isinstance(rule, dict) else {"statement": str(rule)})}
                    for rule_id, rule in rules_raw.items()
                ]
            elif isinstance(rules_raw, list):
                rules_iter = rules_raw
            else:
                rules_iter = []
            for rule in rules_iter:
                if not isinstance(rule, dict):
                    continue
                rule_id = str(rule.get("id") or rule.get("rule_id") or "")
                if not rule_id:
                    continue
                statement = sanitize_for_index(
                    str(rule.get("statement") or rule.get("description") or rule.get("rule") or "")
                )
                if not statement:
                    continue
                text = sanitize_for_index(f"{flow_id} {rule_id} {statement}")
                payload = {"flow_id": flow_id, "rule_id": rule_id, "statement": statement}
                docs.append(
                    QaKnowledgeDocument(
                        document_id=stable_document_id("rule", flow_id, rule_id),
                        document_type="BUSINESS_RULE",
                        flow_id=flow_id,
                        title=f"{rule_id} — {flow_id}",
                        text=text,
                        source="discovery-kb/flows",
                        status=str(entry.get("status") or "DRAFT"),
                        sme_ready=flow_id in set(index.get("sme_ready") or []),
                        approval_state=self._flow_approval_state(flow_id),
                        polarity="positive",
                        tags=["business_rule"],
                        metadata=sanitize_metadata({"rule_id": rule_id}),
                        source_path=str(path),
                        source_hash=compute_source_hash(payload),
                        indexed_at=_now_iso(),
                        version=1,
                    )
                )
        return docs

    def build_step_documents(self) -> list[QaKnowledgeDocument]:
        docs: list[QaKnowledgeDocument] = []
        index = self._load_flow_index()
        for entry in index.get("flows") or []:
            flow_id = str(entry.get("id") or "")
            file_name = entry.get("file")
            if not flow_id or not file_name:
                continue
            path = self.flows_dir / str(file_name)
            if not path.exists():
                continue
            doc_yaml = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            components = doc_yaml.get("components") or {}
            if not isinstance(components, dict):
                continue
            for comp_name, comp in components.items():
                if not isinstance(comp, dict):
                    continue
                locator = comp.get("locator") or comp.get("locators") or {}
                primary = ""
                if isinstance(locator, dict):
                    prim = locator.get("primary") or {}
                    if isinstance(prim, dict):
                        primary = str(prim.get("value") or "")
                action = str(comp.get("action") or comp.get("type") or comp_name)
                text = sanitize_for_index(
                    f"{flow_id} step {comp_name} action {action} locator {primary}"
                )
                step_id = str(comp_name)
                payload = {"flow_id": flow_id, "step_id": step_id, "action": action, "locator": primary}
                docs.append(
                    QaKnowledgeDocument(
                        document_id=stable_document_id("step", flow_id, step_id),
                        document_type="STEP",
                        flow_id=flow_id,
                        step_id=step_id,
                        title=f"{flow_id} — {comp_name}",
                        text=text,
                        source="discovery-kb/flows",
                        status=str(entry.get("status") or "DRAFT"),
                        sme_ready=flow_id in set(index.get("sme_ready") or []),
                        approval_state=self._flow_approval_state(flow_id),
                        polarity="positive",
                        tags=["step", "locator"],
                        metadata=sanitize_metadata({"component": comp_name, "locator": primary}),
                        source_path=str(path),
                        source_hash=compute_source_hash(payload),
                        indexed_at=_now_iso(),
                        version=1,
                    )
                )
        return docs

    def build_exploration_documents(self) -> list[QaKnowledgeDocument]:
        docs: list[QaKnowledgeDocument] = []
        if not self.candidates_dir.exists():
            return docs
        for path in sorted(self.candidates_dir.glob("candidate-explore-*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            candidate_id = str(raw.get("candidate_id") or path.stem.replace("candidate-", ""))
            if not candidate_id:
                continue
            flow_id = str(raw.get("candidate_flow") or "")
            observed_page = sanitize_for_index(str(raw.get("observed_page") or ""))
            behaviors = [sanitize_for_index(str(b)) for b in raw.get("possible_business_behavior") or []]
            element_names = [
                sanitize_for_index(str(el.get("name") or el.get("text") or ""))
                for el in raw.get("elements") or []
                if isinstance(el, dict)
            ]
            text = sanitize_for_index(
                "\n".join([candidate_id, flow_id, observed_page, " ".join(behaviors), " ".join(element_names)])
            )
            payload = {"candidate_id": candidate_id, "flow_id": flow_id, "page": observed_page}
            docs.append(
                QaKnowledgeDocument(
                    document_id=stable_document_id("exploration", candidate_id),
                    document_type="EXPLORATION",
                    flow_id=flow_id,
                    title=f"Exploration {candidate_id}",
                    text=text,
                    source="discovery-kb/candidates",
                    status=str(raw.get("status") or "DRAFT"),
                    sme_ready=False,
                    approval_state="DRAFT",
                    polarity="positive",
                    tags=["exploration"],
                    metadata=sanitize_metadata({"observed_page": observed_page}),
                    source_path=str(path),
                    source_hash=compute_source_hash(payload),
                    indexed_at=_now_iso(),
                    version=1,
                )
            )
        return docs

    def build_healing_documents(self) -> list[QaKnowledgeDocument]:
        docs: list[QaKnowledgeDocument] = []
        approved_dir = self.automation_dir / "healing" / "approved"
        if not approved_dir.exists():
            return docs
        overlay_path = approved_dir / "locator-overlays.json"
        if overlay_path.exists():
            try:
                overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                overlay = {}
            for entry in overlay.get("entries") or []:
                if not isinstance(entry, dict):
                    continue
                if entry.get("status") != "APPROVED" or entry.get("revoked"):
                    continue
                docs.extend(self._healing_entry_to_doc(entry, str(overlay_path)))
        for path in sorted(approved_dir.glob("*.json")):
            if path.name == "locator-overlays.json":
                continue
            try:
                proposal = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if proposal.get("status") != "APPROVED":
                continue
            docs.extend(self._healing_entry_to_doc(proposal, str(path)))
        return docs

    def _healing_entry_to_doc(self, entry: dict[str, Any], source_path: str) -> list[QaKnowledgeDocument]:
        healing_id = str(entry.get("healing_id") or "")
        if not healing_id:
            return []
        flow_id = str(entry.get("flow_id") or "")
        test_id = str(entry.get("test_id") or "")
        label = sanitize_for_index(str(entry.get("locator_label") or ""))
        old_loc = sanitize_for_index(str(entry.get("old_locator") or ""))
        new_loc = sanitize_for_index(str(entry.get("new_locator") or ""))
        selectors = entry.get("selectors") or []
        reason = sanitize_for_index(str(entry.get("reason") or "approved locator replacement"))
        text = sanitize_for_index(
            "\n".join(
                [
                    healing_id,
                    flow_id,
                    test_id,
                    label,
                    old_loc,
                    new_loc,
                    " ".join(str(s) for s in selectors),
                    reason,
                ]
            )
        )
        payload = {
            "healing_id": healing_id,
            "flow_id": flow_id,
            "label": label,
            "new_locator": new_loc,
            "selectors": selectors,
        }
        return [
            QaKnowledgeDocument(
                document_id=stable_document_id("healing", healing_id),
                document_type="HEALING",
                flow_id=flow_id,
                test_id=test_id,
                title=f"Healing {label} — {flow_id}",
                text=text,
                source="automation/healing/approved",
                status="APPROVED",
                sme_ready=True,
                approval_state="APPROVED",
                polarity="positive",
                tags=["healing", "locator"],
                metadata=sanitize_metadata(
                    {
                        "locator_label": label,
                        "old_locator": old_loc,
                        "new_locator": new_loc,
                        "selectors": selectors,
                    }
                ),
                source_path=source_path,
                source_hash=compute_source_hash(payload),
                indexed_at=_now_iso(),
                version=entry.get("entry_version", 1),
            )
        ]
