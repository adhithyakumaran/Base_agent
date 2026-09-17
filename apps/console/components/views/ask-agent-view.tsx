"use client";

import { Loader2, SendHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { parseInsights } from "@/lib/parse-run-insights";
import type { OrchestratorStatus } from "@/lib/use-orchestrator";
import type { AgentRun } from "@/lib/types";

const SUGGESTIONS: { label: string; text: string }[] = [
  { label: "Search a SKU", text: "Search SKU 552811DUDABA00" },
  { label: "Check login", text: "Check login on Endless Aisle UAT" },
  { label: "Verify cart flow", text: "Verify cart flow on UAT" },
  { label: "Run a sanity suite", text: "morning sanity check — Endless Aisle login and home modules" },
];

function buildStages(run: AgentRun | null) {
  const insights = parseInsights(run);
  const traces = run?.traces || [];
  const hasPlan = traces.some((t) => /plan|intent|classif/i.test(t.message));
  const hasExecute = traces.some((t) => /execut|playwright|suite/i.test(t.message));
  const hasObserve =
    (insights.evidence?.length || 0) > 0 || traces.some((t) => /evidence|observe|capture/i.test(t.message));
  const hasVerify =
    traces.some((t) => /verif|ground truth|validation/i.test(t.message)) || Boolean(run?.conclusion);
  const running = run?.status === "running" || run?.status === "resuming";

  const stateFor = (done: boolean, active: boolean): "done" | "active" | "waiting" => {
    if (done) return "done";
    if (active) return "active";
    return "waiting";
  };

  return [
    {
      label: "Plan",
      state: stateFor(hasPlan, running && !hasPlan),
      detail: insights.reasoning || "Intent classified · flow selected",
      time: run?.createdAt,
    },
    {
      label: "Execute",
      state: stateFor(hasExecute, running && hasPlan && !hasExecute),
      detail: insights.commands?.[0] || "Playwright execution",
      time: run?.updatedAt,
    },
    {
      label: "Observe",
      state: stateFor(hasObserve, running && hasExecute && !hasObserve),
      detail: hasObserve ? `${insights.evidence?.length || 0} evidence captures` : "Capturing evidence",
      time: run?.updatedAt,
    },
    {
      label: "Verify",
      state: stateFor(hasVerify, running && hasObserve && !hasVerify),
      detail: run?.conclusion ? `Result ${run.conclusion}` : "Ground-truth verification",
      time: run?.updatedAt,
    },
  ];
}

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
  const stages = buildStages(activeRun);

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
          <div className="timeline-horizontal">
            {stages.map((stage) => (
              <div key={stage.label} className={`timeline-step timeline-step--${stage.state}`}>
                <div className="timeline-step__label">{stage.label}</div>
                <div className="timeline-step__state">
                  {stage.state === "done" ? "Complete" : stage.state === "active" ? "In progress" : "Pending"}
                </div>
                <p className="text-sm text-muted">{stage.detail}</p>
                {stage.time ? (
                  <p className="font-mono text-xs text-muted">{new Date(stage.time).toLocaleString()}</p>
                ) : null}
              </div>
            ))}
          </div>
          <div className="latest-run-footer">
            <StatusBadge status={activeRun.conclusion || activeRun.status} />
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
