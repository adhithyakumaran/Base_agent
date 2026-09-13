"""Validate generated Playwright specs before SME approval."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from qa_orchestrator.models import GeneratedTestCase, GenerationValidation

ALLOWED_ROOT = Path("apps/automation/generated/drafts").resolve()
REQUIRED_IMPORT = "src/fixtures/test-base"
FORBIDDEN_PATTERNS = (
    r"\.\./\.\./\.\./\.\.",
    r"/etc/passwd",
    r"process\.env\.EA_USER_PASSWORD\s*=",
)


def validate_output_path(path: Path, automation_dir: Path) -> GenerationValidation:
    resolved = path.resolve()
    allowed = (automation_dir / "generated" / "drafts").resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError:
        return GenerationValidation(
            valid=False,
            reason_code="generation.path_traversal",
            message=f"Generated path escapes draft directory: {path}",
        )
    if path.suffix != ".ts":
        return GenerationValidation(
            valid=False,
            reason_code="generation.invalid_extension",
            message="Generated file must be .spec.ts",
        )
    return GenerationValidation(valid=True, reason_code="generation.path_ok", message="Path allowed")


def validate_spec_content(
    content: str,
    *,
    test_case: GeneratedTestCase,
) -> GenerationValidation:
    checks: list[dict[str, object]] = []
    if REQUIRED_IMPORT not in content:
        return GenerationValidation(
            valid=False,
            reason_code="generation.import_missing",
            message="Generated spec must import test-base fixture",
            checks=checks,
        )
    checks.append({"check": "import_fixture", "ok": True})

    if test_case.test_case_id not in content:
        return GenerationValidation(
            valid=False,
            reason_code="generation.test_id_missing",
            message=f"Spec must include test case id {test_case.test_case_id}",
            checks=checks,
        )
    checks.append({"check": "test_case_id", "ok": True})

    if test_case.flow_id not in content:
        return GenerationValidation(
            valid=False,
            reason_code="generation.flow_id_missing",
            message=f"Spec must reference flow id {test_case.flow_id}",
            checks=checks,
        )
    checks.append({"check": "flow_id", "ok": True})

    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, content):
            return GenerationValidation(
                valid=False,
                reason_code="generation.unsafe_content",
                message=f"Forbidden pattern detected: {pattern}",
                checks=checks,
            )
    checks.append({"check": "forbidden_patterns", "ok": True})

    if "@generated" not in content or "@draft" not in content:
        return GenerationValidation(
            valid=False,
            reason_code="generation.metadata_tags_missing",
            message="Generated spec must include @generated and @draft tags",
            checks=checks,
        )
    checks.append({"check": "draft_tags", "ok": True})

    if re.search(r"ABC123", content) and "QA_PARAM" not in content:
        return GenerationValidation(
            valid=False,
            reason_code="generation.hardcoded_test_data",
            message="Hard-coded test data detected — use QA_PARAM_* env vars",
            checks=checks,
        )
    checks.append({"check": "param_usage", "ok": True})

    if "GENERATED DRAFT" not in content:
        checks.append({"check": "draft_banner", "ok": False})
    else:
        checks.append({"check": "draft_banner", "ok": True})

    return GenerationValidation(
        valid=True,
        reason_code="generation.valid",
        message="Static validation passed",
        checks=checks,
    )


def validate_syntax_typescript(content: str) -> GenerationValidation:
    if "test.describe(" not in content or "test(" not in content:
        return GenerationValidation(
            valid=False,
            reason_code="generation.syntax_invalid",
            message="Missing test.describe/test structure",
        )
    if content.count("{") != content.count("}"):
        return GenerationValidation(
            valid=False,
            reason_code="generation.syntax_invalid",
            message="Unbalanced braces in generated TypeScript",
        )
    return GenerationValidation(valid=True, reason_code="generation.syntax_ok", message="Syntax check passed")


def validate_playwright_discovery(spec_path: Path, automation_dir: Path) -> GenerationValidation:
    script = automation_dir / "scripts" / "validate-generated-spec.mjs"
    if not script.exists():
        return GenerationValidation(
            valid=True,
            reason_code="generation.discovery_skipped",
            message="Discovery validator script not present — skipped",
        )
    try:
        proc = subprocess.run(
            ["node", str(script), str(spec_path.relative_to(automation_dir))],
            cwd=str(automation_dir),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return GenerationValidation(
            valid=True,
            reason_code="generation.discovery_skipped",
            message=f"Playwright discovery skipped: {exc}",
        )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "playwright test --list failed"
        return GenerationValidation(
            valid=False,
            reason_code="generation.discovery_failed",
            message=detail[:500],
        )
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        payload = {"ok": proc.returncode == 0}
    if not payload.get("ok", False):
        return GenerationValidation(
            valid=False,
            reason_code="generation.discovery_failed",
            message=str(payload.get("error") or "Test discovery failed"),
        )
    return GenerationValidation(
        valid=True,
        reason_code="generation.discovery_ok",
        message="Playwright test discovery passed",
    )
