"use client";

import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/components/ui/empty-state";
import { parseInsights } from "@/lib/parse-run-insights";
import type { AgentRun } from "@/lib/types";

const FILTERS = ["All", "Screenshots", "Navigation", "Test Start", "Test End", "Failed"] as const;

type EvidenceItem = {
  path: string;
  label?: string;
  dom_path?: string;
  runId: string;
  flowId?: string;
  at: string;
};

function classifyFilter(item: EvidenceItem, filter: (typeof FILTERS)[number]): boolean {
  if (filter === "All") return true;
  const label = (item.label || item.path).toLowerCase();
  if (filter === "Screenshots") return /\.png|screenshot/i.test(item.path);
  if (filter === "Navigation") return /nav|route|page/i.test(label);
  if (filter === "Test Start") return /start|begin|login/i.test(label);
  if (filter === "Test End") return /end|finish|complete/i.test(label);
  if (filter === "Failed") return /fail|error/i.test(label);
  return true;
}

export function EvidenceView({ run }: { run: AgentRun | null }) {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("All");
  const [items, setItems] = useState<EvidenceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [lightbox, setLightbox] = useState<EvidenceItem | null>(null);

  useEffect(() => {
    fetch("/api/runs")
      .then((r) => r.json())
      .then((json) => {
        const runs = (json.runs || []) as AgentRun[];
        const merged: EvidenceItem[] = [];
        for (const r of runs.slice(0, 20)) {
          const insights = parseInsights(r);
          for (const ev of insights.evidence || []) {
            merged.push({
              ...ev,
              runId: r.id,
              flowId: insights.flowIds?.[0],
              at: r.updatedAt || r.createdAt,
            });
          }
        }
        if (run) {
          const insights = parseInsights(run);
          for (const ev of insights.evidence || []) {
            if (!merged.some((m) => m.path === ev.path)) {
              merged.unshift({
                ...ev,
                runId: run.id,
                flowId: insights.flowIds?.[0],
                at: run.updatedAt || run.createdAt,
              });
            }
          }
        }
        setItems(merged);
      })
      .finally(() => setLoading(false));
  }, [run]);

  const filtered = useMemo(
    () => items.filter((item) => classifyFilter(item, filter)),
    [items, filter]
  );

  return (
    <div className="view-stack evidence-layout">
      <header className="view-header">
        <div>
          <h1>Evidence</h1>
          <p className="view-subtitle">Screenshots, execution artifacts and validation evidence.</p>
        </div>
      </header>

      <div className="filter-row" role="tablist" aria-label="Evidence filters">
        {FILTERS.map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={filter === t}
            className={filter === t ? "filter-chip filter-chip--active" : "filter-chip"}
            onClick={() => setFilter(t)}
          >
            {t}
          </button>
        ))}
      </div>

      {loading ? <p className="text-muted">Loading evidence…</p> : null}

      {!loading && !filtered.length ? (
        <EmptyState title="No evidence captures" description="Run a QA test to capture screenshots and artifacts." />
      ) : (
        <div className="evidence-grid" role="list">
          {filtered.map((ev) => (
            <button
              key={`${ev.runId}-${ev.path}`}
              type="button"
              role="listitem"
              className="evidence-card"
              onClick={() => setLightbox(ev)}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/api/evidence?path=${encodeURIComponent(ev.path)}`} alt={ev.label || "Evidence"} />
              <div className="evidence-card__body">
                <span>{ev.label || ev.path.split("/").pop()}</span>
                <span className="font-mono text-xs">{ev.flowId || "—"}</span>
                <span className="text-muted text-xs">{new Date(ev.at).toLocaleString()}</span>
                <span className="font-mono text-xs">run_{ev.runId.slice(4, 12)}</span>
              </div>
            </button>
          ))}
        </div>
      )}

      {lightbox ? (
        <div
          className="evidence-lightbox"
          role="dialog"
          aria-label="Evidence viewer"
          onClick={() => setLightbox(null)}
          onKeyDown={(e) => e.key === "Escape" && setLightbox(null)}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`/api/evidence?path=${encodeURIComponent(lightbox.path)}`}
            alt={lightbox.label || "Evidence full size"}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      ) : null}
    </div>
  );
}
