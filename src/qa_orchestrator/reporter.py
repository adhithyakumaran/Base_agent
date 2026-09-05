from __future__ import annotations

from qa_orchestrator.models import OrchestratorResult


def build_markdown_report(
    *,
    result: OrchestratorResult,
    traces: list[dict[str, str]] | None = None,
) -> str:
    intent = result.intent
    suite = result.suite_plan
    execution = result.execution
    validation = result.validation
    discovery = result.discovery

    lines = [
        "# QA Orchestrator Report",
        "",
        "## Request",
        f"- **Goal:** {result.goal}",
        f"- **Run type:** {result.run_type}",
        f"- **Execution mode:** `{intent.execution_mode}`",
        f"- **Capability:** {intent.capability or '—'}",
        f"- **Classifier:** {intent.classifier} (confidence {intent.confidence:.0%})",
        "",
        "## Conclusion",
        f"- **Status:** **{result.conclusion}**",
        f"- **Reason:** `{result.reason_code}`",
        f"- **Validation phase:** {validation.phase}",
        "",
        "## Intent",
        intent.reasoning,
        "",
        f"- **Primary flows:** {', '.join(intent.flow_ids) or '—'}",
        f"- **Supporting (DRAFT):** {', '.join(intent.supporting_flow_ids) or '—'}",
    ]
    if intent.params:
        lines.append(f"- **Parameters:** `{intent.params}`")

    lines.extend(
        [
            "",
            "## Suite selection (deterministic)",
        ]
    )
    for note in suite.notes:
        lines.append(f"- {note}")
    lines.append(f"- **Suite IDs:** {', '.join(suite.suite_ids) or '—'}")
    lines.append(f"- **Flows to execute:** {', '.join(suite.flow_ids) or '—'}")
    lines.append("")
    lines.append("### Commands")
    for cmd in suite.commands:
        lines.append(f"1. `{cmd}`")

    if discovery:
        lines.extend(
            [
                "",
                "## Discovery",
                f"- **Mode:** {discovery.mode} · **Pages:** {discovery.pages_crawled}",
                f"- **Seed:** {discovery.seed_url or '—'}",
            ]
        )
        for s in discovery.suggestions:
            lines.append(f"- {s}")

    lines.extend(
        [
            "",
            "## Execution",
            f"- **Executor:** {execution.mode}",
            f"- **Elapsed:** {execution.elapsed_ms} ms",
            f"- **LLM calls:** {result.llm_calls} · **Suite runs:** {result.steps}",
            f"- **Tokens:** in {result.tokens_in} / out {result.tokens_out}",
            "",
            validation.summary,
            "",
        ]
    )
    if execution.error:
        lines.append(f"- **Error:** {execution.error}")
    for obs in execution.observations:
        status = "PASS" if obs.ok else "FAIL"
        lines.append(f"- [{status}] `{obs.action}` — {obs.message}")

    if validation.findings:
        lines.extend(["", "## Findings"])
        for f in validation.findings:
            lines.append(f"- **{f.severity.upper()}** `{f.code}` — {f.message}")

    if result.kb_refs:
        lines.extend(["", "## KB refs", ", ".join(result.kb_refs)])

    if traces:
        lines.extend(["", "## Trace"])
        for t in traces:
            lines.append(f"- `{t.get('at', '')}` **{t.get('kind', 'info')}** — {t.get('message', '')}")

    lines.extend(
        [
            "",
            "## Policy",
            "- 19 READY flows = primary automation; 6 DRAFT = supporting context until SME approval",
            "- LLM classifies intent only; Playwright executes approved suites deterministically",
            "- Morning sanity runs all suites with zero LLM at execution time",
            "- Phase A: honest NEEDS_REVIEW until SME approves Ground Truth",
            "- Swap Groq → Claude via `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`",
        ]
    )
    return "\n".join(lines)
