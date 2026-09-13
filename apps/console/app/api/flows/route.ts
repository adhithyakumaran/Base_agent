import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { repoRoot } from "@/lib/repo-root";

const REPO = repoRoot();
const INDEX = path.join(REPO, "data", "discovery-kb", "flows", "index.yaml");
const DESIGN_ROOT = path.join(REPO, "apps", "automation", "test-design", "flows");

type FlowRow = {
  id: string;
  name: string;
  status: string;
  file: string;
  parent?: string;
  testCount: number;
  approvalStatus?: string;
  smeReady: boolean;
  executable: boolean;
};

function parseIndex(raw: string): { smeReady: Set<string>; flows: Omit<FlowRow, "testCount" | "approvalStatus" | "smeReady" | "executable">[] } {
  const smeReady = new Set<string>();
  const flows: Omit<FlowRow, "testCount" | "approvalStatus" | "smeReady" | "executable">[] = [];
  let inSme = false;
  let inFlows = false;
  let current: Partial<Omit<FlowRow, "testCount" | "approvalStatus" | "smeReady" | "executable">> | null = null;

  for (const line of raw.split("\n")) {
    if (/^sme_ready:\s*$/.test(line)) {
      inSme = true;
      inFlows = false;
      continue;
    }
    if (/^flows:\s*$/.test(line)) {
      inFlows = true;
      inSme = false;
      continue;
    }
    if (inSme) {
      const hit = line.match(/^\s+-\s+(BF-[A-Z0-9-]+)\s*$/);
      if (hit) smeReady.add(hit[1]);
      else if (line.trim() && !/^\s/.test(line)) inSme = false;
    }
    if (inFlows) {
      const idMatch = line.match(/^\s+-\s+id:\s*(.+)\s*$/);
      if (idMatch) {
        if (current?.id) flows.push(current as typeof flows[number]);
        current = { id: idMatch[1].trim() };
        continue;
      }
      if (!current) continue;
      const file = line.match(/^\s+file:\s*(.+)\s*$/);
      const name = line.match(/^\s+name:\s*(.+)\s*$/);
      const status = line.match(/^\s+status:\s*(.+)\s*$/);
      const parent = line.match(/^\s+parent:\s*(.+)\s*$/);
      if (file) current.file = file[1].trim();
      if (name) current.name = name[1].trim();
      if (status) current.status = status[1].trim();
      if (parent) current.parent = parent[1].trim();
    }
  }
  if (current?.id) flows.push(current as typeof flows[number]);
  return { smeReady, flows };
}

async function readTestCount(flowId: string): Promise<number> {
  const tcPath = path.join(DESIGN_ROOT, flowId, "test-cases.yaml");
  try {
    const raw = await fs.readFile(tcPath, "utf8");
    return (raw.match(/^- id:\s*TC-/gm) || []).length;
  } catch {
    return 0;
  }
}

async function readApprovalStatus(flowId: string): Promise<string | undefined> {
  const tcPath = path.join(DESIGN_ROOT, flowId, "test-cases.yaml");
  try {
    const raw = await fs.readFile(tcPath, "utf8");
    const match = raw.match(/^status:\s*(PENDING_SME_APPROVAL|APPROVED|REJECTED)\s*$/m);
    return match?.[1];
  } catch {
    return undefined;
  }
}

export async function GET(req: Request) {
  try {
    const raw = await fs.readFile(INDEX, "utf8");
    const { smeReady, flows } = parseIndex(raw);
    const url = new URL(req.url);
    const filter = url.searchParams.get("filter") || "all";

    const enriched: FlowRow[] = [];
    for (const flow of flows) {
      const testCount = await readTestCount(flow.id);
      const approvalStatus = await readApprovalStatus(flow.id);
      const inSme = smeReady.has(flow.id);
      const executable = inSme && approvalStatus === "APPROVED" && flow.status === "READY";
      enriched.push({
        ...flow,
        name: flow.name || flow.id,
        status: flow.status || "DRAFT",
        file: flow.file || `${flow.id}.yaml`,
        testCount,
        approvalStatus,
        smeReady: inSme,
        executable,
      });
    }

    let rows = enriched;
    if (filter === "approved") {
      rows = rows.filter((f) => f.approvalStatus === "APPROVED" && f.status === "READY");
    } else if (filter === "sme_ready") {
      rows = rows.filter((f) => f.smeReady && f.status === "READY");
    } else if (filter === "needs_review") {
      rows = rows.filter(
        (f) => f.approvalStatus === "PENDING_SME_APPROVAL" || f.status === "DRAFT" || f.status === "SUPERSEDED"
      );
    } else if (filter === "sanity") {
      rows = rows.filter((f) => f.smeReady && f.status === "READY");
    }

    const approvedCount = enriched.filter((f) => f.approvalStatus === "APPROVED" && f.status === "READY").length;
    const smeReadyCount = enriched.filter((f) => f.smeReady && f.status === "READY").length;

    return NextResponse.json({
      flows: rows.sort((a, b) => a.id.localeCompare(b.id)),
      totals: {
        all: enriched.length,
        approved: approvedCount,
        smeReady: smeReadyCount,
        ready: enriched.filter((f) => f.status === "READY").length,
      },
    });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
