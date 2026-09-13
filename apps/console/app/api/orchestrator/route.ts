import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { repoRoot } from "@/lib/repo-root";
import { evaluateFlowExecution, listPendingArtifacts } from "@/lib/approval-store";

const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL || "http://127.0.0.1:43124";
const REPO = repoRoot();
const INDEX = path.join(REPO, "data", "discovery-kb", "flows", "index.yaml");
const DESIGN_ROOT = path.join(REPO, "apps", "automation", "test-design", "flows");

async function readSmeReady(raw: string): Promise<Set<string>> {
  const ready = new Set<string>();
  let inBlock = false;
  for (const line of raw.split("\n")) {
    if (/^sme_ready:\s*$/.test(line)) {
      inBlock = true;
      continue;
    }
    if (inBlock) {
      const hit = line.match(/^\s+-\s+(BF-[A-Z0-9-]+)\s*$/);
      if (hit) ready.add(hit[1]);
      else if (line.trim() && !/^\s/.test(line)) break;
    }
  }
  return ready;
}

async function readFlowIds(raw: string): Promise<string[]> {
  const ids: string[] = [];
  for (const line of raw.split("\n")) {
    const hit = line.match(/^\s+-\s+id:\s*(BF-[A-Z0-9-]+)\s*$/);
    if (hit) ids.push(hit[1]);
  }
  return ids;
}

async function readApprovalStatus(flowId: string): Promise<string | undefined> {
  const tcPath = path.join(DESIGN_ROOT, flowId, "test-cases.yaml");
  try {
    const raw = await fs.readFile(tcPath, "utf8");
    return raw.match(/^status:\s*(PENDING_SME_APPROVAL|APPROVED|REJECTED)\s*$/m)?.[1];
  } catch {
    return undefined;
  }
}

export async function GET() {
  let raw = "";
  try {
    raw = await fs.readFile(INDEX, "utf8");
  } catch {
    raw = "";
  }

  const smeReadySet = await readSmeReady(raw);
  const flowIds = await readFlowIds(raw);
  let approved = 0;
  let executable = 0;
  let pendingApproval = 0;

  for (const flowId of flowIds) {
    const approvalStatus = await readApprovalStatus(flowId);
    if (approvalStatus === "APPROVED") approved += 1;
    if (approvalStatus === "PENDING_SME_APPROVAL") pendingApproval += 1;
    try {
      const gate = await evaluateFlowExecution(flowId);
      if (gate.executable) executable += 1;
    } catch {
      /* skip */
    }
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
  const pendingArtifacts = artifacts.filter((a) => a.status === "PENDING_SME_APPROVAL").length;

  return NextResponse.json({
    connected,
    environment: process.env.QA_ENV || "UAT",
    executor: String(health?.executor || "playwright"),
    llmEnabled: Boolean(health?.llm_enabled),
    flowCounts: {
      total: flowIds.length,
      smeReady: smeReadySet.size,
      approved,
      executable,
      awaitingApproval: pendingApproval,
      pendingArtifacts,
    },
    pendingApprovals: pendingArtifacts,
    safetyGate: "deterministic",
    agentMode: health?.llm_enabled ? "assisted" : "controlled",
    health,
  });
}
