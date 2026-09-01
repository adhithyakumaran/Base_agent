import { NextResponse } from "next/server";
import { executeRun } from "@/lib/agent-runner";
import { deliverReport } from "@/lib/notify";
import { hasActiveRun, mutateState, pushHistory, readState } from "@/lib/store";
import type { AgentRun } from "@/lib/types";
import { uid } from "@/lib/utils";

export async function GET() {
  const { readState } = await import("@/lib/store");
  const state = await readState();
  return NextResponse.json({ runs: state.runs, locked: hasActiveRun(state) });
}

export async function POST(req: Request) {
  const body = await req.json();
  const goal = String(body.goal || "").trim();
  if (!goal) return NextResponse.json({ error: "Command required" }, { status: 400 });

  const type = (body.type || "adhoc") as AgentRun["type"];
  const knowledgeIds: string[] = Array.isArray(body.knowledgeIds) ? body.knowledgeIds : [];
  const notify: string[] = Array.isArray(body.channels) ? body.channels : ["email", "whatsapp"];

  // Hard lock: one command at a time
  const gate = await readState();
  if (hasActiveRun(gate)) {
    return NextResponse.json(
      {
        error: "Another command is already running. Wait until it finishes.",
        locked: true,
        activeRunId: gate.runs.find((r) => r.status === "running" || r.status === "queued")?.id,
      },
      { status: 409 }
    );
  }

  let runId = "";
  await mutateState((state) => {
    if (hasActiveRun(state)) return;
    const run: AgentRun = {
      id: uid("run"),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      type,
      goal,
      status: "queued",
      model: state.selectedModel,
      llmEnabled: state.selectedModel !== "disabled",
      traces: [],
      usage: { tokensIn: 0, tokensOut: 0, toolCalls: 0, steps: 0, llmCalls: 0 },
      knowledgePillIds: knowledgeIds,
      channelsNotified: [],
    };
    runId = run.id;
    state.runs = [run, ...state.runs].slice(0, 100);
    pushHistory(state, `Started ${type}: ${goal.slice(0, 80)}`, "client", { runId, goal });
  });

  if (!runId) {
    return NextResponse.json({ error: "Could not acquire run lock", locked: true }, { status: 409 });
  }

  const final = await mutateState(async (state) => {
    const idx = state.runs.findIndex((r) => r.id === runId);
    if (idx < 0) return;
    let run = state.runs[idx];
    const ids = [...new Set([...(knowledgeIds || []), ...(run.knowledgePillIds || [])])];
    const pills = state.knowledge.filter((k) => ids.includes(k.id));
    run.knowledgePillIds = ids;
    run = await executeRun(run, pills, async (updated) => {
      const i = state.runs.findIndex((r) => r.id === updated.id);
      if (i >= 0) state.runs[i] = updated;
    });

    if (notify.length && run.report) {
      const deliveries = await deliverReport(run, state.channels, notify);
      run.channelsNotified = deliveries.map((d) => `${d.channel}:${d.mode}`);
      run.traces.push({
        id: uid("tr"),
        at: new Date().toISOString(),
        kind: "report",
        message: `Report delivery: ${deliveries.map((d) => `${d.channel}=${d.mode}`).join(", ")}`,
        detail: JSON.stringify(deliveries, null, 2),
      });
      pushHistory(state, `Report routed (${run.channelsNotified.join(", ")})`, "system", { runId });
    }

    state.runs[idx] = run;
    state.usageTotal.tokensIn += run.usage.tokensIn;
    state.usageTotal.tokensOut += run.usage.tokensOut;
    state.usageTotal.runs += 1;
    pushHistory(state, `Finished ${run.status}: ${run.conclusion}`, "agent", {
      runId,
      conclusion: run.conclusion,
    });
  });

  const run = final.runs.find((r) => r.id === runId);
  return NextResponse.json({ run, locked: false });
}
