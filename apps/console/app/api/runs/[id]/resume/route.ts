import { NextResponse } from "next/server";
import { extractAuthenticatedActor, requireMutationAuth, requireRunAccess } from "@/lib/api-auth";
import { applyOrchestratorResultToRun, enrichWaitingRunFromAgent } from "@/lib/orchestrator-bridge";
import { fetchInternalAgent } from "@/lib/internal-agent";
import { mutateState, pushHistory, readState } from "@/lib/store";
import { uid } from "@/lib/utils";

function unwrapResumePayload(payload: Record<string, unknown>): Record<string, unknown> {
  if (typeof payload.conclusion === "string") {
    return payload;
  }
  const nested = payload.result as Record<string, unknown> | undefined;
  if (nested && typeof nested.conclusion === "string") {
    return nested;
  }
  return payload;
}

export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const denied = requireMutationAuth(req);
  if (denied) return denied;
  const deniedRun = await requireRunAccess(req, id);
  if (deniedRun) return deniedRun;

  const body = await req.json().catch(() => ({}));
  const actor = extractAuthenticatedActor(req);
  const resumeToken = body.resume_token ? String(body.resume_token) : undefined;
  const reason = String(body.reason || "console operator approved run continuation");

  const gate = await readState();
  const existing = gate.runs.find((r) => r.id === id);
  if (!existing) {
    return NextResponse.json({ error: "run not found" }, { status: 404 });
  }
  if (existing.status !== "waiting_approval" && existing.conclusion !== "WAITING_FOR_APPROVAL") {
    return NextResponse.json(
      { error: "run is not waiting for approval", status: existing.status, conclusion: existing.conclusion },
      { status: 409 }
    );
  }

  let agentPayload: Record<string, unknown> | null = null;
  try {
    const agentRes = await fetchInternalAgent(`/agent/${encodeURIComponent(id)}`, { cache: "no-store" });
    if (agentRes.ok) {
      agentPayload = (await agentRes.json()) as Record<string, unknown>;
    }
  } catch {
    /* warm server may still accept resume */
  }

  const token = resumeToken || existing.resumeToken || (agentPayload?.resume_token as string | undefined);
  if (!token) {
    return NextResponse.json({ error: "resume_token unavailable — warm server offline?" }, { status: 503 });
  }

  await mutateState((state) => {
    const idx = state.runs.findIndex((r) => r.id === id);
    if (idx >= 0) {
      state.runs[idx].status = "resuming";
      state.runs[idx].updatedAt = new Date().toISOString();
      state.runs[idx].traces.push({
        id: uid("tr"),
        at: new Date().toISOString(),
        kind: "decision",
        message: "Resuming run after operator approval",
        detail: reason,
      });
    }
  });

  let resumeRes: Response;
  try {
    resumeRes = await fetchInternalAgent(`/agent/${encodeURIComponent(id)}/resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume_token: token, reason }),
      signal: AbortSignal.timeout(300_000),
    });
  } catch (e) {
    await mutateState((state) => {
      const idx = state.runs.findIndex((r) => r.id === id);
      if (idx >= 0) state.runs[idx].status = "waiting_approval";
    });
    return NextResponse.json({ error: e instanceof Error ? e.message : "resume_failed" }, { status: 503 });
  }

  const resumeJson = (await resumeRes.json()) as { ok?: boolean; result?: Record<string, unknown>; error?: string };
  if (!resumeRes.ok || !resumeJson.ok || !resumeJson.result) {
    await mutateState((state) => {
      const idx = state.runs.findIndex((r) => r.id === id);
      if (idx >= 0) {
        state.runs[idx].status = "waiting_approval";
        state.runs[idx].traces.push({
          id: uid("tr"),
          at: new Date().toISOString(),
          kind: "error",
          message: "Resume rejected",
          detail: resumeJson.error || `http_${resumeRes.status}`,
        });
      }
    });
    return NextResponse.json({ error: resumeJson.error || "resume_rejected" }, { status: 400 });
  }

  const orchestratorResult = unwrapResumePayload(resumeJson.result);
  const summaryNote = String(orchestratorResult.summary || "");

  let updatedRun = existing;
  let idempotent = false;

  await mutateState(async (state) => {
    const idx = state.runs.findIndex((r) => r.id === id);
    if (idx < 0) return;
    const run = { ...state.runs[idx], traces: [...state.runs[idx].traces] };

    if (summaryNote.toLowerCase().includes("idempotent")) {
      idempotent = true;
      run.traces.push({
        id: uid("tr"),
        at: new Date().toISOString(),
        kind: "info",
        message: "Idempotent resume — no duplicate actions",
      });
      run.status = "waiting_approval";
      state.runs[idx] = run;
      updatedRun = run;
      return;
    }

    applyOrchestratorResultToRun(run, orchestratorResult, run.traces);
    run.traces.push({
      id: uid("tr"),
      at: new Date().toISOString(),
      kind: "decision",
      message: `Resume complete → ${run.conclusion}`,
      detail: `actor=${actor}`,
    });

    if (run.status === "waiting_approval") {
      const enriched = await enrichWaitingRunFromAgent(run);
      Object.assign(run, enriched);
    }

    state.runs[idx] = run;
    updatedRun = run;
    pushHistory(state, `Resumed run ${id.slice(0, 8)} → ${run.conclusion}`, actor, { runId: id });
  });

  return NextResponse.json({ ok: true, run: updatedRun, idempotent });
}
