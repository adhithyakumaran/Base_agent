"use client";

import { Loader2, SendHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { buildRunTimelineStages, runDisplayBadge, runSummaryMetrics } from "@/lib/run-display";
import type { OrchestratorStatus } from "@/lib/use-orchestrator";
import type { AgentRun } from "@/lib/types";

const SUGGESTIONS: { label: string; text: string }[] = [
  { label: "Search a SKU", text: "Search SKU 552811DUDABA00" },
  { label: "Check login", text: "Check login on Endless Aisle UAT" },
  { label: "Verify cart flow", text: "Verify cart flow on UAT" },
  { label: "Run a sanity suite", text: "morning sanity check — Endless Aisle login and home modules" },
];

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
  const env = orchestrator?.environment || "UAT";
  const connected = orchestrator?.connected;
  const stages = buildRunTimelineStages(activeRun);
  const metrics = runSummaryMetrics(activeRun);

  return (
    <div className="view-stack ask-page">
      <header className="ask-hero">
        <h1>Test your application with ScoutAI.</h1>
        <p className="view-subtitle">
          Describe what you want to verify in plain language. ScoutAI plans, executes, observes and verifies the
          result.
        </p>
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
            placeholder="Search SKU 552811DUDABA00"
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
            className="command-submit btn-black"
            disabled={busy || !prompt.trim()}
            onClick={() => onRun(prompt, "adhoc")}
            aria-label="Submit QA request"
          >
            {busy ? <Loader2 size={18} className="status-badge-spin" /> : <SendHorizontal size={18} />}
          </Button>
        </div>

        <div className="suggestion-row">
          <span className="suggestion-label">Try a test</span>
          {SUGGESTIONS.map((s) => (
            <button
              key={s.label}
              type="button"
              className="suggestion-chip"
              disabled={busy}
              onClick={() => setPrompt(s.text)}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div className="command-actions-v2">
          <Button className="btn-black" disabled={busy || !prompt.trim()} onClick={() => onRun(prompt, "adhoc")}>
            Run controlled test
          </Button>
          <Button
            variant="secondary"
            className="btn-outline-dark"
            disabled={busy}
            onClick={() => onRun(`morning sanity check — ${prompt}`, "sanity")}
          >
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

      <section className="readiness-strip" aria-label="Execution readiness">
        <div className="readiness-strip__cell">
          <strong>{orchestrator?.flowCounts?.executable ?? "—"}</strong>
          <span>Executable</span>
        </div>
        <div className="readiness-strip__cell">
          <strong>{orchestrator?.flowCounts?.smeReady ?? "—"}</strong>
          <span>SME-ready</span>
        </div>
        <div className="readiness-strip__cell">
          <strong>{orchestrator?.flowCounts?.awaitingApproval ?? "—"}</strong>
          <span>Awaiting approval</span>
        </div>
        <div className="readiness-strip__cell">
          <strong>{env}</strong>
          <span>{connected ? "Connected" : "Offline"}</span>
        </div>
      </section>

      {activeRun ? (
        <section aria-labelledby="latest-run-heading">
          <h2 id="latest-run-heading" className="section-label">
            Latest run
          </h2>
          <p className="latest-run-card__goal">{activeRun.goal}</p>
          <div className="run-summary-metrics run-summary-metrics--compact" aria-label="Execution summary">
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
          <div className="timeline-horizontal">
            {stages.map((stage) => (
              <div key={stage.id} className={`timeline-step timeline-step--${stage.state}`}>
                <div className="timeline-step__label">{stage.label}</div>
                <div className="timeline-step__state">{stage.statusLabel}</div>
                <p className="text-sm text-muted">{stage.detail}</p>
                {stage.time ? (
                  <p className="font-mono text-xs text-muted">{new Date(stage.time).toLocaleString()}</p>
                ) : null}
              </div>
            ))}
          </div>
          <div className="latest-run-footer">
            <StatusBadge status={runDisplayBadge(activeRun)} />
            {onViewRun ? (
              <Button variant="secondary" className="btn-outline-dark" size="sm" onClick={onViewRun}>
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
