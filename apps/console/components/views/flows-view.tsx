"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, Copy, Play, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  scenarios: { id: string; title: string; description: string }[];
  suites: { name: string; count: number; status: string }[];
  automation: {
    framework: string;
    runner: string;
    sampleTest: string;
    parameters: string;
  };
  overview: Record<string, string>;
  coverage: { positive: number; negative: number; parameterized: number; edge: number };
  businessRules: string[];
  executionGate: { executable: boolean; message: string };
};

const FILTERS = [
  { id: "all", label: "All" },
  { id: "approved", label: "Approved" },
  { id: "sme_ready", label: "SME Ready" },
  { id: "needs_review", label: "Needs Review" },
] as const;

const TABS = ["Overview", "Scenarios", "Test Cases", "Test Suites", "Automation"] as const;

const TERMINAL_LINES = [
  "✓ browser launched",
  "✓ authenticated",
  "✓ product search opened",
  "✓ SKU entered",
  "✓ search executed",
  "✓ evidence captured",
];

export function FlowsView({
  onRunFlow,
  initialFlowId,
}: {
  onRunFlow?: (goal: string) => void;
  initialFlowId?: string | null;
}) {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["id"]>("all");
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState<FlowRow[]>([]);
  const [totals, setTotals] = useState<{
    approved: number;
    smeReady: number;
    executable?: number;
    pendingApproval?: number;
  } | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(initialFlowId || null);
  const [detail, setDetail] = useState<FlowDetail | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showFullLog, setShowFullLog] = useState(false);

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
    if (initialFlowId) setSelectedId(initialFlowId);
  }, [initialFlowId]);

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
    return rows.filter((r) => r.id.toLowerCase().includes(q) || r.name.toLowerCase().includes(q));
  }, [rows, search]);

  async function copyRunner(cmd: string) {
    await navigator.clipboard.writeText(cmd);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

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
          <h1>Approved QA Flows</h1>
          <p className="view-subtitle">
            {totals?.executable ?? "—"} executable · {totals?.smeReady ?? "—"} SME-ready ·{" "}
            {totals?.pendingApproval ?? "—"} awaiting approval
          </p>
        </div>
      </header>

      <div className="toolbar">
        <div className="search-field">
          <Search size={16} aria-hidden />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search flows..."
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

      {loading && !rows.length ? <p className="text-muted">Loading flows…</p> : null}

      <div className="flow-card-grid" role="list">
        {filtered.map((row) => (
          <button
            key={row.id}
            type="button"
            role="listitem"
            className={selectedId === row.id ? "flow-card flow-card--selected" : "flow-card"}
            onClick={() => {
              setSelectedId(row.id);
              setTab("Overview");
            }}
          >
            <div className="flow-card__id">{row.id}</div>
            <div className="flow-card__title">{row.name}</div>
            <p className="text-sm">{row.testCount} test cases</p>
            <StatusBadge status={row.approvalStatus || row.status} />
            <div className="flow-card__meta">
              <span>{row.testCount} Tests</span>
              {row.smeReady ? <span>SME Ready</span> : null}
              {row.executable ? <span>Executable</span> : <span>Blocked</span>}
            </div>
          </button>
        ))}
      </div>

      {detail ? (
        <section className="flow-drawer" aria-labelledby="flow-detail-title">
          <div className="flow-detail-head flow-tab-panel">
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
            {onRunFlow ? (
              <Button className="btn-black" onClick={() => onRunFlow(`Run flow ${detail.id}`)}>
                <Play size={16} />
                Run flow
              </Button>
            ) : null}
          </div>

          <div className="flow-tabs" role="tablist">
            {TABS.map((t) => (
              <button
                key={t}
                type="button"
                role="tab"
                aria-selected={tab === t}
                className={tab === t ? "flow-tab flow-tab--active" : "flow-tab"}
                onClick={() => setTab(t)}
              >
                {t}
              </button>
            ))}
          </div>

          <div className="flow-tab-panel">
            {tab === "Overview" ? (
              <div className="info-card-grid">
                {Object.entries(detail.overview || {}).map(([key, value]) => (
                  <div key={key} className="info-card">
                    <h3>{key.replace(/([A-Z])/g, " $1").replace(/^./, (s) => s.toUpperCase())}</h3>
                    <p>{value}</p>
                  </div>
                ))}
              </div>
            ) : null}

            {tab === "Scenarios"
              ? detail.scenarios.map((sc, i) => (
                  <div key={sc.id} className="tc-card">
                    <h3>
                      Scenario {String(i + 1).padStart(2, "0")} · {sc.title}
                    </h3>
                    <p>{sc.description || "Primary business path."}</p>
                    <p>
                      <strong>Status:</strong> Ready
                    </p>
                  </div>
                ))
              : null}

            {tab === "Test Cases"
              ? detail.testCases.map((tc) => (
                  <div key={tc.id} className="tc-card">
                    <p className="font-mono">{tc.id}</p>
                    <h3>{tc.title}</h3>
                    <p>
                      <strong>Type:</strong> {tc.type} · <strong>Priority:</strong> {tc.priority}
                    </p>
                    <p>
                      <strong>Status:</strong> {detail.executionGate.executable ? "Executable" : "Blocked"}
                    </p>
                  </div>
                ))
              : null}

            {tab === "Test Suites"
              ? detail.suites.map((su) => (
                  <div key={su.name} className="tc-card">
                    <h3>{su.name}</h3>
                    <p>
                      {su.count} test{su.count === 1 ? "" : "s"} · {su.status}
                    </p>
                  </div>
                ))
              : null}

            {tab === "Automation" && detail.automation ? (
              <>
                <p>
                  <strong>Automation</strong> · {detail.automation.framework}
                </p>
                <p className="font-mono text-sm">Runner: {detail.automation.runner}</p>
                <p className="font-mono text-sm">Test: {detail.automation.sampleTest}</p>
                <p className="text-sm">Parameters: {detail.automation.parameters}</p>
                <div className="terminal-box">
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    className="terminal-box__copy"
                    onClick={() => copyRunner(detail.automation.runner)}
                  >
                    {copied ? <Check size={14} /> : <Copy size={14} />}
                    Copy
                  </Button>
                  <div className="terminal-line--cmd">$ {detail.automation.runner}</div>
                  <br />
                  {TERMINAL_LINES.slice(0, showFullLog ? undefined : 6).map((line) => (
                    <div key={line} className="terminal-line--ok">
                      {line}
                    </div>
                  ))}
                </div>
                <button type="button" className="text-sm link-button" onClick={() => setShowFullLog((v) => !v)}>
                  {showFullLog ? "Hide full execution log" : "View full execution log"}
                </button>
              </>
            ) : null}
          </div>
        </section>
      ) : null}
    </div>
  );
}
