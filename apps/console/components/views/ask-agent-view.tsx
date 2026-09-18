"use client";

import { Loader2, SendHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { buildRunTimelineStages, runDisplayBadge } from "@/lib/run-display";
import type { OrchestratorStatus } from "@/lib/use-orchestrator";
import type { AgentRun } from "@/lib/types";

const SUGGESTIONS: { label: string; text: string }[] = [
  { label: "Search a SKU", text: "Search SKU 552811DUDABA00" },
  { label: "View a product", text: "View product using SKU 552811DUDABA00" },
  { label: "Check login", text: "Check login on Endless Aisle UAT" },
  { label: "Verify cart", text: "Verify cart flow on UAT" },
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
  const verifyBadge = activeRun ? runDisplayBadge(activeRun) : null;

  return (
    <div className="view-stack ask-page">
      <header className="ask-hero">
        <h1>Test your application with ScoutAI.</h1>
        <p className="view-subtitle">
          Describe what you want to verify in plain language. ScoutAI plans, executes, observes and verifies the
          result.
        </p>
      </header>

      <section className="command-workspace" aria-labelledby="command-workspace-title">
        <div className="command-workspace__accent" aria-hidden />
        <p id="command-workspace-title" className="command-workspace__eyebrow">
          Command
        </p>
        <label className="command-workspace__label" htmlFor="scout-command">
          What do you want ScoutAI to verify?
        </label>

        <div className="command-workspace__input-row">
          <Textarea
            id="scout-command"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Search SKU 552811DUDABA00"
            className="command-workspace__input"
            disabled={busy}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && prompt.trim()) {
                e.preventDefault();
                onRun(prompt, "adhoc");
              }
            }}
          />
          <Button
            className="command-workspace__send btn-black"
            disabled={busy || !prompt.trim()}
            onClick={() => onRun(prompt, "adhoc")}
            aria-label="Submit QA request"
          >
            {busy ? <Loader2 size={20} className="status-badge-spin" /> : <SendHorizontal size={20} />}
          </Button>
        </div>

        <div className="command-workspace__suggestions">
          <span className="command-workspace__suggestions-label">Try a test</span>
          <div className="command-workspace__chips">
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
        </div>

        <div className="command-workspace__actions">
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
          <span className="command-workspace__hint">Ctrl+Enter to submit</span>
        </div>
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
          <span>SME ready</span>
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

      <section className="latest-run-panel" aria-labelledby="latest-run-heading">
        <h2 id="latest-run-heading" className="section-label">
          Latest run
        </h2>
        {activeRun ? (
          <>
            <p className="latest-run-panel__goal">{activeRun.goal}</p>
            <div className="latest-run-timeline" role="list" aria-label="Run pipeline">
              {stages.map((stage) => (
                <div
                  key={stage.id}
                  role="listitem"
                  className={`latest-run-timeline__step latest-run-timeline__step--${stage.state}`}
                >
                  <span className="latest-run-timeline__name">{stage.label}</span>
                  <span className="latest-run-timeline__status">{stage.statusLabel}</span>
                </div>
              ))}
            </div>
            <div className="latest-run-panel__footer">
              <StatusBadge status={verifyBadge || "PENDING"} />
              {onViewRun ? (
                <Button variant="secondary" className="btn-outline-dark" size="sm" onClick={onViewRun}>
                  View run details
                </Button>
              ) : null}
            </div>
          </>
        ) : (
          <EmptyState title="No active run" description="Submit a command above to start a controlled test." />
        )}
      </section>
    </div>
  );
}
