import { parseInsights } from "@/lib/parse-run-insights";
import { isTerminalRunStatus } from "@/lib/run-resume";
import type { AgentRun } from "@/lib/types";

export type TimelineStageState = "done" | "active" | "waiting";

export type RunTimelineStage = {
  id: "plan" | "execute" | "observe" | "verify";
  label: string;
  state: TimelineStageState;
  /** Short label under the stage (Complete, In progress, Pending, or terminal verify outcome). */
  statusLabel: string;
  detail?: string;
  time?: string;
};

export type RunSummaryMetrics = {
  playwrightProcesses: number;
  browsers: number;
  contexts: number;
  logins: number;
  selectedTests: number;
  evidenceCaptures: number;
};

export function runDisplayBadge(run: AgentRun | null | undefined): string {
  if (!run) return "PENDING";
  if (run.status === "resuming") return "RUNNING";
  if (run.status === "waiting_approval" || run.conclusion === "WAITING_FOR_APPROVAL") {
    return "WAITING_FOR_APPROVAL";
  }
  if (run.status === "queued") return "PENDING";
  if (run.status === "running") return "RUNNING";
  if (run.conclusion) return run.conclusion;
  if (run.status === "needs_review") return "NEEDS_REVIEW";
  if (run.status === "failed") return "FAIL";
  if (run.status === "blocked") return "BLOCKED";
  if (run.status === "completed") return "PASS";
  return String(run.status).toUpperCase();
}

export function isRunTerminal(run: AgentRun | null | undefined): boolean {
  if (!run) return false;
  if (run.conclusion) {
    const c = run.conclusion.toUpperCase();
    if (["PASS", "FAIL", "NEEDS_REVIEW", "BLOCKED", "WAITING_FOR_APPROVAL"].includes(c)) {
      return c !== "WAITING_FOR_APPROVAL";
    }
  }
  return isTerminalRunStatus(run.status);
}

export function runSummaryMetrics(run: AgentRun | null | undefined): RunSummaryMetrics {
  const insights = parseInsights(run ?? null);
  const evidence = insights.evidence?.length || 0;
  const terminal = isRunTerminal(run);
  const executed =
    terminal ||
    run?.status === "running" ||
    run?.status === "resuming" ||
    (run?.traces || []).some((t) => /execut|playwright|suite/i.test(t.message));
  return {
    playwrightProcesses: executed ? 1 : 0,
    browsers: executed ? 1 : 0,
    contexts: executed ? 1 : 0,
    logins: executed ? 1 : 0,
    selectedTests: executed ? 1 : 0,
    evidenceCaptures: evidence,
  };
}

function verifyStatusLabel(run: AgentRun, verifyDone: boolean): string {
  if (!verifyDone) {
    if (run.status === "running" || run.status === "resuming") return "In progress";
    return "Pending";
  }
  const badge = runDisplayBadge(run);
  if (["PASS", "FAIL", "NEEDS_REVIEW", "BLOCKED", "WAITING_FOR_APPROVAL"].includes(badge)) {
    return badge === "WAITING_FOR_APPROVAL" ? "Waiting" : badge;
  }
  return "Complete";
}

