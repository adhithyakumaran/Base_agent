"""P11.4 — canonical deterministic QA reporting."""

from qa_orchestrator.qa_report.builder import build_qa_report
from qa_orchestrator.qa_report.models import QAReport, REPORT_SCHEMA_VERSION

__all__ = ["QAReport", "REPORT_SCHEMA_VERSION", "build_qa_report"]
