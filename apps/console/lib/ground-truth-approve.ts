import { promises as fs } from "fs";
import path from "path";
import { spawn } from "child_process";
import { extractAuthenticatedActor, isAuthorizedRequest, allowInsecureLocal } from "@/lib/api-auth-core";
import { applyOrchestratorResultToRun } from "@/lib/orchestrator-bridge";
import { parseInsights } from "@/lib/parse-run-insights";
import { repoRoot } from "@/lib/repo-root";
import { mapConclusionToRunStatus } from "@/lib/run-resume";
import {
  executionSucceededForGtReview,
  isGroundTruthReviewReason,
  type GroundTruthApprovalEligibility,
} from "@/lib/run-display";
import type { AgentRun } from "@/lib/types";
import { uid } from "@/lib/utils";

const REPO = repoRoot();
const GT_DIR = path.join(REPO, "data", "discovery-kb", "gt");
const GT_AUDIT_PATH = path.join(REPO, "data", "discovery-kb", "gt", "approval-audit.jsonl");

export type GroundTruthDoc = {
  id: string;
  status?: string;
  flow_id?: string;
  subject?: string;
  description?: string;
  business_contract?: string[];
  tags?: string[];
  approval?: Record<string, unknown>;
};

export function isSmeAuthorized(req: Request): boolean {
  if (!isAuthorizedRequest(req)) return false;
  const role = req.headers.get("x-scout-role")?.trim().toLowerCase();
  if (role === "sme" || role === "reviewer") return true;
  const actors = (process.env.SCOUT_SME_ACTORS || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (actors.length) {
    return actors.includes(extractAuthenticatedActor(req));
  }
  return allowInsecureLocal();
}

export async function readGroundTruthDoc(gtId: string): Promise<GroundTruthDoc | null> {
  const safe = gtId.replace(/[^a-zA-Z0-9_-]/g, "");
  if (safe !== gtId) return null;
  const filePath = path.join(GT_DIR, `${gtId}.json`);
  try {
    const doc = JSON.parse(await fs.readFile(filePath, "utf8")) as GroundTruthDoc;
    doc.id = doc.id || gtId;
    return doc;
  } catch {
    return null;
  }
}

function goalMatchesTags(goal: string, doc: GroundTruthDoc): boolean {
  const g = goal.toLowerCase();
  for (const tag of doc.tags || []) {
    const t = String(tag).toLowerCase();
    if (t.length >= 4 && g.includes(t)) return true;
  }
  if (doc.flow_id && g.includes(doc.flow_id.toLowerCase())) return true;
  if (doc.subject && g.includes(String(doc.subject).toLowerCase())) return true;
  return false;
}

export async function findPendingGroundTruthForRun(run: AgentRun): Promise<GroundTruthDoc | null> {
  const diag = run.decisionDiagnostics as { gt_id?: string } | undefined;
  if (diag?.gt_id) {
    const doc = await readGroundTruthDoc(String(diag.gt_id));
    if (doc && doc.status !== "approved") return doc;
  }
  const flowId = parseInsights(run).flowIds?.[0];
  let entries: string[] = [];
  try {
    entries = (await fs.readdir(GT_DIR)).filter((f) => f.endsWith(".json"));
  } catch {
    return null;
  }
  for (const file of entries) {
    const doc = await readGroundTruthDoc(path.basename(file, ".json"));
    if (!doc || doc.status === "approved") continue;
    if (flowId && doc.flow_id === flowId && goalMatchesTags(run.goal, doc)) return doc;
    if (!flowId && goalMatchesTags(run.goal, doc)) return doc;
  }
  return null;
}

export async function evaluateGroundTruthApprovalEligibility(run: AgentRun): Promise<GroundTruthApprovalEligibility> {
  if (run.conclusion !== "NEEDS_REVIEW") {
    return { eligible: false, reason: "run_not_needs_review" };
  }
  if (!isGroundTruthReviewReason(run.reasonCode, run.decisionDiagnostics)) {
    return { eligible: false, reason: "not_ground_truth_review" };
  }
  if (!executionSucceededForGtReview(run)) {
    return { eligible: false, reason: "execution_not_ok" };
  }
  const pending = await findPendingGroundTruthForRun(run);
  if (!pending) {
    return { eligible: false, reason: "no_pending_gt" };
  }
  return { eligible: true, gtId: pending.id };
}

export async function approveGroundTruthFile(gtId: string, approver: string): Promise<GroundTruthDoc> {
  const doc = await readGroundTruthDoc(gtId);
  if (!doc) throw new Error("GT file not found");
  if (doc.status === "approved") throw new Error("GT already approved");

  const approvedAt = new Date().toISOString();
  doc.status = "approved";
  (doc as Record<string, unknown>).approved_by = approver;
  (doc as Record<string, unknown>).approved_at = approvedAt;
  if (doc.approval && typeof doc.approval === "object") {
    doc.approval.state = "approved";
    doc.approval.approved_by = approver;
    doc.approval.approved_at = approvedAt;
  }

  const filePath = path.join(GT_DIR, `${gtId}.json`);
  await fs.writeFile(filePath, `${JSON.stringify(doc, null, 2)}\n`, "utf8");
  return doc;
}

export async function appendGroundTruthAudit(entry: Record<string, unknown>): Promise<void> {
  await fs.mkdir(GT_DIR, { recursive: true });
  await fs.appendFile(GT_AUDIT_PATH, `${JSON.stringify(entry)}\n`, "utf8");
}

async function spawnRevalidation(run: AgentRun): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const agent = run.report?.json?.agent as Record<string, unknown> | undefined;
    if (!agent?.local) {
      reject(new Error("run missing stored execution snapshot"));
      return;
    }
    const payload = {
      goal: run.goal,
      run_id: run.id,
      run_type: run.type,
      local: agent.local,
    };
    const pyBin = process.platform === "win32" ? "python" : "python3";
    const py = spawn(pyBin, ["-m", "qa_orchestrator.run_revalidation"], {
      cwd: REPO,
      env: {
        ...process.env,
        QA_DISCOVERY_ROOT: path.join(REPO, "data", "discovery-kb"),
        PYTHONPATH: [
          path.join(REPO, "services", "agent-runtime"),
          path.join(REPO, "services", "qa-orchestrator"),
          REPO,
        ].join(path.delimiter),
      },
    });
    let stdout = "";
    let stderr = "";
    py.stdin.write(JSON.stringify(payload));
    py.stdin.end();
    py.stdout.on("data", (d) => {
      stdout += d.toString();
    });
    py.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    py.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(stderr || `revalidation exit ${code}`));
        return;
      }
      try {
        const start = stdout.indexOf("{");
        resolve(JSON.parse(start >= 0 ? stdout.slice(start) : stdout) as Record<string, unknown>);
      } catch {
        reject(new Error("Failed to parse revalidation JSON"));
      }
    });
  });
}

