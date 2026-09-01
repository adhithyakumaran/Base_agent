from __future__ import annotations

import uuid
from typing import Any

from base_agent.contracts.models import Observation
from base_agent.ground_truth.protocol import GroundTruthProvider, ValidationReport


class ObservationPipeline:
    """raw → normalize → validate schema → GT/rules → LLM only if necessary."""

    def __init__(self, gt: GroundTruthProvider | None = None) -> None:
        self.gt = gt

    def process(
        self,
        *,
        tool_name: str,
        plugin_id: str | None,
        raw: dict[str, Any],
        ok: bool,
        error_class: str | None = None,
        gt_subject: str | None = None,
        context: dict[str, Any] | None = None,
        allow_llm: bool = False,
    ) -> Observation:
        obs_id = f"obs_{uuid.uuid4().hex[:10]}"
        if not ok:
            return Observation(
                id=obs_id,
                source_tool=tool_name,
                source_plugin=plugin_id,
                payload={"error_class": error_class, "raw": raw},
                validation_outcome="fail" if error_class == "validation_failure" else "not_applicable",
                reason_code=error_class or "tool_error",
            )

        normalized = dict(raw)
        # Deterministic GT validation when subject provided
        if self.gt and gt_subject:
            report: ValidationReport = self.gt.validate(gt_subject, normalized, context or {})
            return Observation(
                id=obs_id,
                source_tool=tool_name,
                source_plugin=plugin_id,
                payload={"data": normalized, "validation": report.model_dump()},
                validation_outcome=report.outcome,
                used_llm=False,
                reason_code=report.reason_code,
            )

        # Built-in deterministic rules for APEX-ish payloads
        text = str(normalized.get("body_text") or normalized.get("text") or "")
        if any(tok in text for tok in ("ORA-", "Unexpected error", "APEX error")):
            return Observation(
                id=obs_id,
                source_tool=tool_name,
                source_plugin=plugin_id,
                payload={"data": normalized},
                validation_outcome="fail",
                reason_code="rule.apex.error_page",
            )

        # Sanity / crawl technical aggregate (no business GT)
        tech = normalized.get("technical_aggregate")
        if tech == "fail":
            return Observation(
                id=obs_id,
                source_tool=tool_name,
                source_plugin=plugin_id,
                payload={"data": normalized},
                validation_outcome="fail",
                reason_code="rule.apex.technical_fail",
            )
        if tech == "pass" and tool_name.endswith("sanity_probe"):
            # Technical pass is not business PASS — still insufficient for GT-backed claims
            return Observation(
                id=obs_id,
                source_tool=tool_name,
                source_plugin=plugin_id,
                payload={"data": normalized},
                validation_outcome="insufficient",
                reason_code="obs.technical_ok_no_business_gt",
            )

        # Crawl/discover with pages and no error → useful evidence, no GT
        if tool_name.endswith("discover") and normalized.get("pages") is not None:
            page_errors = []
            for p in normalized.get("pages") or []:
                if isinstance(p, dict):
                    page_errors.extend(p.get("errors") or [])
            if any("apex.error_page" in str(e) for e in page_errors):
                return Observation(
                    id=obs_id,
                    source_tool=tool_name,
                    source_plugin=plugin_id,
                    payload={"data": normalized},
                    validation_outcome="fail",
                    reason_code="rule.apex.error_page",
                )

        # No GT / no rule → do NOT invent PASS/FAIL
        if allow_llm:
            # Placeholder: intelligence plane may interpret later; still not a conclusion
            return Observation(
                id=obs_id,
                source_tool=tool_name,
                source_plugin=plugin_id,
                payload={"data": normalized, "needs_interpretation": True},
                validation_outcome="insufficient",
                used_llm=False,
                reason_code="obs.unclassified",
            )

        return Observation(
            id=obs_id,
            source_tool=tool_name,
            source_plugin=plugin_id,
            payload={"data": normalized},
            validation_outcome="insufficient",
            reason_code="obs.no_gt_no_rule",
        )