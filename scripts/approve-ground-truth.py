#!/usr/bin/env python3
"""SME approval for Ground Truth JSON files under data/discovery-kb/gt/."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GT_DIR = REPO / "data" / "discovery-kb" / "gt"


def main() -> int:
    parser = argparse.ArgumentParser(description="Approve a Ground Truth JSON artifact (SME governance).")
    parser.add_argument("gt_id", help="GT file stem, e.g. gt-bf-product-003-positive")
    parser.add_argument("--approver", default="SME Reviewer", help="Approver display name")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    args = parser.parse_args()

    path = GT_DIR / f"{args.gt_id}.json"
    if not path.exists():
        raise SystemExit(f"GT file not found: {path}")

    doc = json.loads(path.read_text(encoding="utf-8"))
    prior = doc.get("status")
    doc["status"] = "approved"
    doc["approved_by"] = args.approver
    doc["approved_at"] = datetime.now(timezone.utc).isoformat()
    if isinstance(doc.get("approval"), dict):
        doc["approval"]["state"] = "approved"
        doc["approval"]["approved_by"] = args.approver
        doc["approval"]["approved_at"] = doc["approved_at"]

    print(f"GT: {args.gt_id}")
    print(f"  prior status: {prior}")
    print(f"  new status: approved")
    print(f"  approver: {args.approver}")
    print(f"  path: {path}")

    if args.dry_run:
        print("(dry-run — file not written)")
        return 0

    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print("Approved. Re-run LIVE_DEMO to allow validator Phase B.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
