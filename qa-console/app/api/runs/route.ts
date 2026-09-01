import { NextResponse } from "next/server";
import { executeRun } from "@/lib/agent-runner";
import { mutateState, pushHistory } from "@/lib/store";
import type { AgentRun } from "@/lib/types";
import { uid } from "@/lib/utils";

export async function GET() {
  const { readState } = await import("@/lib/store");
  const state = await readState();
  return NextResponse.json({ runs: state.runs });
}

export async function POST(req: Request) {
  const body = await req.json();
  const goal = String(body.goal || "").trim();
  if (!goal) return NextResponse.json({ error: "goal required" }, { status: 400 });

  const type = (body.type || "adhoc") as AgentRun["type"];
  const knowledgeIds: string[] = Array.isArray(body.knowledgeIds) ? body.knowledgeIds : [];
  const notify: string[] = Array.isArray(body.channels) ? body.channels : [];

  let runId = "";
  await mutateState((state) => {
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
    pushHistory(state, `Triggered ${type} run`, "client", { runId, goal });
  });

  // Execute synchronously for demo reliability (still streams via polling traces)
  const final = await mutateState(async (state) => {
    const idx = state.runs.findIndex((r) => r.id === runId);
    if (idx < 0) return;
    let run = state.runs[idx];
    const pills = state.knowledge.filter((k) => knowledgeIds.includes(k.id));
    run = await executeRun(run, pills, async (updated) => {
      const s = state;
      const i = s.runs.findIndex((r) => r.id === updated.id);
      if (i >= 0) s.runs[i] = updated;
    });

    // Channel fan-out (stub — records delivery intent; wire webhooks in OCI)
    if (notify.length && run.report) {
      run.channelsNotified = notify;
      run.traces.push({
        id: uid("tr"),
        at: new Date().toISOString(),
        kind: "report",
        message: `Report queued to channels: ${notify.join(", ")}`,
        detail: JSON.stringify(state.channels),
      });
      pushHistory(state, `Report dispatched (${notify.join(",")})`, "system", { runId });
    }

    state.runs[idx] = run;
    state.usageTotal.tokensIn += run.usage.tokensIn;
    state.usageTotal.tokensOut += run.usage.tokensOut;
    state.usageTotal.runs += 1;
    pushHistory(state, `Run ${run.status}: ${run.conclusion}`, "agent", {
      runId,
      conclusion: run.conclusion,
    });
  });

  const run = final.runs.find((r) => r.id === runId);
  return NextResponse.json({ run });
}
