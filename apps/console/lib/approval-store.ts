import { promises as fs } from "fs";
import path from "path";
import { repoRoot } from "@/lib/repo-root";

export type ApprovalStatus = "PENDING_SME_APPROVAL" | "APPROVED" | "REJECTED";

export type ApprovalArtifact = {
  flowId: string;
  artifact: "test-cases.yaml" | "scenarios.yaml" | "suite.yaml";
  status: ApprovalStatus;
  approver?: string;
  decidedAt?: string;
  note?: string;
};

export type ApprovalRecord = {
  flowId: string;
  artifact: ApprovalArtifact["artifact"];
  status: ApprovalStatus;
  approver: string;
  decidedAt: string;
  note?: string;
};

const REPO = repoRoot();
const DESIGN_ROOT = path.join(REPO, "apps", "automation", "test-design", "flows");
const LOG_PATH = path.join(REPO, "apps", "automation", "approval", "approval-log.json");

const ARTIFACTS: ApprovalArtifact["artifact"][] = ["test-cases.yaml", "scenarios.yaml", "suite.yaml"];

export function isValidFlowId(flowId: string): boolean {
  return /^BF-[A-Z0-9-]+$/.test(flowId);
}

export function isValidArtifact(name: string): name is ApprovalArtifact["artifact"] {
  return ARTIFACTS.includes(name as ApprovalArtifact["artifact"]);
}

export function isValidTransition(from: ApprovalStatus, to: ApprovalStatus): boolean {
  if (from === to) return false;
  if (from === "PENDING_SME_APPROVAL" && (to === "APPROVED" || to === "REJECTED")) return true;
  if (from === "REJECTED" && to === "PENDING_SME_APPROVAL") return true;
  return false;
}

async function readYamlStatus(filePath: string): Promise<ApprovalStatus | null> {
  try {
    const raw = await fs.readFile(filePath, "utf8");
    const match = raw.match(/^status:\s*(PENDING_SME_APPROVAL|APPROVED|REJECTED)\s*$/m);
    return (match?.[1] as ApprovalStatus) || null;
  } catch {
    return null;
  }
}

async function writeYamlStatus(filePath: string, status: ApprovalStatus): Promise<void> {
  const raw = await fs.readFile(filePath, "utf8");
  if (/^status:\s*(PENDING_SME_APPROVAL|APPROVED|REJECTED)\s*$/m.test(raw)) {
    const updated = raw.replace(
      /^status:\s*(PENDING_SME_APPROVAL|APPROVED|REJECTED)\s*$/m,
      `status: ${status}`
    );
    await fs.writeFile(filePath, updated, "utf8");
    return;
  }
  await fs.writeFile(filePath, `status: ${status}\n${raw}`, "utf8");
}

async function readLog(): Promise<ApprovalRecord[]> {
  try {
    const raw = await fs.readFile(LOG_PATH, "utf8");
    const parsed = JSON.parse(raw) as { records?: ApprovalRecord[] };
    return parsed.records || [];
  } catch {
    return [];
  }
}

async function appendLog(record: ApprovalRecord): Promise<void> {
  const records = await readLog();
  records.unshift(record);
  await fs.mkdir(path.dirname(LOG_PATH), { recursive: true });
  await fs.writeFile(LOG_PATH, JSON.stringify({ records: records.slice(0, 500) }, null, 2), "utf8");
}

export async function listPendingArtifacts(): Promise<ApprovalArtifact[]> {
  const out: ApprovalArtifact[] = [];
  let entries: string[] = [];
  try {
    entries = await fs.readdir(DESIGN_ROOT);
  } catch {
    return out;
  }
  for (const flowId of entries) {
    if (!isValidFlowId(flowId)) continue;
    for (const artifact of ARTIFACTS) {
      const filePath = path.join(DESIGN_ROOT, flowId, artifact);
      const status = await readYamlStatus(filePath);
      if (status) {
        out.push({ flowId, artifact, status });
      }
    }
  }
  return out;
}

export async function transitionArtifact(input: {
  flowId: string;
  artifact: ApprovalArtifact["artifact"];
  action: "approve" | "reject";
  approver: string;
  note?: string;
}): Promise<ApprovalRecord> {
  if (!isValidFlowId(input.flowId)) {
    throw new Error(`invalid flowId: ${input.flowId}`);
  }
  if (!isValidArtifact(input.artifact)) {
    throw new Error(`invalid artifact: ${input.artifact}`);
  }
  if (!input.approver.trim()) {
    throw new Error("approver identity is required");
  }

  const filePath = path.join(DESIGN_ROOT, input.flowId, input.artifact);
  try {
    await fs.access(filePath);
  } catch {
    throw new Error(`artifact not found: ${input.artifact} for ${input.flowId}`);
  }

  const current = await readYamlStatus(filePath);
  if (!current) {
    throw new Error(`artifact missing status field: ${input.artifact}`);
  }

  const next: ApprovalStatus = input.action === "approve" ? "APPROVED" : "REJECTED";
  if (!isValidTransition(current, next)) {
    throw new Error(`invalid transition ${current} -> ${next}`);
  }

  await writeYamlStatus(filePath, next);
  const record: ApprovalRecord = {
    flowId: input.flowId,
    artifact: input.artifact,
    status: next,
    approver: input.approver.trim(),
    decidedAt: new Date().toISOString(),
    note: input.note?.trim() || undefined,
  };
  await appendLog(record);
  return record;
}

export async function isFlowApproved(flowId: string): Promise<boolean> {
  const tcPath = path.join(DESIGN_ROOT, flowId, "test-cases.yaml");
  const status = await readYamlStatus(tcPath);
  return status === "APPROVED";
}
