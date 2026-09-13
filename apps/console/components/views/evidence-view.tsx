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
      <EmptyState
        title="No evidence selected"
        description="Run a QA test to capture screenshots, DOM snapshots, and execution artifacts."
      />
    );
  }

  return (
    <div className="view-stack evidence-layout">
      <header className="view-header">
        <div>
          <h1>Evidence workspace</h1>
          <p className="view-subtitle">
            Run {run.id.slice(0, 8).toUpperCase()} → {insights.flowIds?.[0] || "Flow"} → Evidence
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

      <div className="evidence-split">
        <section className="panel evidence-list" aria-label="Evidence items">
          {tab === "Screenshots" && evidence.length ? (
            <ul className="evidence-items">
              {evidence.map((ev) => (
                <li key={ev.path}>
                  <button
                    type="button"
                    className={selectedPath === ev.path ? "evidence-item evidence-item--active" : "evidence-item"}
                    onClick={() => setSelectedPath(ev.path)}
                  >
                    <span className="font-mono">{ev.label || ev.path.split("/").pop()}</span>
                    <span className="text-muted">{ev.dom_path || "screenshot"}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title={`No ${tab.toLowerCase()} artifacts`}
              description="Evidence for this category will appear when captured during execution."
            />
          )}
        </section>

        <section className="panel evidence-preview" aria-label="Evidence preview">
          {selectedPath ? (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/api/evidence?path=${encodeURIComponent(selectedPath)}`} alt="Evidence preview" />
              <pre className="font-mono">{selectedPath}</pre>
            </>
          ) : (
            <EmptyState title="Select evidence" description="Choose an artifact from the list to preview it." />
          )}
        </section>
      </div>
    </div>
  );
}
