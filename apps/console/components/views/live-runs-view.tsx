"use client";

import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { RunApprovalPanel } from "@/components/run-approval-panel";
import { RunReportExport } from "@/components/run-report-export";
import { parseInsights } from "@/lib/parse-run-insights";
import type { AgentRun } from "@/lib/types";

type Stage = {
  id: string;
  label: string;
  state: "done" | "active" | "waiting";
  detail?: string;
};

function buildStages(run: AgentRun | null): Stage[] {
  const insights = parseInsights(run);
  const traces = run?.traces || [];
  const hasPlan = traces.some((t) => /plan|intent|classif/i.test(t.message));
  const hasExecute = traces.some((t) => /execut|playwright|suite/i.test(t.message));
  const hasObserve = (insights.evidence?.length || 0) > 0 || traces.some((t) => /evidence|observe|capture/i.test(t.message));
  const hasVerify = traces.some((t) => /verif|ground truth|validation/i.test(t.message)) || run?.conclusion;

  const running = run?.status === "running" || run?.status === "resuming";
  const completed =
    run?.status === "completed" ||
    run?.status === "failed" ||
    run?.status === "needs_review" ||
    run?.status === "blocked";
  const waiting = run?.status === "waiting_approval" || run?.conclusion === "WAITING_FOR_APPROVAL";

  return [
    {
      id: "plan",
      label: "Plan",
      state: hasPlan || completed ? "done" : running ? "active" : "waiting",
      detail: insights.reasoning || "Intent classified · flow selected · execution gate",
    },
    {
      id: "execute",
      label: "Execute",
      state: waiting ? "waiting" : hasExecute ? "done" : running && hasPlan ? "active" : "waiting",
      detail: waiting
        ? "Awaiting operator Approve & Resume"
        : insights.commands?.[0] || insights.executor || "Playwright execution",
    },
    {
      id: "observe",
      label: "Observe",
      state: hasObserve ? "done" : running && hasExecute ? "active" : "waiting",
      detail: hasObserve ? `${insights.evidence?.length || 0} evidence captures` : "Capturing evidence",
    },
    {
      id: "verify",
      label: "Verify",
      state: hasVerify ? "done" : running && hasObserve ? "active" : "waiting",
      detail: (() => {
        const diag = run?.decisionDiagnostics as
          | { reason_code?: string; message?: string; failed_checks?: string[]; failed_condition?: string }
          | undefined;
        if (diag?.reason_code) {
          const failed = (diag.failed_checks || []).join(", ") || diag.failed_condition || "see trace";
          const msg = diag.message ? String(diag.message).slice(0, 120) : "";
          return [
            `NEEDS_REVIEW`,
            `Reason: ${diag.reason_code}`,
            `Failed check: ${failed}`,
            msg ? `Detail: ${msg}` : "",
          ]
            .filter(Boolean)
            .join(" · ");
        }
        return run?.conclusion ? `Result ${run.conclusion}` : "Waiting for ground-truth verification";
      })(),
    },
  ];
}

function runStatusBadge(run: AgentRun) {
  if (run.status === "resuming") return "RUNNING";
  if (run.status === "waiting_approval" || run.conclusion === "WAITING_FOR_APPROVAL") {
    return "WAITING_FOR_APPROVAL";
  }
  if (run.status === "running") return "RUNNING";
  return run.conclusion || run.status;
}

