import { promises as fs } from "fs";
import path from "path";
import { repoRoot } from "@/lib/repo-root";
import { atomicWriteJson, withFileLock } from "@/lib/fs-atomic";

export type ApprovalStatus = "PENDING_SME_APPROVAL" | "APPROVED" | "REJECTED";

export type ExecutionGateDecision = {
  flowId: string;
  executable: boolean;
  reasonCode: string;
  message: string;
  approvalStatus: ApprovalStatus | null;
  kbReady: boolean;
  inSmeReady: boolean;
  catalogAutomated: boolean;
  approvalStale: boolean;
};

export type ApprovalArtifact = {
  flowId: string;
  artifact: "test-cases.yaml" | "scenarios.yaml" | "suite.yaml";
  status: ApprovalStatus;
  approver?: string;
  decidedAt?: string;
  note?: string;
  executionGate?: ExecutionGateDecision;
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
const LOG_LOCK = path.join(REPO, "apps", "automation", "approval", ".locks", "approval-log.lock");
const KB_INDEX_PATH = path.join(REPO, "data", "discovery-kb", "flows", "index.yaml");
const CATALOG_PATH = path.join(REPO, "apps", "automation", "catalog", "index.yaml");
const CANONICAL_ARTIFACT = "test-cases.yaml";

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
  const updated = /^status:\s*(PENDING_SME_APPROVAL|APPROVED|REJECTED)\s*$/m.test(raw)
    ? raw.replace(
        /^status:\s*(PENDING_SME_APPROVAL|APPROVED|REJECTED)\s*$/m,
        `status: ${status}`
      )
    : `status: ${status}\n${raw}`;
  const tmp = `${filePath}.tmp.${process.pid}`;
  await fs.writeFile(tmp, updated, "utf8");
  await fs.rename(tmp, filePath);
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
  await withFileLock(LOG_LOCK, async () => {
    const records = await readLog();
    records.unshift(record);
    await fs.mkdir(path.dirname(LOG_PATH), { recursive: true });
    await atomicWriteJson(LOG_PATH, { records: records.slice(0, 500) });
  });
}

async function readSmeReady(): Promise<Set<string>> {
  try {
    const raw = await fs.readFile(KB_INDEX_PATH, "utf8");
    const ready: string[] = [];
    let inBlock = false;
    for (const line of raw.split("\n")) {
      if (/^sme_ready:\s*$/.test(line)) {
        inBlock = true;
        continue;
      }
      if (inBlock) {
        const match = line.match(/^\s+-\s+(BF-[A-Z0-9-]+)\s*$/);
        if (match) {
          ready.push(match[1]);
          continue;
        }
        if (line.trim() && !/^\s/.test(line)) {
          break;
        }
      }
    }
    return new Set(ready);
  } catch {
    return new Set();
  }
}

async function isCatalogAutomated(flowId: string): Promise<boolean> {
  try {
    const raw = await fs.readFile(CATALOG_PATH, "utf8");
    return new RegExp(`^-\\s+flow_id:\\s*${flowId}\\s*$`, "m").test(raw);
  } catch {
    return false;
  }
}

async function approvalIsStale(flowId: string, artifactPath: string): Promise<boolean> {
  const records = await readLog();
  const approved = records.filter(
    (r) =>
      r.flowId === flowId &&
      r.artifact === CANONICAL_ARTIFACT &&
      r.status === "APPROVED"
  );
  if (!approved.length) return true;
  const latest = approved.reduce((a, b) => (a.decidedAt >= b.decidedAt ? a : b));
  if (!latest.decidedAt) return true;
  const decidedTs = Date.parse(latest.decidedAt);
  if (Number.isNaN(decidedTs)) return true;
  const stat = await fs.stat(artifactPath);
  return stat.mtimeMs > decidedTs + 1000;
}

/** Canonical execution gate — mirrors Python ExecutionGate.evaluate(). */
export async function evaluateFlowExecution(flowId: string): Promise<ExecutionGateDecision> {
  const smeReady = await readSmeReady();
  const inSmeReady = smeReady.has(flowId);
  const catalogAutomated = await isCatalogAutomated(flowId);
  const kbReady = inSmeReady && catalogAutomated;
  const tcPath = path.join(DESIGN_ROOT, flowId, CANONICAL_ARTIFACT);
  const status = await readYamlStatus(tcPath);

  if (!status) {
    return {
      flowId,
      executable: false,
      reasonCode: "approval.missing",
      message: `${flowId}: missing ${CANONICAL_ARTIFACT} approval status`,
      approvalStatus: null,
      kbReady,
      inSmeReady,
      catalogAutomated,
      approvalStale: false,
    };
  }

  if (status === "PENDING_SME_APPROVAL") {
    return {
      flowId,
      executable: false,
      reasonCode: "approval.pending",
      message: `${flowId}: artifact approval is PENDING_SME_APPROVAL`,
      approvalStatus: status,
      kbReady,
      inSmeReady,
      catalogAutomated,
      approvalStale: false,
    };
  }

  if (status === "REJECTED") {
    return {
      flowId,
      executable: false,
      reasonCode: "approval.rejected",
      message: `${flowId}: artifact approval is REJECTED`,
      approvalStatus: status,
      kbReady,
      inSmeReady,
      catalogAutomated,
      approvalStale: false,
    };
  }

  const stale = await approvalIsStale(flowId, tcPath);
  if (stale) {
    return {
      flowId,
      executable: false,
      reasonCode: "approval.stale",
      message: `${flowId}: APPROVED artifact changed after last SME sign-off — re-approval required`,
      approvalStatus: status,
      kbReady,
      inSmeReady,
      catalogAutomated,
      approvalStale: true,
    };
  }

  if (!inSmeReady) {
    return {
      flowId,
      executable: false,
      reasonCode: "kb.not_sme_ready",
      message: `${flowId}: not in KB sme_ready list`,
      approvalStatus: status,
      kbReady: false,
      inSmeReady: false,
      catalogAutomated,
      approvalStale: false,
    };
  }

  if (!kbReady) {
    return {
      flowId,
      executable: false,
      reasonCode: "kb.not_in_catalog",
      message: `${flowId}: KB readiness failed (kb.not_in_catalog)`,
      approvalStatus: status,
      kbReady: false,
      inSmeReady,
      catalogAutomated,
      approvalStale: false,
    };
  }

  return {
    flowId,
    executable: true,
    reasonCode: "gate.executable",
    message: `${flowId}: APPROVED artifact + sme_ready + KB safety checks satisfied`,
    approvalStatus: status,
    kbReady: true,
    inSmeReady: true,
    catalogAutomated,
    approvalStale: false,
  };
}

export async function isFlowExecutable(flowId: string): Promise<boolean> {
  return (await evaluateFlowExecution(flowId)).executable;
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
        const item: ApprovalArtifact = { flowId, artifact, status };
        if (artifact === CANONICAL_ARTIFACT) {
          item.executionGate = await evaluateFlowExecution(flowId);
        }
        out.push(item);
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

  const artifactLock = path.join(
    REPO,
    "apps",
    "automation",
    "test-design",
    "flows",
    ".locks",
    `${input.flowId}-${input.artifact}.lock`
  );

  return withFileLock(artifactLock, async () => {
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
  });
}

export async function isFlowApproved(flowId: string): Promise<boolean> {
  const tcPath = path.join(DESIGN_ROOT, flowId, CANONICAL_ARTIFACT);
  const status = await readYamlStatus(tcPath);
  return status === "APPROVED";
}
