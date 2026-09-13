"""Approval workflow state transition tests (YAML persistence rules)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ARTIFACT = "test-cases.yaml"
VALID_STATUSES = {"PENDING_SME_APPROVAL", "APPROVED", "REJECTED"}


def read_status(raw: str) -> str | None:
    match = re.search(r"^status:\s*(PENDING_SME_APPROVAL|APPROVED|REJECTED)\s*$", raw, re.M)
    return match.group(1) if match else None


def write_status(raw: str, status: str) -> str:
    if re.search(r"^status:\s*(PENDING_SME_APPROVAL|APPROVED|REJECTED)\s*$", raw, re.M):
        return re.sub(
            r"^status:\s*(PENDING_SME_APPROVAL|APPROVED|REJECTED)\s*$",
            f"status: {status}",
            raw,
            count=1,
            flags=re.M,
        )
    return f"status: {status}\n{raw}"


def is_valid_transition(current: str, new: str) -> bool:
    if current == new:
        return False
    if current == "PENDING_SME_APPROVAL" and new in {"APPROVED", "REJECTED"}:
        return True
    if current == "REJECTED" and new == "PENDING_SME_APPROVAL":
        return True
    return False


def transition_file(path: Path, action: str, approver: str) -> dict[str, str]:
    if action not in {"approve", "reject"}:
        raise ValueError("invalid action")
    if not approver.strip():
        raise ValueError("approver required")
    if not path.exists():
        raise FileNotFoundError(str(path))
    raw = path.read_text(encoding="utf-8")
    current = read_status(raw)
    if not current:
        raise ValueError("missing status")
    new_status = "APPROVED" if action == "approve" else "REJECTED"
    if not is_valid_transition(current, new_status):
        raise ValueError(f"invalid transition {current} -> {new_status}")
    path.write_text(write_status(raw, new_status), encoding="utf-8")
    return {"status": new_status, "approver": approver.strip()}


def test_approval_pending_to_approved(tmp_path: Path):
    artifact = tmp_path / ARTIFACT
    artifact.write_text("status: PENDING_SME_APPROVAL\nflow_id: BF-LOGIN-001\n", encoding="utf-8")
    result = transition_file(artifact, "approve", "sme@test.com")
    assert result["status"] == "APPROVED"
    assert read_status(artifact.read_text(encoding="utf-8")) == "APPROVED"


def test_approval_pending_to_rejected(tmp_path: Path):
    artifact = tmp_path / ARTIFACT
    artifact.write_text("status: PENDING_SME_APPROVAL\n", encoding="utf-8")
    result = transition_file(artifact, "reject", "sme@test.com")
    assert result["status"] == "REJECTED"


def test_approval_rejects_invalid_transition(tmp_path: Path):
    artifact = tmp_path / ARTIFACT
    artifact.write_text("status: APPROVED\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid transition"):
        transition_file(artifact, "approve", "sme@test.com")


def test_approval_requires_approver(tmp_path: Path):
    artifact = tmp_path / ARTIFACT
    artifact.write_text("status: PENDING_SME_APPROVAL\n", encoding="utf-8")
    with pytest.raises(ValueError, match="approver"):
        transition_file(artifact, "approve", "  ")
