#!/usr/bin/env python3
"""Approve SME-ready catalog flows for controlled QA/demo environments."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services" / "qa-orchestrator"), str(ROOT)]

from qa_orchestrator.bootstrap_approval import (
    bootstrap_approve_sme_ready_flows,
    bootstrap_approvals_enabled,
    format_gate_evaluation_table,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap SME-ready flow approvals (controlled env only)")
    parser.add_argument("--discovery-root", default="data/discovery-kb")
    parser.add_argument("--automation-dir", default=None)
    parser.add_argument(
        "--enable",
        action="store_true",
        help="Set QA_BOOTSTRAP_APPROVALS=true for this run only",
    )
    args = parser.parse_args()

    if args.enable:
        os.environ["QA_BOOTSTRAP_APPROVALS"] = "true"

    if not bootstrap_approvals_enabled():
        print(
            "Bootstrap approval is disabled. Set QA_BOOTSTRAP_APPROVALS=true or pass --enable.",
            file=sys.stderr,
        )
        return 2

    summary = bootstrap_approve_sme_ready_flows(
        discovery_root=args.discovery_root,
        automation_dir=args.automation_dir,
        enabled=True,
    )
    counts = summary.to_dict()["counts"]
    print(f"Approved baseline flows: {counts['approved_baseline_flows']}")
    print(f"Already approved: {counts['already_approved']}")
    print(f"Blocked: {counts['blocked']}")
    print(f"Rejected: {counts['rejected']}")
    print(f"Stale: {counts['stale']}")
    print("")
    print(f"Executable after approval: {counts['executable_after']}")
    print("")
    print(format_gate_evaluation_table(summary))
    if summary.blocked or summary.stale:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
