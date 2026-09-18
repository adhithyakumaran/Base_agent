"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { GroundTruthApprovalModal } from "@/components/ground-truth-approval-modal";
import { RunApprovalPanel } from "@/components/run-approval-panel";
import { RunReportExport } from "@/components/run-report-export";
import type { GroundTruthDoc } from "@/lib/ground-truth-approve";
import {
  buildRunTimelineStages,
  isRunTerminal,
  runDisplayBadge,
  runSummaryMetrics,
} from "@/lib/run-display";
import { parseInsights } from "@/lib/parse-run-insights";
import type { AgentRun } from "@/lib/types";

export function LiveRunsView({
  runId,
  initialRun,
  onRunUpdated,
}: {
  runId?: string | null;
  initialRun?: AgentRun | null;
  onRunUpdated?: (run: AgentRun) => void;
}) {
  const [run, setRun] = useState<AgentRun | null>(initialRun || null);
  const [error, setError] = useState<string | null>(null);
  const [gtEligible, setGtEligible] = useState(false);
  const [gtDoc, setGtDoc] = useState<GroundTruthDoc | null>(null);
  const [gtModalOpen, setGtModalOpen] = useState(false);
  const [gtBusy, setGtBusy] = useState(false);
  const [gtError, setGtError] = useState<string | null>(null);

  const insights = useMemo(() => parseInsights(run), [run]);
  const stages = useMemo(() => buildRunTimelineStages(run), [run]);
  const metrics = useMemo(() => runSummaryMetrics(run), [run]);

  const applyRun = useCallback(
    (next: AgentRun) => {
      setRun(next);
      onRunUpdated?.(next);
    },
    [onRunUpdated]
  );

  useEffect(() => {
    if (initialRun) setRun(initialRun);
  }, [initialRun]);

  useEffect(() => {
    const id = runId || run?.id;
    if (!id) return;
    let cancelled = false;
    let timer: number | undefined;

    async function poll(): Promise<boolean> {
      try {
        const res = await fetch(`/api/runs/${id}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`Run ${id} unavailable`);
        const json = await res.json();
        if (!cancelled) {
          const fresh = json.run as AgentRun;
          applyRun(fresh);
          setError(null);
          return isRunTerminal(fresh);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
      return false;
    }

    void poll().then((done) => {
      if (done || cancelled) return;
      timer = window.setInterval(async () => {
        const finished = await poll();
        if (finished && timer) {
          window.clearInterval(timer);
          timer = undefined;
        }
      }, 2500);
    });

    return () => {
      cancelled = true;
      if (timer) window.clearInterval(timer);
    };
  }, [runId, run?.id, applyRun]);

  useEffect(() => {
    const id = run?.id;
    if (!id || run.conclusion !== "NEEDS_REVIEW") {
      setGtEligible(false);
      setGtDoc(null);
      return;
    }
    let cancelled = false;
    fetch(`/api/runs/${id}/ground-truth/approve`, { cache: "no-store" })
      .then((r) => r.json())
      .then((json) => {
        if (cancelled) return;
        setGtEligible(Boolean(json.eligible));
        setGtDoc(json.gt || null);
      })
      .catch(() => {
        if (!cancelled) {
          setGtEligible(false);
          setGtDoc(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [run?.id, run?.conclusion, run?.decisionDiagnostics]);

  async function submitGtApproval() {
    if (!run || !gtDoc) return;
    setGtBusy(true);
    setGtError(null);
    try {
      const res = await fetch(`/api/runs/${run.id}/ground-truth/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gt_id: gtDoc.id }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Approval failed");
      applyRun(json.run as AgentRun);
      setGtModalOpen(false);
      setGtEligible(false);
    } catch (e) {
      setGtError(e instanceof Error ? e.message : String(e));
    } finally {
      setGtBusy(false);
    }
  }

  if (!run) {
    return (
      <EmptyState
        title="No runs yet"
        description="Start a QA run from Ask Agent to monitor execution here."
      />
    );
  }

  const gtMeta = run.decisionDiagnostics?.ground_truth as
    | { gt_id?: string; approved_by?: string; approved_at?: string }
    | undefined;
  const showGtApprovedBanner = run.conclusion === "PASS" && gtMeta?.approved_by;

  return (
    <div className="view-stack run-console">
      <header className="view-header run-detail-header">
        <div>
          <h1>{run.goal}</h1>
          <p className="view-subtitle font-mono">
            Primary: {insights.primaryExecutableFlow || insights.flowIds?.[0] || "Flow pending"}
            {insights.supportingFlows?.length
              ? ` · Supporting: ${insights.supportingFlows.join(", ")}`
              : ""}{" "}
            · {run.executionMode || "LIVE_DEMO"} · UAT
          </p>
          {insights.commands?.[0] ? (
            <p className="text-sm text-muted font-mono">Command: {insights.commands[0]}</p>
          ) : null}
        </div>
        <div className="run-detail-header__status">
          <StatusBadge status={runDisplayBadge(run)} />
          <RunReportExport run={run} />
        </div>
      </header>

      {error ? <div className="inline-alert">{error}</div> : null}

      {gtEligible && gtDoc ? (
        <section className="panel gt-approval-callout" aria-label="Ground Truth approval">
          <div>
            <h2 className="section-label">Ground Truth review</h2>
            <p className="text-sm text-muted">
              Execution completed. Approve Ground Truth <span className="font-mono">{gtDoc.id}</span> to revalidate
              this run without rerunning Playwright.
            </p>
          </div>
          <Button className="btn-black" onClick={() => setGtModalOpen(true)}>
            Approve Ground Truth
          </Button>
        </section>
      ) : null}

      {showGtApprovedBanner ? (
        <section className="panel panel--muted gt-approved-banner">
          <StatusBadge status="PASS" />
          <div>
            <p className="section-label">Ground Truth approved</p>
            <p className="font-mono text-sm">GT: {gtMeta?.gt_id || "—"}</p>
            <p className="text-sm">
              Approved by: <strong>{gtMeta?.approved_by}</strong>
            </p>
            <p className="text-sm text-muted">
              Approved at: {gtMeta?.approved_at ? new Date(String(gtMeta.approved_at)).toLocaleString() : "—"}
            </p>
            <ul className="gt-checklist gt-checklist--inline">
              <li>
                <span aria-hidden>✓</span> Execution successful
              </li>
              <li>
                <span aria-hidden>✓</span> Ground Truth approved
              </li>
              <li>
                <span aria-hidden>✓</span> Business validation complete
              </li>
            </ul>
          </div>
        </section>
      ) : null}

      <div className="run-summary-metrics" aria-label="Execution summary">
        <div className="run-metric">
          <strong>{metrics.playwrightProcesses}</strong>
          <span>Playwright process</span>
        </div>
        <div className="run-metric">
          <strong>{metrics.browsers}</strong>
          <span>Browser</span>
        </div>
        <div className="run-metric">
          <strong>{metrics.contexts}</strong>
          <span>Context</span>
        </div>
        <div className="run-metric">
          <strong>{metrics.logins}</strong>
          <span>Login</span>
        </div>
        <div className="run-metric">
          <strong>{metrics.selectedTests}</strong>
          <span>Selected test</span>
        </div>
        <div className="run-metric">
          <strong>{metrics.evidenceCaptures}</strong>
          <span>Evidence captures</span>
        </div>
      </div>

      <RunApprovalPanel run={run} onRunUpdated={applyRun} />

      <section aria-labelledby="timeline-heading">
        <h2 id="timeline-heading" className="section-label">
          Execution timeline
        </h2>
        <div className="timeline-horizontal">
          {stages.map((stage) => (
            <div key={stage.id} className={`timeline-step timeline-step--${stage.state}`}>
              <div className="timeline-step__label">{stage.label}</div>
              <div className="timeline-step__state">{stage.statusLabel}</div>
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

      {gtDoc ? (
        <GroundTruthApprovalModal
          open={gtModalOpen}
          run={run}
          gt={gtDoc}
          busy={gtBusy}
          error={gtError}
          onCancel={() => {
            setGtModalOpen(false);
            setGtError(null);
          }}
          onConfirm={() => void submitGtApproval()}
        />
      ) : null}
    </div>
  );
}
