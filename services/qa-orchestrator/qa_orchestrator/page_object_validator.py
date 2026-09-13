"""Validate page object references in generated actions."""

from __future__ import annotations

import re
from pathlib import Path

from qa_orchestrator.models import GeneratedAction, GenerationValidation
from qa_orchestrator.page_object_registry import (
    FLOW_PAGE_OBJECTS,
    page_object_file_exists,
    resolve_page_object,
)


def validate_page_object_actions(
    actions: list[GeneratedAction],
    automation_dir: Path,
) -> GenerationValidation:
    checks: list[dict[str, object]] = []
    for action in actions:
        if action.type != "page_object" or not action.page_object or not action.page_object_method:
            continue
        binding = _resolve_binding(action.page_object, action.page_object_method)
        if binding is None:
            return GenerationValidation(
                valid=False,
                reason_code="generation.page_object_missing",
                message=f"Page object {action.page_object} is not registered",
                checks=checks,
            )
        if not page_object_file_exists(automation_dir, binding):
            return GenerationValidation(
                valid=False,
                reason_code="generation.page_object_file_missing",
                message=f"Page object file missing for {action.page_object}",
                checks=checks,
            )
        if action.page_object_method not in binding.methods:
            return GenerationValidation(
                valid=False,
                reason_code="generation.page_object_method_missing",
                message=f"Method {action.page_object_method} not defined on {action.page_object}",
                checks=checks,
            )
        if not _method_signature_compatible(
            automation_dir,
            binding,
            action.page_object_method,
            action.value_source,
        ):
            return GenerationValidation(
                valid=False,
                reason_code="generation.page_object_signature_invalid",
                message=f"Method {action.page_object_method} signature incompatible with generated usage",
                checks=checks,
            )
        checks.append(
            {
                "page_object": action.page_object,
                "method": action.page_object_method,
                "ok": True,
            }
        )
    return GenerationValidation(
        valid=True,
        reason_code="generation.page_object_ok",
        message="Page object references validated",
        checks=checks,
    )


def _resolve_binding(class_name: str, method: str | None = None):
    matches = [binding for binding in FLOW_PAGE_OBJECTS.values() if binding.class_name == class_name]
    if not matches:
        return None
    if method:
        for binding in matches:
            if method in binding.methods:
                return binding
    return matches[0]


def _method_signature_compatible(
    automation_dir: Path,
    binding,
    method: str,
    value_source: str | None,
) -> bool:
    rel = binding.import_path.removeprefix("../../")
    if not rel.endswith(".ts"):
        rel = rel.replace(".page", ".page.ts")
    path = automation_dir / rel
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    pattern = rf"async\s+{re.escape(method)}\s*\(([^)]*)\)"
    match = re.search(pattern, content)
    if not match:
        return False
    params = match.group(1).strip()
    if method == "searchItemCode":
        return True  # optional param — QA_PARAM_SKU compatible
    if params and value_source and "?" not in params and params != "itemCode?: string":
        return False
    return True
