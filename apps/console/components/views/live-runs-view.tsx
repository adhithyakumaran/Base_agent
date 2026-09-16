"use client";

import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { RunApprovalPanel } from "@/components/run-approval-panel";
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
      detail: run?.conclusion ? `Result ${run.conclusion}` : "Waiting for ground-truth verification",
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
        description="Start your first QA run from Ask Agent to monitor execution here."
      />
    );
  }

  return (
    <div className="view-stack">
      <header className="view-header">
        <div>
          <StatusBadge status={runStatusBadge(run)} />
          <h1>{run.goal}</h1>
          <p className="view-subtitle font-mono">
            {insights.flowIds?.[0] || "Flow pending"} · Run {run.id.slice(0, 8).toUpperCase()}
          </p>
        </div>
      </header>

      {error ? <div className="inline-alert">{error}</div> : null}

      <RunApprovalPanel run={run} onRunUpdated={setRun} />

      <section className="panel timeline-panel" aria-label="Execution timeline">
        <ol className="run-timeline">
          {stages.map((stage) => (
            <li key={stage.id} className={`run-timeline__item run-timeline__item--${stage.state}`}>
              <div className="run-timeline__marker" aria-hidden />
              <div>
                <strong>{stage.label}</strong>
                <p>{stage.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {insights.decision ? (
        <section className="panel" aria-labelledby="decision-panel">
          <div className="panel-head">
            <h2 id="decision-panel">Decision</h2>
          </div>
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
            <div>
              <dt>Iteration</dt>
              <dd>{insights.decision.iteration ?? "—"}</dd>
            </div>
            <div>
              <dt>Recovery count</dt>
              <dd>{insights.decision.recoveryCount ?? 0}</dd>
            </div>
          </dl>
          {insights.decision.reason ? <p className="decision-reason">{insights.decision.reason}</p> : null}
        </section>
      ) : null}

      <section className="panel">
        <div className="panel-head">
          <h2>Activity log</h2>
        </div>
        <ul className="activity-log">
          {run.traces.slice(-12).map((trace) => (
            <li key={trace.id}>
              <span className="font-mono text-muted">{new Date(trace.at).toLocaleTimeString()}</span>
              <span className="font-mono">{trace.kind}</span>
              <span>{trace.message}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
