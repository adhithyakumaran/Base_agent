import { NextResponse } from "next/server";
import { extractAuthenticatedActor, requireMutationAuth, requireRunAccess } from "@/lib/api-auth";
import {
  approveGroundTruthAndRevalidateRun,
  evaluateGroundTruthApprovalEligibility,
  isSmeAuthorized,
  readGroundTruthDoc,
} from "@/lib/ground-truth-approve";
import { mutateState, pushHistory, readState } from "@/lib/store";
import { uid } from "@/lib/utils";

export async function GET(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const denied = await requireRunAccess(req, id);
  if (denied) return denied;

  const state = await readState();
  const run = state.runs.find((r) => r.id === id);
  if (!run) return NextResponse.json({ error: "not found" }, { status: 404 });

  const eligibility = await evaluateGroundTruthApprovalEligibility(run);
  const smeAuthorized = isSmeAuthorized(req);
  let gt = null;
  if (eligibility.gtId) {
    gt = await readGroundTruthDoc(eligibility.gtId);
  }

  return NextResponse.json({
    eligible: eligibility.eligible && smeAuthorized,
    eligibility,
    smeAuthorized,
    gt,
  });
}

export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const denied = requireMutationAuth(req);
  if (denied) return denied;
  const deniedRun = await requireRunAccess(req, id);
  if (deniedRun) return deniedRun;

  if (!isSmeAuthorized(req)) {
    return NextResponse.json({ error: "Forbidden", detail: "SME reviewer role required" }, { status: 403 });
  }

  const body = await req.json().catch(() => ({}));
  const gtId = String(body.gt_id || body.gtId || "").trim();
  if (!gtId) {
    return NextResponse.json({ error: "gt_id required" }, { status: 400 });
  }

  const actor = extractAuthenticatedActor(req);
  const state = await readState();
  const existing = state.runs.find((r) => r.id === id);
  if (!existing) {
    return NextResponse.json({ error: "run not found" }, { status: 404 });
  }

  const eligibility = await evaluateGroundTruthApprovalEligibility(existing);
  if (!eligibility.eligible || eligibility.gtId !== gtId) {
    return NextResponse.json(
      { error: "run not eligible for ground truth approval", reason: eligibility.reason },
      { status: 409 }
    );
  }

  try {
    let updatedRun = existing;
    await mutateState(async (draft) => {
      const idx = draft.runs.findIndex((r) => r.id === id);
      if (idx < 0) throw new Error("run not found");
      updatedRun = await approveGroundTruthAndRevalidateRun(draft.runs[idx], gtId, actor);
      draft.runs[idx] = updatedRun;
      pushHistory(draft, `Ground Truth approved for run ${id.slice(0, 8)}`, actor, {
        runId: id,
        gtId,
        conclusion: updatedRun.conclusion,
      });
      draft.runs[idx].traces.push({
        id: uid("tr"),
        at: new Date().toISOString(),
        kind: "report",
        message: "Audit: ground_truth.approve",
        detail: JSON.stringify({ gt_id: gtId, approver: actor, run_id: id }, null, 2),
      });
    });

    return NextResponse.json({ run: updatedRun });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    const status = message.includes("already approved") ? 409 : 500;
    return NextResponse.json({ error: message }, { status });
  }
}
