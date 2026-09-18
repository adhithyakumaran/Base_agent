"""P10.2 runtime reliability and concurrency tests."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from qa_orchestrator.agent_state_store import ResumableAgentSnapshot, load_snapshot, mutate_snapshot, save_snapshot
from qa_orchestrator.agent_models import AgentRunState
from qa_orchestrator.approval_log import append_approval_record
from qa_orchestrator.fs_atomic import atomic_write_json
from qa_orchestrator.healing_overlay import apply_approved_proposal, load_overlay_store
from qa_orchestrator.live_browser_close import mark_session_closed, process_close_signal
from qa_orchestrator.models import HealingProposal


def _snapshot(run_id: str, *, token: str | None = None) -> ResumableAgentSnapshot:
    state = AgentRunState(
        run_id=run_id,
        request="demo",
        run_type="adhoc",
        status="WAITING_FOR_APPROVAL",
    )
    snap = ResumableAgentSnapshot(run_id=run_id, state=state)
    if token:
        snap.last_applied_resume_token = token
    return snap


def test_run_state_concurrent_mutations_preserve_counter(tmp_path: Path):
    base = tmp_path / "agent"
    run_id = "run-concurrent"
    save_snapshot(_snapshot(run_id), base_dir=base)
    errors: list[str] = []

    def worker() -> None:
        try:
            def bump(snap: ResumableAgentSnapshot) -> None:
                snap.completed_steps.append("step")

            mutate_snapshot(run_id, bump, base_dir=base)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: worker(), range(20)))
    assert not errors
    loaded = load_snapshot(run_id, base_dir=base)
    assert len(loaded.completed_steps) == 20


def test_approval_log_concurrent_appends(tmp_path: Path):
    log_path = tmp_path / "approval-log.json"
    lock_errors: list[str] = []

    def append(i: int) -> None:
        try:
            append_approval_record(
                log_path,
                {
                    "flowId": "BF-LOGIN-001",
                    "artifact": "test-cases.yaml",
                    "status": "APPROVED",
                    "approver": f"user-{i}",
                    "decidedAt": f"2026-01-01T00:00:{i:02d}Z",
                },
            )
        except Exception as exc:  # noqa: BLE001
            lock_errors.append(str(exc))

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(append, range(12)))
    assert not lock_errors
    records = json.loads(log_path.read_text(encoding="utf-8"))["records"]
    assert len(records) == 12
    assert len({r["approver"] for r in records}) == 12


def test_healing_overlay_concurrent_updates(tmp_path: Path):
    automation = tmp_path / "automation"
    proposal = HealingProposal(
        healing_id="heal-1",
        flow_id="BF-PRODUCT-003",
        test_id="TC-1",
        locator_label="P6_SKU",
        status="APPROVED",
        old_locator="#old",
        new_locator="#P2_ITEM_CODE",
        fallbacks=[],
    )

    def apply(label: str) -> None:
        p = proposal.model_copy(update={"healing_id": label, "locator_label": label})
        apply_approved_proposal(automation, p)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(apply, [f"L{i}" for i in range(4)]))
    store = load_overlay_store(automation)
    assert len(store["entries"]) == 4


def test_live_event_sequence_stress(tmp_path: Path):
    from qa_orchestrator.live_browser_events import LiveEventStore

    path = tmp_path / "events.jsonl"
    store = LiveEventStore("run-seq", path=path)

    def emit(i: int) -> None:
        store.emit(phase="ACTION", action=f"CLICK-{i}", status="OK")

    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(emit, range(40)))
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    seqs = sorted(int(r["sequence"]) for r in rows)
    assert seqs == list(range(1, 41))
    assert len(seqs) == len(set(seqs))


def test_browser_close_idempotent(tmp_path: Path):
    profile = tmp_path / "run-a"
    profile.mkdir()
    atomic_write_json(profile / "session.json", {"run_id": "run-a", "status": "ACTIVE"})
    (profile / "close.signal").write_text("now", encoding="utf-8")
    changed1, meta1 = process_close_signal(profile)
    changed2, meta2 = process_close_signal(profile)
    assert changed1 is True
    assert meta1["status"] == "CLOSED"
    assert changed2 is False
    assert meta2["status"] == "CLOSED"


def test_repeated_close_signal_after_closed(tmp_path: Path):
    profile = tmp_path / "run-b"
    profile.mkdir()
    mark_session_closed(profile, extra={"run_id": "run-b"})
    (profile / "close.signal").write_text("again", encoding="utf-8")
    changed, meta = process_close_signal(profile)
    assert changed is True
    assert meta["status"] == "CLOSED"
    assert not (profile / "close.signal").exists()


def test_concurrent_runs_isolated_state(tmp_path: Path):
    base = tmp_path / "agent"
    save_snapshot(_snapshot("run-1"), base_dir=base)
    save_snapshot(_snapshot("run-2"), base_dir=base)

    def tag(run_id: str, marker: str) -> None:
        mutate_snapshot(run_id, lambda s: s.completed_steps.append(marker), base_dir=base)

    t1 = threading.Thread(target=tag, args=("run-1", "r1"))
    t2 = threading.Thread(target=tag, args=("run-2", "r2"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    one = load_snapshot("run-1", base_dir=base)
    two = load_snapshot("run-2", base_dir=base)
    assert one.completed_steps == ["r1"]
    assert two.completed_steps == ["r2"]


def test_resume_token_idempotent_field(tmp_path: Path):
    base = tmp_path / "agent"
    run_id = "run-resume"
    snap = _snapshot(run_id)
    snap.last_applied_resume_token = "token-1"
    save_snapshot(snap, base_dir=base)
    loaded = load_snapshot(run_id, base_dir=base)
    assert loaded.last_applied_resume_token == "token-1"
