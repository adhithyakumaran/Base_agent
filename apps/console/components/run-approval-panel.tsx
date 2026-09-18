"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import type { AgentRun } from "@/lib/types";
import { isRunResumable } from "@/lib/run-resume";

type AgentState = {
  ok?: boolean;
  status?: string;
  resumable?: boolean;
  approval_pause_kind?: string;
  approval_reason?: string;
  reason_code?: string;
  summary?: string;
  resume_token?: string;
  checkpoint?: string;
};

const PAUSE_LABELS: Record<string, string> = {
  execution_gate: "Execution gate — operator must approve continuing this run",
  generation: "Generated test artifacts require approval before execution",
  healing: "Healing proposal requires approval before retry",
};

function describePause(agent: AgentState | null, run: AgentRun): string {
  if (agent?.summary) return agent.summary;
  if (run.approvalReason) return run.approvalReason;
  if (agent?.approval_reason) return agent.approval_reason;
  if (run.reasonCode) return run.reasonCode;
  return "Human approval required before Playwright execution";
}

export function RunApprovalPanel({
  run,
  onRunUpdated,
}: {
  run: AgentRun;
  onRunUpdated: (run: AgentRun) => void;
}) {
  const [agent, setAgent] = useState<AgentState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const waiting = isRunResumable(run) || run.status === "resuming";
  const resuming = run.status === "resuming";

  const refreshAgent = useCallback(async () => {
    try {
      const res = await fetch(`/api/runs/${run.id}/agent`, { cache: "no-store" });
      if (!res.ok) return;
      setAgent((await res.json()) as AgentState);
    } catch {
      /* offline */
    }
  }, [run.id]);

  useEffect(() => {
    if (!waiting) return;
    refreshAgent();
    const t = window.setInterval(refreshAgent, 4000);
    return () => window.clearInterval(t);
  }, [waiting, refreshAgent]);

  async function approveAndResume() {
    if (busy || resuming) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/runs/${run.id}/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resume_token: agent?.resume_token || run.resumeToken,
          reason: "Operator approved run continuation (console)",
        }),
      });
      const json = await res.json();
      if (!res.ok) {
        setError(json.error || "Resume failed");
        return;
      }
      if (json.run) {
        onRunUpdated(json.run as AgentRun);
      }
      if (json.idempotent) {
        setError(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!waiting) return null;

  const pauseKind = agent?.approval_pause_kind || run.approvalPauseKind || "execution_gate";
  const pauseLabel = PAUSE_LABELS[pauseKind] || pauseKind;

  return (
    <section className="panel run-approval-panel" aria-label="Run approval required">
      <div className="panel-head">
        <h2>Approval required</h2>
        <StatusBadge status="WAITING_FOR_APPROVAL" />
      </div>
      <p className="run-approval-lead">{describePause(agent, run)}</p>
      <dl className="meta-grid">
        <div>
          <dt>Approval state</dt>
          <dd className="font-mono">{agent?.status || run.conclusion || "WAITING_FOR_APPROVAL"}</dd>
        </div>
        <div>
          <dt>Pause kind</dt>
          <dd className="font-mono">{pauseKind}</dd>
        </div>
        <div>
          <dt>Reason code</dt>
          <dd className="font-mono">{agent?.reason_code || run.reasonCode || "—"}</dd>
        </div>
        <div>
          <dt>Checkpoint</dt>
          <dd className="font-mono">{agent?.checkpoint || run.agentCheckpoint || "—"}</dd>
        </div>
      </dl>
      <p className="scout-muted">{pauseLabel}</p>
      <p className="scout-muted">
        This is run-level HITL approval (not flow artifact approval). Resume re-validates ExecutionGate and
        continues the same run ID.
      </p>
      {error ? <div className="inline-alert">{error}</div> : null}
      <div className="run-approval-actions">
        <Button type="button" disabled={busy || resuming} onClick={approveAndResume}>
          {resuming || busy ? (
            <>
              <Loader2 size={16} className="spin" aria-hidden /> Resuming…
            </>
          ) : (
            <>
              <ShieldCheck size={16} aria-hidden /> Approve &amp; Resume
            </>
          )}
        </Button>
      </div>
    </section>
  );
}
