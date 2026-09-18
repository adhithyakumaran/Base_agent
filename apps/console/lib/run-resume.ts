import type { AgentRun } from "@/lib/types";

/** Map orchestrator conclusion to console run status (run-level HITL). */
export function mapConclusionToRunStatus(conclusion: string | undefined): AgentRun["status"] {
  const c = (conclusion || "").toUpperCase();
  if (c === "WAITING_FOR_APPROVAL") return "waiting_approval";
  if (c === "FAIL") return "failed";
  if (c === "BLOCKED") return "blocked";
  if (c === "NEEDS_REVIEW") return "needs_review";
  if (c === "PASS" || c === "COMPLETED") return "completed";
  return "completed";
}

export function isRunResumable(run: AgentRun | null | undefined): boolean {
  if (!run) return false;
  return run.status === "waiting_approval" || run.conclusion === "WAITING_FOR_APPROVAL";
}

export function isTerminalRunStatus(status: AgentRun["status"]): boolean {
  return (
    status === "completed" ||
    status === "failed" ||
    status === "blocked" ||
    status === "needs_review"
  );
}

export type AgentPauseInfo = {
  status: string;
  resumable: boolean;
  approval_pause_kind?: string;
  approval_reason?: string;
  reason_code?: string;
  summary?: string;
  resume_token?: string;
  checkpoint?: string;
};

export function mergeAgentPauseIntoRun(run: AgentRun, agent: AgentPauseInfo): AgentRun {
  return {
    ...run,
    conclusion: agent.status === "WAITING_FOR_APPROVAL" ? "WAITING_FOR_APPROVAL" : run.conclusion,
    reasonCode: agent.reason_code || run.reasonCode,
    resumeToken: agent.resume_token || run.resumeToken,
    approvalPauseKind: agent.approval_pause_kind || run.approvalPauseKind,
    approvalReason: agent.approval_reason || agent.reason_code || run.approvalReason,
    agentCheckpoint: agent.checkpoint || run.agentCheckpoint,
  };
}
