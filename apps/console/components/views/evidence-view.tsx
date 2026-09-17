"use client";

import { useMemo, useState } from "react";
import { EmptyState } from "@/components/ui/empty-state";
import { parseInsights } from "@/lib/parse-run-insights";
import type { AgentRun } from "@/lib/types";

const TABS = ["Screenshots", "DOM", "Network", "Console", "JSON", "Healing"] as const;

export function EvidenceView({ run }: { run: AgentRun | null }) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Screenshots");
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const insights = useMemo(() => parseInsights(run), [run]);
  const evidence = insights.evidence || [];

  if (!run) {
    return (
      <EmptyState title="No evidence selected" description="Run a QA test to capture screenshots and execution artifacts." />
    );
  }

  return (
    <div className="view-stack evidence-layout">
      <header className="view-header">
        <div>
          <h1>Evidence</h1>
          <p className="view-subtitle">
            {evidence.length} capture{evidence.length === 1 ? "" : "s"} · Run{" "}
            <span className="font-mono">{run.id.slice(0, 8).toUpperCase()}</span>
            {insights.flowIds?.[0] ? (
              <>
                {" "}
                · <span className="font-mono">{insights.flowIds[0]}</span>
              </>
            ) : null}
          </p>
        </div>
      </header>

      <div className="filter-row" role="tablist" aria-label="Evidence filters">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            className={tab === t ? "filter-chip filter-chip--active" : "filter-chip"}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Screenshots" && evidence.length ? (
        <>
          <div className="evidence-grid" role="list">
            {evidence.map((ev) => {
              const active = selectedPath === ev.path;
              return (
                <button
                  key={ev.path}
                  type="button"
                  role="listitem"
                  className={active ? "evidence-card evidence-card--active" : "evidence-card"}
                  onClick={() => setSelectedPath(ev.path)}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={`/api/evidence?path=${encodeURIComponent(ev.path)}`} alt={ev.label || "Screenshot"} />
                  <div className="evidence-card__body">
                    <span>{ev.label || ev.path.split("/").pop()}</span>
                    <span className="font-mono">{ev.dom_path || "screenshot"}</span>
                  </div>
                </button>
              );
            })}
          </div>

          <section className="panel evidence-preview" aria-label="Evidence preview">
            {selectedPath ? (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`/api/evidence?path=${encodeURIComponent(selectedPath)}`} alt="Evidence preview" />
                <pre className="font-mono text-muted">{selectedPath}</pre>
              </>
            ) : (
              <EmptyState title="Select a capture" description="Choose a screenshot to inspect it in full size." />
            )}
          </section>
        </>
      ) : (
        <section className="panel">
          <EmptyState
            title={`No ${tab.toLowerCase()} artifacts`}
            description="Evidence for this category will appear when captured during execution."
          />
        </section>
      )}
    </div>
  );
}
