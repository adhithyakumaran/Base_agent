"use client";

import { Loader2, SendHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { parseInsights } from "@/lib/parse-run-insights";
import type { OrchestratorStatus } from "@/lib/use-orchestrator";
import type { AgentRun } from "@/lib/types";

export function AskAgentView({
  orchestrator,
  busy,
  error,
  prompt,
  setPrompt,
  onRun,
  activeRun,
  onViewRun,
}: {
  orchestrator: OrchestratorStatus | null;
  busy: boolean;
  error: string | null;
  prompt: string;
  setPrompt: (value: string) => void;
  onRun: (goal: string, type: "adhoc" | "sanity") => void;
  activeRun: AgentRun | null;
  onViewRun?: () => void;
}) {
  const insights = parseInsights(activeRun);
  const env = orchestrator?.environment || "UAT";
  const connected = orchestrator?.connected;

  return (
    <div className="view-stack ask-page">
      <header className="ask-hero">
        <h1>Test your application with ScoutAI.</h1>
        <p className="view-subtitle">Run approved QA flows, inspect evidence, and verify results.</p>
      </header>

      <section className="ask-command-card" aria-labelledby="command-label">
        <label id="command-label" className="sr-only" htmlFor="scout-command">
          QA request
        </label>
        <div className="command-input-row">
          <Textarea
            id="scout-command"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Search SKU 552811DUDABA00, verify login, run morning sanity…"
            className="command-input"
            disabled={busy}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && prompt.trim()) {
                e.preventDefault();
                onRun(prompt, "adhoc");
              }
            }}
          />
          <Button
            className="command-submit"
            disabled={busy || !prompt.trim()}
            onClick={() => onRun(prompt, "adhoc")}
            aria-label="Submit QA request"
          >
            {busy ? <Loader2 size={18} className="status-badge-spin" /> : <SendHorizontal size={18} />}
          </Button>
        </div>

        <div className="command-actions">
          <Button disabled={busy || !prompt.trim()} onClick={() => onRun(prompt, "adhoc")}>
            Run controlled test
          </Button>
          <Button variant="secondary" disabled={busy} onClick={() => onRun(`morning sanity check — ${prompt}`, "sanity")}>
            Run sanity suites
          </Button>
        </div>
        <p className="hint">Ctrl+Enter to submit</p>
      </section>

      {error ? (
        <div className="inline-alert" role="alert">
          {error}
        </div>
      ) : null}

      <section className="panel readiness-card" aria-labelledby="readiness-heading">
        <h2 id="readiness-heading" className="section-label">
          Run readiness
        </h2>
        <div className="readiness-stats">
          <div className="readiness-stat">
            <strong>{orchestrator?.flowCounts?.executable ?? "—"}</strong>
            <span>executable</span>
          </div>
          <div className="readiness-stat">
            <strong>{orchestrator?.flowCounts?.smeReady ?? "—"}</strong>
            <span>SME-ready</span>
          </div>
          <div className="readiness-stat">
            <strong>{orchestrator?.flowCounts?.awaitingApproval ?? "—"}</strong>
            <span>awaiting approval</span>
          </div>
        </div>
        <p className="readiness-env">
          {connected ? "Connected" : "Offline"} to {env}
          {orchestrator?.agentMode ? ` · ${orchestrator.agentMode === "assisted" ? "Assisted" : "Controlled"} mode` : ""}
        </p>
      </section>

      {activeRun ? (
        <section className="panel latest-run-card" aria-labelledby="latest-run-heading">
          <h2 id="latest-run-heading" className="section-label">
            Latest run
          </h2>
          <p className="latest-run-card__goal">{activeRun.goal}</p>
          <div className="latest-run-meta">
            {insights.flowIds?.[0] ? (
              <span>
                Flow <span className="font-mono">{insights.flowIds[0]}</span>
              </span>
            ) : null}
            <span>
              Run <span className="font-mono">{activeRun.id.slice(0, 8).toUpperCase()}</span>
            </span>
            <span className="text-muted">{new Date(activeRun.updatedAt || activeRun.createdAt).toLocaleString()}</span>
          </div>
          <div className="latest-run-footer">
            <StatusBadge status={activeRun.conclusion || activeRun.status} />
            {onViewRun ? (
              <Button variant="secondary" size="sm" onClick={onViewRun}>
                View run
              </Button>
            ) : null}
          </div>
        </section>
      ) : (
        <EmptyState title="No active run" description="Start a QA run from above." />
      )}
    </div>
  );
}
