import type { AgentRun, TraceEvent } from "@/lib/types";
import { mapConclusionToRunStatus, mergeAgentPauseIntoRun, type AgentPauseInfo } from "@/lib/run-resume";
import { fetchInternalAgent } from "@/lib/internal-agent";
import { uid } from "@/lib/utils";

export type OrchestratorBridgeResult = Record<string, unknown>;

export async function fetchAgentPauseInfo(runId: string): Promise<AgentPauseInfo | null> {
  try {
    const res = await fetchInternalAgent(`/agent/${encodeURIComponent(runId)}`, { cache: "no-store" });
    if (!res.ok) return null;
    const json = (await res.json()) as AgentPauseInfo & { ok?: boolean };
    return json;
  } catch {
    return null;
  }
}

export function applyOrchestratorResultToRun(
  run: AgentRun,
  result: OrchestratorBridgeResult,
  traces: TraceEvent[]
): AgentRun {
  const local = (result.local as Record<string, unknown> | undefined) || {};
  const intent = (local.intent as Record<string, unknown>) || {};
  const discovery = (local.discovery as Record<string, unknown>) || {};
  const agent = (result.agent as Record<string, unknown> | undefined) || {};
  const metadata = (result.metadata as Record<string, unknown> | undefined) || {};
  const diagnostics =
    (result.decision_diagnostics as Record<string, unknown> | undefined) ||
    (agent.decision_diagnostics as Record<string, unknown> | undefined) ||
    (metadata.decision_diagnostics as Record<string, unknown> | undefined) ||
    (local.decision_diagnostics as Record<string, unknown> | undefined);

  run.conclusion = String(result.conclusion || "UNKNOWN");
  run.reasonCode = String(result.reason_code || diagnostics?.reason_code || "");
  if (diagnostics) {
    run.decisionDiagnostics = diagnostics;
  }
  run.usage.toolCalls = Number(result.tool_calls || 0);
  run.usage.steps = Number(result.steps || 0);
  run.usage.llmCalls = Number(result.llm_calls || 0);
  run.usage.tokensIn = Number(result.tokens_in || 0);
  run.usage.tokensOut = Number(result.tokens_out || 0);

  traces.push({
    id: uid("tr"),
    at: new Date().toISOString(),
    kind: "decision",
    message: `Intent: ${String(intent.execution_mode || "unknown")} — ${String(intent.reasoning || "classified")}`,
    detail: JSON.stringify(intent, null, 2),
  });

  const suggestions = discovery.suggestions as string[] | undefined;
  if (suggestions?.length) {
    traces.push({
      id: uid("tr"),
      at: new Date().toISOString(),
      kind: "observe",
      message: `Discovery insights (${suggestions.length})`,
      detail: suggestions.join("\n"),
    });
  }

  traces.push({
    id: uid("tr"),
    at: new Date().toISOString(),
    kind: "observe",
    message: `Validation phase ${String(local.validation_phase || "A")} → ${run.conclusion}${
      run.reasonCode ? ` (${run.reasonCode})` : ""
    }`,
    detail: JSON.stringify(
      {
        reason: run.reasonCode,
        decision_diagnostics: diagnostics ?? run.decisionDiagnostics,
        classifier: local.classifier,
        execution_mode: local.execution_mode,
        executor: local.executor,
        suites: (local.suite_plan as { suite_ids?: unknown[] } | undefined)?.suite_ids,
      },
      null,
      2
    ),
  });

  const orchestratorMd = typeof local.report_markdown === "string" ? local.report_markdown : "";
  const md =
    orchestratorMd ||
    [
      `# QA Agent Report`,
      ``,
      `- **Run ID:** ${run.id}`,
      `- **Conclusion:** ${run.conclusion}`,
      `- **Reason:** ${run.reasonCode || "n/a"}`,
    ].join("\n");

  run.report = {
    summary: `${run.conclusion}: ${run.goal}`,
    markdown: md,
    json: {
      runId: run.id,
      conclusion: run.conclusion,
      reasonCode: run.reasonCode,
      decisionDiagnostics: run.decisionDiagnostics,
      usage: run.usage,
      traces,
      agent: result,
      resumeToken: run.resumeToken,
    },
  };

  run.status = mapConclusionToRunStatus(run.conclusion);
  run.updatedAt = new Date().toISOString();
  return run;
}

export async function enrichWaitingRunFromAgent(run: AgentRun): Promise<AgentRun> {
  if (run.status !== "waiting_approval" && run.conclusion !== "WAITING_FOR_APPROVAL") {
    return run;
  }
  const agent = await fetchAgentPauseInfo(run.id);
  if (!agent) return run;
  return mergeAgentPauseIntoRun(run, agent);
}
