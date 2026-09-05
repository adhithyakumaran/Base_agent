#!/usr/bin/env python3
"""Generate enterprise scenarios + test cases from READY flow KB YAML."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FLOWS_DIR = ROOT / "discovery" / "uat_ea" / "flows"
INDEX = FLOWS_DIR / "index.yaml"
OUT = ROOT / "automation" / "test-design" / "flows"


def load_ready_flow_ids() -> list[str]:
    index = yaml.safe_load(INDEX.read_text(encoding="utf-8"))
    ready = set(index.get("sme_ready", []))
    flows = index.get("flows", [])
    return [
        f["id"]
        for f in flows
        if f.get("status") == "READY" or f["id"] in ready
    ]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def extract_steps(flow: dict) -> list[str]:
    steps: list[str] = []
    bf = flow.get("business_flow")
    if isinstance(bf, list):
        for item in bf:
            if isinstance(item, str):
                steps.append(item)
            elif isinstance(item, dict):
                if "action" in item:
                    steps.append(str(item["action"]).strip())
                elif "steps" in item:
                    for s in item["steps"]:
                        if isinstance(s, dict) and "action" in s:
                            steps.append(str(s["action"]).strip())
    elif isinstance(bf, dict):
        for key, val in bf.items():
            if key in {"overview", "navigation", "product_discovery_pattern"}:
                continue
            if isinstance(val, list):
                for s in val:
                    if isinstance(s, dict) and "action" in s:
                        steps.append(f"[{key}] {s['action']}".strip())
            elif isinstance(val, dict) and "steps" in val:
                for s in val["steps"]:
                    if isinstance(s, dict) and "action" in s:
                        steps.append(f"[{key}] {s['action']}".strip())
    return steps


def extract_rules(flow: dict) -> list[str]:
    rules = flow.get("business_rules")
    out: list[str] = []
    if isinstance(rules, list):
        for r in rules:
            if isinstance(r, dict) and "rule" in r:
                out.append(str(r["rule"]).strip())
            elif isinstance(r, str):
                out.append(r.strip())
    elif isinstance(rules, dict):
        for _k, v in rules.items():
            if isinstance(v, dict) and "rule" in v:
                out.append(str(v["rule"]).strip())
    return out


def observed_scenarios(flow: dict) -> list[dict]:
    obs = flow.get("observed_scenarios") or []
    out: list[dict] = []
    for item in obs:
        if isinstance(item, dict):
            out.append(item)
        elif isinstance(item, str):
            out.append({"scenario": item, "status": "Observed"})
    return out


def build_scenarios(flow_id: str, flow: dict) -> dict:
    steps = extract_steps(flow)
    obs = observed_scenarios(flow)
    scenarios = []
    if steps:
        scenarios.append(
            {
                "id": f"SC-{flow_id}-001",
                "title": f"{flow.get('flow_name', flow_id)} — primary business path",
                "type": "functional",
                "priority": "P0",
                "source": "business_flow",
                "steps": steps,
                "tags": ["sanity", "regression", flow_id.lower()],
            }
        )
    for i, o in enumerate(obs, start=2):
        title = o.get("scenario") or o.get("result") or f"Observed scenario {i}"
        scenarios.append(
            {
                "id": f"SC-{flow_id}-{i:03d}",
                "title": str(title)[:200],
                "type": "observed",
                "priority": "P1" if i == 2 else "P2",
                "source": "observed_scenarios",
                "metadata": o,
                "tags": ["regression", flow_id.lower()],
            }
        )
    return {
        "schema": "automation_scenarios_v1",
        "flow_id": flow_id,
        "flow_name": flow.get("flow_name"),
        "status": "PENDING_SME_APPROVAL",
        "scenarios": scenarios,
    }


def safety_tags(flow_id: str, flow: dict) -> list[str]:
    tags: list[str] = []
    auto = flow.get("automation") or {}
    if auto.get("safety_guardrails") or auto.get("safety_guardrails"):
        tags.append("read-only-sanity")
    sec = flow.get("security") or {}
    if isinstance(sec, dict) and sec.get("transaction_protection"):
        tags.append("no-transaction")
    if flow_id in {"BF-ADMINISTRATION-009", "BF-MANUAL-INVOICE-009"}:
        tags.extend(["read-only-sanity", "no-transaction", "no-data-mutation"])
    return tags


def build_test_cases(flow_id: str, flow: dict) -> dict:
    flow_name = flow.get("flow_name", flow_id)
    rules = extract_rules(flow)
    extra_tags = safety_tags(flow_id, flow)
    base_tags = ["regression", flow_id.lower(), *extra_tags]

    cases: list[dict] = [
        {
            "id": f"TC-{flow_id}-P01",
            "title": f"{flow_name} — primary path succeeds",
            "type": "positive",
            "priority": "P0",
            "tags": ["sanity", *base_tags],
            "linked_scenario": f"SC-{flow_id}-001",
            "preconditions": flow.get("preconditions") or flow.get("actors"),
            "steps_summary": "Execute primary business_flow steps end-to-end.",
            "expected_result": flow.get("expected_success"),
            "automation": {
                "framework": "playwright",
                "spec_glob": f"tests/**/{flow_id}*.spec.ts",
                "test_match": f"TC-{flow_id}-P01",
            },
        },
        {
            "id": f"TC-{flow_id}-N01",
            "title": f"{flow_name} — required-field / access validation",
            "type": "negative",
            "priority": "P1",
            "tags": base_tags,
            "linked_scenario": f"SC-{flow_id}-001",
            "steps_summary": "Attempt flow with missing required input or unauthorized context.",
            "expected_result": "Application blocks progress with validation or access control.",
            "automation": {
                "framework": "playwright",
                "spec_glob": f"tests/**/{flow_id}*.spec.ts",
                "test_match": f"TC-{flow_id}-N01",
            },
        },
        {
            "id": f"TC-{flow_id}-E01",
            "title": f"{flow_name} — back navigation / context integrity",
            "type": "edge",
            "priority": "P2",
            "tags": base_tags,
            "linked_scenario": f"SC-{flow_id}-001",
            "steps_summary": "Validate Back/navigation preserves authorized context.",
            "expected_result": "User returns to expected page; session/context remains valid.",
            "automation": {
                "framework": "playwright",
                "spec_glob": f"tests/**/{flow_id}*.spec.ts",
                "test_match": f"TC-{flow_id}-E01",
            },
        },
    ]

    if flow.get("unknown_business_rules"):
        cases.append(
            {
                "id": f"TC-{flow_id}-E02",
                "title": f"{flow_name} — documented unknown-rule boundaries",
                "type": "edge",
                "priority": "P3",
                "tags": ["manual-review", *base_tags],
                "steps_summary": "Manual/assisted checks for KB-documented unknown rules only.",
                "expected_result": "No automation assertion beyond observed KB scope.",
                "automation": {"framework": "playwright", "test_match": f"TC-{flow_id}-E02", "mode": "skip-until-sme"},
            }
        )

    if rules:
        cases[0]["business_rules_validated"] = rules[:5]

    return {
        "schema": "automation_test_cases_v1",
        "flow_id": flow_id,
        "flow_name": flow_name,
        "status": "PENDING_SME_APPROVAL",
        "test_cases": cases,
    }


def build_suite(flow_id: str, flow: dict, cases: dict) -> dict:
    tc_ids = [c["id"] for c in cases["test_cases"]]
    sanity = [c["id"] for c in cases["test_cases"] if "sanity" in c.get("tags", [])]
    return {
        "schema": "automation_suite_v1",
        "suite_id": f"SUITE-{flow_id}",
        "flow_id": flow_id,
        "flow_name": flow.get("flow_name"),
        "status": "PENDING_SME_APPROVAL",
        "tags": ["regression", flow_id.lower(), *safety_tags(flow_id, flow)],
        "test_cases": tc_ids,
        "sanity_subset": sanity,
        "runner": {
            "framework": "playwright",
            "command_template": "npx playwright test --grep '@{flow_id}'",
        },
    }


def main() -> None:
    ready = load_ready_flow_ids()
    OUT.mkdir(parents=True, exist_ok=True)
    catalog: list[dict] = []
    for flow_id in sorted(set(ready)):
        path = FLOWS_DIR / f"{flow_id}.yaml"
        if not path.exists():
            continue
        flow = yaml.safe_load(path.read_text(encoding="utf-8"))
        out_dir = OUT / flow_id
        out_dir.mkdir(parents=True, exist_ok=True)

        scenarios = build_scenarios(flow_id, flow)
        cases = build_test_cases(flow_id, flow)
        suite = build_suite(flow_id, flow, cases)

        (out_dir / "scenarios.yaml").write_text(
            yaml.safe_dump(scenarios, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        (out_dir / "test-cases.yaml").write_text(
            yaml.safe_dump(cases, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        (out_dir / "suite.yaml").write_text(
            yaml.safe_dump(suite, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        catalog.append(
            {
                "flow_id": flow_id,
                "flow_name": flow.get("flow_name"),
                "artifacts": {
                    "scenarios": str(out_dir / "scenarios.yaml"),
                    "test_cases": str(out_dir / "test-cases.yaml"),
                    "suite": str(out_dir / "suite.yaml"),
                },
            }
        )

    catalog_doc = {
        "schema": "automation_catalog_v1",
        "ready_flow_count": len(catalog),
        "approval_status": "PENDING_SME",
        "flows": catalog,
    }
    (ROOT / "automation" / "catalog" / "index.yaml").parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "automation" / "catalog" / "index.yaml").write_text(
        yaml.safe_dump(catalog_doc, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"Generated artifacts for {len(catalog)} READY flows → {OUT}")


if __name__ == "__main__":
    main()
