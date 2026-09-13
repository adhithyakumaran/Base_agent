"use client";

import { Loader2, SendHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { greetingForHour, parseInsights } from "@/lib/parse-run-insights";
import type { OrchestratorStatus } from "@/lib/use-orchestrator";
import type { AgentRun } from "@/lib/types";

const SUGGESTIONS = [
  "Check login",
  "Search SKU ABC123",
  "Run morning sanity",
];

export function AskAgentView({
  orchestrator,
  busy,
  error,
  prompt,
  setPrompt,
  onRun,
  activeRun,
}: {
  orchestrator: OrchestratorStatus | null;
  busy: boolean;
  error: string | null;
  prompt: string;
  setPrompt: (value: string) => void;
  onRun: (goal: string, type: "adhoc" | "sanity") => void;
  activeRun: AgentRun | null;
}) {
  const insights = parseInsights(activeRun);

  return (
    <div className="view-stack">
      <header className="view-header">
        <div>
          <p className="view-kicker">{greetingForHour()}</p>
          <h1>What should ScoutAI test?</h1>
          <p className="view-subtitle">
            Controlled QA execution with approved business flows, evidence-backed validation, and human
            approval when required.
          </p>
        </div>
      </header>

      <section className="panel panel--raised command-panel" aria-labelledby="command-label">
        <div className="system-strip" role="status" aria-live="polite">
          <span>{orchestrator?.environment || "UAT"}</span>
          <span>{orchestrator?.connected ? "Orchestrator connected" : "Orchestrator offline"}</span>
          <span>{orchestrator?.approvedFlows ?? "—"} approved flows</span>
          <span>{orchestrator?.executor || "playwright"} executor</span>
          <span>{orchestrator?.safetyGate || "deterministic"} safety gate</span>
        </div>

        <label id="command-label" className="sr-only" htmlFor="scout-command">
          QA request
        </label>
        <div className="command-input-row">
          <Textarea
            id="scout-command"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Search SKU ABC123, verify login, run morning sanity…"
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

        <div className="command-meta">
          <div>
            <span className="meta-label">Agent mode</span>
            <strong>{orchestrator?.agentMode === "assisted" ? "Assisted" : "Controlled"}</strong>
          </div>
          <div>
            <span className="meta-label">Knowledge</span>
            <strong>{orchestrator?.smeReadyFlows ?? "—"} SME-ready flows</strong>
          </div>
          <div>
            <span className="meta-label">Execution</span>
            <strong>{orchestrator?.executor || "Playwright"}</strong>
          </div>
        </div>

        <div className="suggestion-row" aria-label="Suggested requests">
          {SUGGESTIONS.map((s) => (
            <button key={s} type="button" className="chip" onClick={() => setPrompt(s)} disabled={busy}>
              {s}
            </button>
          ))}
        </div>

        <div className="command-actions">
          <Button disabled={busy || !prompt.trim()} onClick={() => onRun(prompt, "adhoc")}>
            Run controlled test
          </Button>
          <Button variant="secondary" disabled={busy} onClick={() => onRun(`morning sanity check — ${prompt}`, "sanity")}>
            Run sanity suites
          </Button>
        </div>
        <p className="hint">Press Ctrl+Enter to submit. Reports route to configured delivery channels.</p>
      </section>

      {error ? (
        <div className="inline-alert" role="alert">
          {error}
        </div>
      ) : null}

      {activeRun ? (
        <section className="panel">
          <div className="panel-head">
            <h2>Latest run</h2>
            <StatusBadge status={activeRun.conclusion || activeRun.status} />
          </div>
          <dl className="meta-grid">
            <div>
              <dt>Run ID</dt>
              <dd className="font-mono">{activeRun.id.slice(0, 8).toUpperCase()}</dd>
            </div>
            <div>
              <dt>Goal</dt>
              <dd>{activeRun.goal}</dd>
            </div>
            {insights.flowIds?.[0] ? (
              <div>
                <dt>Flow</dt>
                <dd className="font-mono">{insights.flowIds[0]}</dd>
              </div>
            ) : null}
          </dl>
        </section>
      ) : (
        <EmptyState
          title="No active run"
          description="Start your first QA run using the command workspace above."
        />
      )}
    </div>
  );
}
