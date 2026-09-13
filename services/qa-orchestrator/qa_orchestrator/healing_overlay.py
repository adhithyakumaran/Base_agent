"""Healing locator overlay schema — approved proposals only, never KB YAML mutation."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qa_orchestrator.models import HealingProposal

OVERLAY_SCHEMA = "healing_locator_overlay_v1"


def overlays_path(automation_dir: Path) -> Path:
    return automation_dir / "healing" / "approved" / "locator-overlays.json"


def load_overlay_store(automation_dir: Path) -> dict[str, Any]:
    path = overlays_path(automation_dir)
    if not path.exists():
        return empty_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return empty_store()
    if isinstance(data, dict) and data.get("schema") == OVERLAY_SCHEMA:
        return data
    return migrate_legacy_store(data)


def empty_store() -> dict[str, Any]:
    store = {"schema": OVERLAY_SCHEMA, "overlay_version": "", "overlay_hash": "", "entries": []}
    store["overlay_hash"] = compute_store_hash(store)
    return store


def migrate_legacy_store(legacy: Any) -> dict[str, Any]:
    """Convert old flow->label->selectors map into v1 store."""
    store = empty_store()
    if not isinstance(legacy, dict):
        return store
    for flow_id, labels in legacy.items():
        if flow_id in {"schema", "overlay_version", "overlay_hash", "entries"}:
            continue
        if not isinstance(labels, dict):
            continue
        for locator_label, selectors in labels.items():
            if not isinstance(selectors, list):
                continue
            store["entries"].append(
                {
                    "healing_id": f"legacy-{flow_id}-{locator_label}",
                    "flow_id": flow_id,
                    "test_id": "",
                    "step_id": "",
                    "locator_label": locator_label,
                    "status": "APPROVED",
                    "revoked": False,
                    "selectors": selectors,
                    "approved_at": datetime.now(timezone.utc).isoformat(),
                    "entry_version": 1,
                }
            )
    store = finalize_store(store)
    return store


def apply_approved_proposal(automation_dir: Path, proposal: HealingProposal) -> Path:
    if proposal.status != "APPROVED":
        raise ValueError("Only APPROVED proposals may update locator overlays")
    store = load_overlay_store(automation_dir)
    selectors: list[str] = []
    if proposal.new_locator:
        css = primary_to_css(proposal.new_locator)
        if css:
            selectors.append(css)
    for fb in proposal.fallbacks:
        css = primary_to_css(fb) if "getBy" in fb or fb.startswith("page.") else fb
        if css and css not in selectors:
            selectors.append(css)
    if not selectors:
        raise ValueError("Approved proposal has no usable CSS selectors for overlay")

    entry = {
        "healing_id": proposal.healing_id,
        "flow_id": proposal.flow_id,
        "test_id": proposal.test_id or "",
        "step_id": proposal.step_id or "",
        "locator_label": proposal.locator_label or "default",
        "status": "APPROVED",
        "revoked": False,
        "selectors": selectors,
        "old_locator": proposal.old_locator,
        "new_locator": proposal.new_locator,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "entry_version": 1,
    }
    entries = [e for e in store.get("entries", []) if not _same_target(e, entry)]
    entries.append(entry)
    store["entries"] = entries
    store = finalize_store(store)

    path = overlays_path(automation_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2), encoding="utf-8")
    return path


def load_overlays(automation_dir: Path) -> dict[str, dict[str, list[str]]]:
    """Legacy helper — flattened view for existing tests."""
    store = load_overlay_store(automation_dir)
    out: dict[str, dict[str, list[str]]] = {}
    for entry in store.get("entries", []):
        if entry.get("status") != "APPROVED" or entry.get("revoked"):
            continue
        flow = entry.get("flow_id", "")
        label = entry.get("locator_label", "default")
        out.setdefault(flow, {})[label] = list(entry.get("selectors") or [])
    return out


def validate_entry(entry: dict[str, Any]) -> tuple[bool, str]:
    required = ("healing_id", "flow_id", "locator_label", "status", "selectors")
    for key in required:
        if key not in entry:
            return False, f"missing field {key}"
    if entry.get("status") != "APPROVED":
        return False, "status is not APPROVED"
    if entry.get("revoked"):
        return False, "entry revoked"
    selectors = entry.get("selectors")
    if not isinstance(selectors, list) or not selectors:
        return False, "selectors must be non-empty list"
    if not all(isinstance(s, str) and s.strip() for s in selectors):
        return False, "invalid selector strings"
    return True, "ok"


def resolve_overlay_selectors(
    store: dict[str, Any],
    *,
    flow_id: str,
    locator_label: str,
    test_id: str = "",
    step_id: str = "",
) -> dict[str, Any] | None:
    matches: list[dict[str, Any]] = []
    for entry in store.get("entries", []):
        if not isinstance(entry, dict):
            continue
        ok, _ = validate_entry(entry)
        if not ok:
            continue
        if entry.get("flow_id") != flow_id:
            continue
        if entry.get("locator_label") != locator_label:
            continue
        entry_test = str(entry.get("test_id") or "")
        if entry_test and test_id and entry_test != test_id:
            continue
        entry_step = str(entry.get("step_id") or "")
        if entry_step and step_id and entry_step != step_id:
            continue
        matches.append(entry)
    if not matches:
        return None
    matches.sort(key=lambda e: str(e.get("approved_at") or ""), reverse=True)
    best = matches[0]
    return {
        "selectors": list(best.get("selectors") or []),
        "healing_id": best.get("healing_id"),
        "overlay_version": store.get("overlay_version"),
        "overlay_hash": store.get("overlay_hash"),
        "locator_source": "HEALING_OVERLAY",
        "entry_version": best.get("entry_version", 1),
    }


def finalize_store(store: dict[str, Any]) -> dict[str, Any]:
    store["schema"] = OVERLAY_SCHEMA
    store["overlay_version"] = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    store["overlay_hash"] = compute_store_hash(store)
    return store


def compute_store_hash(store: dict[str, Any]) -> str:
    payload = {
        "schema": store.get("schema"),
        "entries": store.get("entries", []),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return digest


def _same_target(existing: dict[str, Any], new: dict[str, Any]) -> bool:
    return (
        existing.get("flow_id") == new.get("flow_id")
        and existing.get("locator_label") == new.get("locator_label")
        and str(existing.get("test_id") or "") == str(new.get("test_id") or "")
        and str(existing.get("step_id") or "") == str(new.get("step_id") or "")
    )


def primary_to_css(primary: str) -> str | None:
    if primary.startswith("#") or primary.startswith("["):
        return primary
    if "getByTestId" in primary:
        import re

        match = re.search(r"getByTestId\('([^']+)'\)", primary)
        if match:
            return f'[data-testid="{match.group(1)}"]'
    if "getByRole" in primary:
        import re

        match = re.search(r"getByRole\('([^']+)',\s*\{\s*name:\s*'([^']+)'", primary)
        if match:
            role = match.group(1)
            name = match.group(2).replace('"', '\\"')
            if role == "button":
                return f'button[aria-label="{name}"]'
            return f'{role}[aria-label="{name}"]'
    if primary.startswith("page.locator("):
        import re

        match = re.search(r"locator\('([^']+)'\)", primary)
        if match:
            return match.group(1)
    return primary if primary and not primary.startswith("page.") else None
