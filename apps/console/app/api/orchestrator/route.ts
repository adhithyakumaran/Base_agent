import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { repoRoot } from "@/lib/repo-root";
import { listPendingArtifacts } from "@/lib/approval-store";

const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL || "http://127.0.0.1:43124";
const REPO = repoRoot();
const INDEX = path.join(REPO, "data", "discovery-kb", "flows", "index.yaml");

export async function GET() {
  let readyFlows = 0;
  try {
    const raw = await fs.readFile(INDEX, "utf8");
    readyFlows = (raw.match(/status: READY/g) || []).length;
  } catch {
    readyFlows = 0;
  }

  let health: Record<string, unknown> | null = null;
  let connected = false;
  try {
    const res = await fetch(`${AGENT_URL}/health`, { cache: "no-store" });
    if (res.ok) {
      health = await res.json();
      connected = true;
    }
  } catch {
    connected = false;
  }

  const artifacts = await listPendingArtifacts();
  const pendingApprovals = artifacts.filter((a) => a.status === "PENDING_SME_APPROVAL").length;

  return NextResponse.json({
    connected,
    environment: process.env.QA_ENV || "UAT",
    executor: String(health?.executor || "playwright"),
    llmEnabled: Boolean(health?.llm_enabled),
    approvedFlows: Number(health?.primary_ready_flows ?? readyFlows),
    smeReadyFlows: readyFlows,
    pendingApprovals,
    safetyGate: "deterministic",
    agentMode: health?.llm_enabled ? "assisted" : "controlled",
    health,
  });
}
