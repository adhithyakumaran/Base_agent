"use client";

import { useEffect, useState } from "react";
import { DataTable, StatusCell } from "@/components/ui/data-table";
import { EmptyState, ErrorState } from "@/components/ui/empty-state";
import type { AgentRun, HistoryItem } from "@/lib/types";
import { parseInsights } from "@/lib/parse-run-insights";

export function HistoryView() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch("/api/runs").then((r) => r.json()),
      fetch("/api/state").then((r) => r.json()),
    ])
      .then(([runsJson, stateJson]) => {
        setRuns(runsJson.runs || []);
        setHistory(stateJson.history || []);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (error && !runs.length) {
    return (
      <ErrorState
        title="Unable to load history"
        description="Run history and audit activity could not be loaded."
        details={error}
      />
    );
  }

  return (
    <div className="view-stack">
      <header className="view-header">
        <div>
          <h1>History</h1>
          <p className="view-subtitle">Operational run log and audit activity</p>
        </div>
      </header>

      <section className="panel">
        <div className="panel-head">
          <h2>Runs</h2>
        </div>
        <DataTable
          columns={[
            {
              key: "id",
              header: "Run ID",
              mono: true,
              render: (r) => r.id.slice(0, 5).toUpperCase(),
            },
            { key: "goal", header: "Goal", render: (r) => r.goal.slice(0, 80) },
            {
              key: "conclusion",
              header: "Result",
              render: (r) => <StatusCell status={r.conclusion || r.status} />,
            },
            {
              key: "flow",
              header: "Flow",
              mono: true,
              render: (r) => parseInsights(r).flowIds?.[0] || "—",
            },
            {
              key: "time",
              header: "Time",
              render: (r) => new Date(r.createdAt).toLocaleString(),
            },
          ]}
          rows={runs}
          loading={loading}
          emptyTitle="No runs yet"
          emptyDescription="Completed and in-progress runs will appear here."
        />
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>Audit activity</h2>
        </div>
        {history.length ? (
          <DataTable
            columns={[
              { key: "actor", header: "Actor", render: (r) => r.actor },
              { key: "action", header: "Action", render: (r) => r.action },
              { key: "at", header: "Timestamp", render: (r) => new Date(r.at).toLocaleString() },
              {
                key: "target",
                header: "Target",
                render: (r) => String(r.meta?.target || r.meta?.flowId || "—"),
              },
              {
                key: "result",
                header: "Result",
                render: (r) => String(r.meta?.result || r.meta?.status || "—"),
              },
            ]}
            rows={history}
            emptyTitle="No audit entries"
          />
        ) : (
          <EmptyState title="No audit entries" description="Approval and configuration events will appear here." />
        )}
      </section>
    </div>
  );
}
