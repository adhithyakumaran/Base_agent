import { NextResponse } from "next/server";
import { listPendingArtifacts, transitionArtifact } from "@/lib/approval-store";
import { extractAuthenticatedActor, requireApiAuth, requireMutationAuth } from "@/lib/api-auth";

export async function GET(req: Request) {
  const denied = requireApiAuth(req);
  if (denied) return denied;

  const artifacts = await listPendingArtifacts();
  const pending = artifacts.filter((a) => a.status === "PENDING_SME_APPROVAL");
  return NextResponse.json({
    status: "ok",
    pendingCount: pending.length,
    artifacts,
    security_boundary: "scout_api_token_v1",
  });
}

export async function POST(req: Request) {
  const denied = requireMutationAuth(req);
  if (denied) return denied;

  const body = await req.json();
  const flowId = String(body.flowId || "").trim();
  const artifact = String(body.artifact || "test-cases.yaml").trim();
  const action = String(body.action || "").trim().toLowerCase();
  const actor = extractAuthenticatedActor(req);
  const approver = String(body.approver || body.approverIdentity || actor).trim();
  const note = body.note ? String(body.note) : undefined;
  const reason = body.reason ? String(body.reason) : note;

  if (!flowId) {
    return NextResponse.json({ error: "flowId required" }, { status: 400 });
  }
  if (action !== "approve" && action !== "reject") {
    return NextResponse.json({ error: "action must be approve or reject" }, { status: 400 });
  }
  if (!approver) {
    return NextResponse.json({ error: "authenticated approver identity required" }, { status: 401 });
  }

  try {
    const record = await transitionArtifact({
      flowId,
      artifact: artifact as "test-cases.yaml" | "scenarios.yaml" | "suite.yaml",
      action,
      approver,
      note: reason || note,
    });
    return NextResponse.json({
      ok: true,
      record: {
        ...record,
        actor: approver,
        source: approver.startsWith("bootstrap-") ? "BOOTSTRAP" : "AUTHENTICATED_API",
        decision: action,
        reason: reason || note || "",
      },
    });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 400 }
    );
  }
}