export function buildRunTimelineStages(run: AgentRun | null): RunTimelineStage[] {
  if (!run) {
    return ["plan", "execute", "observe", "verify"].map((id) => ({
      id: id as RunTimelineStage["id"],
      label: id.charAt(0).toUpperCase() + id.slice(1),
      state: "waiting" as const,
      statusLabel: "Pending",
    }));
  }

  const insights = parseInsights(run);
  const traces = run.traces || [];
  const terminal = isRunTerminal(run);
  const waitingApproval =
    run.status === "waiting_approval" || run.conclusion === "WAITING_FOR_APPROVAL";
  const running = run.status === "running" || run.status === "resuming";
  const queued = run.status === "queued";

  const hasPlan =
    terminal ||
    traces.some((t) => /plan|intent|classif/i.test(t.message)) ||
    Boolean(insights.reasoning || insights.flowIds?.length);
  const hasExecute =
    terminal ||
    traces.some((t) => /execut|playwright|suite/i.test(t.message)) ||
    Boolean(insights.commands?.length);
  const hasObserve =
    terminal ||
    (insights.evidence?.length || 0) > 0 ||
    traces.some((t) => /evidence|observe|capture/i.test(t.message));
  const hasVerify =
    terminal ||
    Boolean(run.conclusion) ||
    traces.some((t) => /verif|ground truth|validation/i.test(t.message));

  const stateFor = (done: boolean, active: boolean): TimelineStageState => {
    if (done) return "done";
    if (active) return "active";
    return "waiting";
  };

  const planState = stateFor(hasPlan, running && !hasPlan && !queued);
  const executeState = waitingApproval
    ? "waiting"
    : stateFor(hasExecute, running && hasPlan && !hasExecute);
  const observeState = stateFor(hasObserve, running && hasExecute && !hasObserve);
  const verifyState = stateFor(hasVerify, running && hasObserve && !hasVerify);

  const stageStatus = (state: TimelineStageState) =>
    state === "done" ? "Complete" : state === "active" ? "In progress" : "Pending";

  const verifyDetail = (() => {
    const diag = run.decisionDiagnostics as
      | {
          reason_code?: string;
          message?: string;
          failed_checks?: string[];
          failed_condition?: string;
        }
      | undefined;
    if (diag?.reason_code && run.conclusion === "NEEDS_REVIEW") {
      const failed = (diag.failed_checks || []).join(", ") || diag.failed_condition || "see trace";
      return [`Reason: ${diag.reason_code}`, `Failed check: ${failed}`].filter(Boolean).join(" · ");
    }
    if (run.conclusion) return `Result ${run.conclusion}`;
    return "Ground-truth verification";
  })();

  return [
    {
      id: "plan",
      label: "Plan",
      state: planState,
      statusLabel: stageStatus(planState),
      detail: insights.reasoning || "Intent classified · flow selected",
      time: run.createdAt,
    },
    {
      id: "execute",
      label: "Execute",
      state: executeState,
      statusLabel: waitingApproval ? "Waiting" : stageStatus(executeState),
      detail: waitingApproval
        ? "Awaiting operator Approve & Resume"
        : insights.commands?.[0] || insights.executor || "Playwright execution",
      time: run.updatedAt,
    },
    {
      id: "observe",
      label: "Observe",
      state: observeState,
      statusLabel: stageStatus(observeState),
      detail: hasObserve
        ? `${insights.evidence?.length || 0} evidence captures`
        : "Capturing evidence",
      time: run.updatedAt,
    },
    {
      id: "verify",
      label: "Verify",
      state: verifyState,
      statusLabel: verifyStatusLabel(run, hasVerify),
      detail: verifyDetail,
      time: run.updatedAt,
    },
  ];
}

const GT_REVIEW_REASONS = new Set([
  "validator.pre_gt_honest",
  "validator.gt_pending",
  "validator.no_approved_gt",
]);

export type GroundTruthApprovalEligibility = {
  eligible: boolean;
  gtId?: string;
  reason?: string;
};

export function isGroundTruthReviewReason(reasonCode: string | undefined, diagnostics: Record<string, unknown> | undefined): boolean {
  const code = (reasonCode || "").trim();
  if (GT_REVIEW_REASONS.has(code)) return true;
  const failed = diagnostics?.failed_checks;
  if (Array.isArray(failed) && failed.map(String).includes("ground_truth")) return true;
  if (diagnostics?.failed_condition === "no_approved_ground_truth") return true;
  return false;
}

export function executionSucceededForGtReview(run: AgentRun): boolean {
  const diag = run.decisionDiagnostics as { evidence?: { execution_ok?: boolean } } | undefined;
  if (diag?.evidence?.execution_ok === false) return false;
  const agent = run.report?.json?.agent as Record<string, unknown> | undefined;
  const local = (agent?.local as Record<string, unknown>) || {};
  const execution = local.execution as { ok?: boolean; mode?: string } | undefined;
  if (execution && execution.mode !== "skipped" && execution.ok === false) return false;
  if (run.conclusion === "FAIL") return false;
  return true;
}