export function applyRevalidationToRun(
  run: AgentRun,
  revalidation: Record<string, unknown>,
  approval: { gtId: string; approver: string; approvedAt: string }
): AgentRun {
  const validation = revalidation.validation as Record<string, unknown> | undefined;
  const conclusion = String(revalidation.conclusion || validation?.conclusion || run.conclusion);
  const reasonCode = String(revalidation.reason_code || validation?.reason_code || run.reasonCode);
  const diagnostics =
    (revalidation.decision_diagnostics as Record<string, unknown> | undefined) ||
    (validation?.decision_diagnostics as Record<string, unknown> | undefined) ||
    run.decisionDiagnostics;

  const mergedDiag = diagnostics ? { ...diagnostics } : {};
  const gt = (mergedDiag.ground_truth as Record<string, unknown> | undefined) || {};
  mergedDiag.ground_truth = {
    ...gt,
    approved_available: true,
    approved_by: approval.approver,
    approved_at: approval.approvedAt,
    gt_id: approval.gtId,
  };

  const agent = (run.report?.json?.agent as Record<string, unknown> | undefined) || {};
  const local = { ...((agent.local as Record<string, unknown>) || {}) };
  if (validation) local.validation = validation;

  const bridgePayload: Record<string, unknown> = {
    conclusion,
    reason_code: reasonCode,
    decision_diagnostics: mergedDiag,
    local: { ...local, validation_phase: validation?.phase ? `validation_phase_${String(validation.phase).toLowerCase()}` : local.validation_phase },
    agent: { ...agent, local, decision_diagnostics: mergedDiag },
    metadata: { decision_diagnostics: mergedDiag },
  };

  const traces = [...run.traces];
  traces.push({
    id: uid("tr"),
    at: new Date().toISOString(),
    kind: "decision",
    message: `Ground Truth approved (${approval.gtId}) — stored run revalidated → ${conclusion}`,
    detail: JSON.stringify({ gt_id: approval.gtId, approver: approval.approver, approved_at: approval.approvedAt }, null, 2),
  });

  const updated = applyOrchestratorResultToRun({ ...run }, bridgePayload, traces);
  updated.decisionDiagnostics = mergedDiag;
  updated.status = mapConclusionToRunStatus(conclusion);
  return updated;
}

export async function approveGroundTruthAndRevalidateRun(
  run: AgentRun,
  gtId: string,
  approver: string
): Promise<AgentRun> {
  const doc = await readGroundTruthDoc(gtId);
  if (!doc) throw new Error("GT not found");
  if (doc.status === "approved") throw new Error("GT already approved");

  const eligibility = await evaluateGroundTruthApprovalEligibility(run);
  if (!eligibility.eligible || eligibility.gtId !== gtId) {
    throw new Error(eligibility.reason || "run not eligible for GT approval");
  }

  const approved = await approveGroundTruthFile(gtId, approver);
  const approvedAt = String((approved as Record<string, unknown>).approved_at || new Date().toISOString());

  await appendGroundTruthAudit({
    action: "ground_truth.approve",
    gt_id: gtId,
    run_id: run.id,
    approver,
    approved_at: approvedAt,
    flow_id: approved.flow_id,
  });

  const revalidation = await spawnRevalidation(run);
  return applyRevalidationToRun(run, revalidation, { gtId, approver, approvedAt });
}