export function LiveRunsView({
  runId,
  initialRun,
}: {
  runId?: string | null;
  initialRun?: AgentRun | null;
}) {
  const [run, setRun] = useState<AgentRun | null>(initialRun || null);
  const [error, setError] = useState<string | null>(null);
  const insights = useMemo(() => parseInsights(run), [run]);
  const stages = useMemo(() => buildStages(run), [run]);

  useEffect(() => {
    if (initialRun) setRun(initialRun);
  }, [initialRun]);

  useEffect(() => {
    const id = runId || run?.id;
    if (!id) return;
    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch(`/api/runs/${id}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`Run ${id} unavailable`);
        const json = await res.json();
        if (!cancelled) {
          setRun(json.run);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }

    poll();
    const timer = window.setInterval(poll, 2500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [runId, run?.id]);

  if (!run) {
    return (
      <EmptyState
        title="No runs yet"
        description="Start a QA run from Ask Agent to monitor execution here."
      />
    );
  }

  return (
    <div className="view-stack run-console">
      <header className="view-header run-detail-header">
        <div>
          <h1>{run.goal}</h1>
          <p className="view-subtitle font-mono">
            {insights.flowIds?.[0] || "Flow pending"} · {run.executionMode || "LIVE_DEMO"} · UAT
          </p>
        </div>
        <div className="run-detail-header__status">
          <StatusBadge status={runStatusBadge(run)} />
          <RunReportExport run={run} />
        </div>
      </header>

      {error ? <div className="inline-alert">{error}</div> : null}

      <div className="run-summary-metrics" aria-label="Execution summary">
        <div className="run-metric">
          <strong>1</strong>
          <span>Playwright process</span>
        </div>
        <div className="run-metric">
          <strong>1</strong>
          <span>Browser</span>
        </div>
        <div className="run-metric">
          <strong>1</strong>
          <span>Context</span>
        </div>
        <div className="run-metric">
          <strong>1</strong>
          <span>Login</span>
        </div>
        <div className="run-metric">
          <strong>1</strong>
          <span>Selected test</span>
        </div>
        <div className="run-metric">
          <strong>{insights.evidence?.length || 0}</strong>
          <span>Evidence captures</span>
        </div>
      </div>

      <RunApprovalPanel run={run} onRunUpdated={setRun} />

      <section aria-labelledby="timeline-heading">
        <h2 id="timeline-heading" className="section-label">
          Execution timeline
        </h2>
        <div className="timeline-horizontal">
          {stages.map((stage) => (
            <div key={stage.id} className={`timeline-step timeline-step--${stage.state}`}>
              <div className="timeline-step__label">{stage.label}</div>
              <div className="timeline-step__state">
                {stage.state === "done" ? "Complete" : stage.state === "active" ? "In progress" : "Pending"}
              </div>
              <p className="text-sm text-muted">{stage.detail}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="panel" aria-labelledby="run-sections">
        <h2 id="run-sections" className="section-label">
          Execution details
        </h2>
        <p className="text-sm text-muted">
          Evidence · Diagnostics · Validation — use tabs below for deep inspection.
        </p>
      </section>

      {(insights.decision || run.decisionDiagnostics) ? (
        <details className="panel panel--muted">
          <summary>Diagnostics (collapsible)</summary>
          {insights.decision ? (
            <dl className="meta-grid">
              <div>
                <dt>Action</dt>
                <dd className="font-mono">{insights.decision.action || "—"}</dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd className="font-mono">{insights.decision.source || "—"}</dd>
              </div>
              <div>
                <dt>Confidence</dt>
                <dd>{insights.decision.confidence != null ? insights.decision.confidence.toFixed(2) : "—"}</dd>
              </div>
              <div>
                <dt>Flow</dt>
                <dd className="font-mono">{insights.flowIds?.[0] || "—"}</dd>
              </div>
            </dl>
          ) : null}
          {run.decisionDiagnostics ? (
            <pre className="font-mono text-sm">{JSON.stringify(run.decisionDiagnostics, null, 2)}</pre>
          ) : null}
        </details>
      ) : null}

      <details className="activity-log-panel">
        <summary>Activity log ({run.traces.length} events)</summary>
        <ul className="activity-log">
          {run.traces.slice(-12).map((trace) => (
            <li key={trace.id}>
              <span className="font-mono text-muted">{new Date(trace.at).toLocaleTimeString()}</span>
              <span className="font-mono">{trace.kind}</span>
              <span>{trace.message}</span>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
