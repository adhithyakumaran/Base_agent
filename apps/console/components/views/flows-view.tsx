"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Play, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataTable, StatusCell } from "@/components/ui/data-table";
import { ErrorState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";

type FlowRow = {
  id: string;
  name: string;
  status: string;
  testCount: number;
  approvalStatus?: string;
  smeReady: boolean;
  executable: boolean;
};

type FlowDetail = {
  id: string;
  name: string;
  purpose: string;
  approvalStatus: string;
  kbStatus: string;
  testCases: { id: string; title: string; type: string; priority: string }[];
  coverage: { positive: number; negative: number; parameterized: number; edge: number };
  businessRules: string[];
  executionGate: { executable: boolean; message: string };
  artifacts: string[];
};

const FILTERS = [
  { id: "all", label: "All" },
  { id: "approved", label: "Approved" },
  { id: "sme_ready", label: "SME ready" },
  { id: "needs_review", label: "Needs review" },
] as const;

export function FlowsView({ onRunFlow }: { onRunFlow?: (goal: string) => void }) {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["id"]>("sme_ready");
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState<FlowRow[]>([]);
  const [totals, setTotals] = useState<{
    all?: number;
    approved: number;
    smeReady: number;
    executable?: number;
    pendingApproval?: number;
  } | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<FlowDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadFlows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/flows?filter=${filter}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`Unable to load flows (${res.status})`);
      const json = await res.json();
      setRows(json.flows || []);
      setTotals(json.totals || null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    loadFlows();
  }, [loadFlows]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    fetch(`/api/flows/${selectedId}`)
      .then((r) => r.json())
      .then((json) => setDetail(json.flow || null))
      .catch(() => setDetail(null));
  }, [selectedId]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (r) => r.id.toLowerCase().includes(q) || r.name.toLowerCase().includes(q)
    );
  }, [rows, search]);

  if (error && !rows.length) {
    return (
      <ErrorState
        title="Unable to load flows"
        description="The QA knowledge service did not respond."
        onRetry={loadFlows}
        details={error}
      />
    );
  }

  return (
    <div className="view-stack flows-layout">
      <header className="view-header">
        <div>
          <h1>Approved QA flows</h1>
          <p className="view-subtitle">
            {totals?.all ?? "—"} total · {totals?.smeReady ?? "—"} SME-ready · {totals?.approved ?? "—"} approved ·{" "}
            {totals?.executable ?? "—"} executable · {totals?.pendingApproval ?? "—"} awaiting approval
          </p>
        </div>
      </header>

      <section className="panel">
        <div className="toolbar">
          <div className="search-field">
            <Search size={16} aria-hidden />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search flows…"
              aria-label="Search flows"
            />
          </div>
          <div className="filter-row" role="tablist" aria-label="Flow filters">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                role="tab"
                aria-selected={filter === f.id}
                className={filter === f.id ? "filter-chip filter-chip--active" : "filter-chip"}
                onClick={() => setFilter(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <DataTable
          columns={[
            { key: "id", header: "Flow ID", mono: true, render: (r) => r.id },
            { key: "name", header: "Business purpose", render: (r) => r.name },
            { key: "testCount", header: "Tests", render: (r) => String(r.testCount) },
            {
              key: "status",
              header: "Status",
              render: (r) => <StatusCell status={r.approvalStatus || r.status} />,
            },
          ]}
          rows={filtered}
          loading={loading}
          selectedId={selectedId}
          onSelect={(row) => setSelectedId(row.id)}
          emptyTitle="No flows match this filter"
          emptyDescription="Adjust filters or search to find approved QA assets."
        />
      </section>

      {detail ? (
        <section className="panel flow-detail" aria-labelledby="flow-detail-title">
          <div className="flow-detail-head">
            <div>
              <h2 id="flow-detail-title" className="font-mono">
                {detail.id}
              </h2>
              <p>{detail.name}</p>
            </div>
            <div className="flow-detail-badges">
              <StatusBadge status={detail.approvalStatus} />
              <StatusBadge status={detail.kbStatus} />
              <StatusBadge status={detail.executionGate.executable ? "APPROVED" : "BLOCKED"} />
            </div>
          </div>
          <p className="flow-purpose">{detail.purpose || "Business flow registered in the QA knowledge base."}</p>
          <div className="command-actions">
            {onRunFlow ? (
              <Button onClick={() => onRunFlow(`Run flow ${detail.id}`)}>
                <Play size={16} />
                Run flow
              </Button>
            ) : null}
          </div>

          <div className="detail-grid">
            <div>
              <h3>Coverage</h3>
              <ul className="detail-list">
                <li>Positive {detail.coverage.positive}</li>
                <li>Negative {detail.coverage.negative}</li>
                <li>Parameterized {detail.coverage.parameterized}</li>
                <li>Edge {detail.coverage.edge}</li>
              </ul>
            </div>
            <div>
              <h3>Artifacts</h3>
              <ul className="detail-list">
                {detail.artifacts.map((a) => (
                  <li key={a} className="font-mono">
                    {a}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <h3>Test cases</h3>
          <DataTable
            columns={[
              { key: "id", header: "Test ID", mono: true, render: (r) => r.id },
              { key: "title", header: "Title", render: (r) => r.title },
              { key: "type", header: "Type", render: (r) => r.type },
              { key: "priority", header: "Priority", render: (r) => r.priority },
            ]}
            rows={detail.testCases}
            emptyTitle="No test cases published"
          />

          {detail.businessRules.length ? (
            <>
              <h3>Business rules</h3>
              <ul className="detail-list">
                {detail.businessRules.map((rule) => (
                  <li key={rule}>{rule}</li>
                ))}
              </ul>
            </>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
