from __future__ import annotations

from qa_orchestrator.models import ExecutionPlan, ExecutionResult, OrchestratorResult, ValidationResult


def build_markdown_report(
    *,
    result: OrchestratorResult,
    traces: list[dict[str, str]] | None = None,
) -> str:
    plan = result.plan
    execution = result.execution
    validation = result.validation
    lines = [
        "# QA Orchestrator Report",
        "",
        f"- **Goal:** {result.goal}",
        f"- **Run type:** {result.run_type}",
        f"- **Conclusion:** {result.conclusion}",
        f"- **Reason:** {result.reason_code}",
        f"- **Validation phase:** {validation.phase}",
        f"- **Planner:** {plan.planner}",
        f"- **Executor:** OpenClaw ({execution.mode})",
        f"- **LLM calls:** {result.llm_calls} · **Steps:** {result.steps}",
        f"- **Tokens:** in {result.tokens_in} / out {result.tokens_out}",
        "",
        "## Summary",
        validation.summary,
        "",
        "## Plan",
        plan.summary,
        "",
    ]
    for i, step in enumerate(plan.steps):
        lines.append(f"{i + 1}. `{step.action}` — {step.target or step.note}")
    lines.extend(["", "## Execution"])
    if execution.error:
        lines.append(f"- **Error:** {execution.error}")
    for obs in execution.observations:
        status = "ok" if obs.ok else "FAIL"
        lines.append(f"- Step {obs.step_index + 1} `{obs.action}` → **{status}**: {obs.message}")
    if validation.findings:
        lines.extend(["", "## Findings"])
        for f in validation.findings:
            lines.append(f"- **{f.severity.upper()}** `{f.code}` — {f.message}")
    if plan.kb_refs:
        lines.extend(["", "## KB refs", ", ".join(plan.kb_refs)])
    if traces:
        lines.extend(["", "## Trace"])
        for t in traces:
            lines.append(f"- `{t.get('at', '')}` **{t.get('kind', 'info')}** — {t.get('message', '')}")
    lines.extend(
        [
            "",
            "## Policy",
            "- No loop-until-success",
            "- Phase A: honest NEEDS_REVIEW until SME approves Ground Truth",
            "- Phase B: deterministic GT compare when approved facts exist",
        ]
    )
    return "\n".join(lines)
