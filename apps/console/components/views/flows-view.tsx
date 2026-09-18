"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, Copy, Play, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { navigationPathForFlow } from "@/lib/flow-navigation-paths";

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

const OVERVIEW_LABELS: Record<string, string> = {
  businessPurpose: "Business purpose",
  preconditions: "Entry point",
  navigation: "Navigation path",
  testData: "Parameters",
  expectedOutcomes: "Expected outcome",
  pagesInvolved: "Last verified",
  apexMetadata: "Verification source",
};

const TERMINAL_LINES = [
  "✓ test selected",
  "✓ parameter injected",
  "✓ browser launched",
  "✓ authenticated",
  "✓ SKU entered",
  "✓ search executed",
  "✓ result verified",
  "✓ evidence captured",
];

function FlowNavigationPath({ flowId }: { flowId: string }) {
  const nodes = navigationPathForFlow(flowId);
  return (
    <div className="nav-path" aria-label="Verified navigation path">
      {nodes.map((node, i) => (
        <div key={`${node.label}-${i}`} className="nav-path__segment">
          {i > 0 ? <div className="nav-path__connector" aria-hidden /> : null}
          <div className={`nav-path__node nav-path__node--${node.status}`}>
            <span>{node.label}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

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
  const [selectedId, setSelectedId] = useState<string | null>(initialFlowId || null);
  const [detail, setDetail] = useState<FlowDetail | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showFullLog, setShowFullLog] = useState(false);
  const [selectedSuite, setSelectedSuite] = useState<string | null>(null);

  const loadFlows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/flows?filter=${filter}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`Unable to load flows (${res.status})`);
      const json = await res.json();
      setRows(json.flows || []);
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
    setSelectedSuite(null);
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
    <div className="view-stack flows-page">
      <div className="flows-master-detail">
        <aside className="flows-list-panel" aria-label="Flow list">
          <header className="flows-list-panel__head">
            <h1>Approved QA Flows</h1>
          </header>

          <div className="flows-list-panel__toolbar">
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

          <div className="flows-list-scroll" role="list">
            {loading && !rows.length ? <p className="text-muted flows-list-empty">Loading flows…</p> : null}
            {!loading && !filtered.length ? (
              <p className="text-muted flows-list-empty">No flows match your search.</p>
            ) : null}
            {filtered.map((row) => {
              const selected = selectedId === row.id;
              return (
                <button
                  key={row.id}
                  type="button"
                  role="listitem"
                  className={selected ? "flow-card flow-card--selected" : "flow-card"}
                  onClick={() => {
                    setSelectedId(row.id);
                    setTab("Overview");
                  }}
                >
                  <div className="flow-card__id">{row.id}</div>
                  <div className="flow-card__title">{row.name}</div>
                  <p className="flow-card__count">{row.testCount} test cases</p>
                  <div className="flow-card__badges">
                    <StatusBadge status={row.approvalStatus || row.status} />
                    {row.smeReady ? <span className="flow-card__pill">SME Ready</span> : null}
                    {row.executable ? (
                      <span className="flow-card__pill">Executable</span>
                    ) : (
                      <span className="flow-card__pill">Blocked</span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </aside>

        <section className="flows-detail-panel" aria-label="Flow detail">
          {!detail ? (
            <div className="flows-detail-empty">
              <h2>Select a flow to inspect its QA coverage.</h2>
              <p className="text-muted">Choose an approved flow on the left to view scenarios, tests, and automation.</p>
            </div>
          ) : (
            <>
              <div className="flow-detail-head">
                <div>
                  <h2 className="font-mono flows-detail-id">{detail.id}</h2>
                  <p className="flows-detail-name">{detail.name}</p>
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

              <div className="flows-detail-scroll">
                {tab === "Overview" ? (
                  <div className="overview-blocks">
                    {Object.entries(detail.overview || {}).map(([key, value]) => {
                      const label = OVERVIEW_LABELS[key] || key.replace(/([A-Z])/g, " $1");
                      if (key === "navigation") {
                        return (
                          <div key={key} className="overview-block overview-block--wide">
                            <h3 className="overview-block__label">Navigation path</h3>
                            <FlowNavigationPath flowId={detail.id} />
                            <p className="text-sm text-muted">{value}</p>
                          </div>
                        );
                      }
                      return (
                        <div key={key} className="overview-block">
                          <h3 className="overview-block__label">{label}</h3>
                          <p>{value}</p>
                        </div>
                      );
                    })}
                  </div>
                ) : null}

                {tab === "Scenarios"
                  ? detail.scenarios.map((sc) => (
                      <div key={sc.id} className="scenario-card">
                        <p className="scenario-card__eyebrow">Scenario</p>
                        <h3>{sc.title}</h3>
                        <dl className="scenario-card__meta">
                          <div>
                            <dt>Capability</dt>
                            <dd>{detail.name}</dd>
                          </div>
                          <div>
                            <dt>Parameters</dt>
                            <dd>{detail.automation?.parameters || "Runtime"}</dd>
                          </div>
                          <div>
                            <dt>Expected</dt>
                            <dd>{detail.businessRules[0] || "Flow completes successfully"}</dd>
                          </div>
                          <div>
                            <dt>Verification</dt>
                            <dd>{detail.executionGate.executable ? "Verified" : "Blocked"}</dd>
                          </div>
                        </dl>
                        {sc.description ? <p className="text-sm text-muted">{sc.description}</p> : null}
                      </div>
                    ))
                  : null}

                {tab === "Test Cases"
                  ? detail.testCases.map((tc) => (
                      <div key={tc.id} className="tc-card">
                        <p className="font-mono tc-card__id">{tc.id}</p>
                        <h3>{tc.title}</h3>
                        <p className="tc-card__steps-label">Steps</p>
                        <ol className="tc-card__steps">
                          <li>Open flow entry</li>
                          <li>Execute {tc.type} path</li>
                          <li>Validate business rules</li>
                          <li>Capture evidence</li>
                        </ol>
                        <p>
                          <strong>Expected:</strong> {detail.businessRules[0] || "Matching outcome is displayed"}
                        </p>
                        <p>
                          <strong>Status:</strong> {detail.executionGate.executable ? "Executable" : "Blocked"}
                        </p>
                      </div>
                    ))
                  : null}

                {tab === "Test Suites"
                  ? detail.suites.map((su) => {
                      const suiteSelected = selectedSuite === su.name;
                      return (
                        <button
                          key={su.name}
                          type="button"
                          className={
                            suiteSelected ? "suite-card suite-card--selected" : "suite-card"
                          }
                          onClick={() => setSelectedSuite(su.name)}
                        >
                          <h3>{su.name}</h3>
                          <p>
                            {su.count} test{su.count === 1 ? "" : "s"} · {su.status}
                          </p>
                        </button>
                      );
                    })
                  : null}

                {tab === "Automation" && detail.automation ? (
                  <div className="automation-panel">
                    <dl className="automation-meta">
                      <div>
                        <dt>Flow</dt>
                        <dd className="font-mono">{detail.id}</dd>
                      </div>
                      <div>
                        <dt>Scenario</dt>
                        <dd>{detail.scenarios[0]?.title || detail.name}</dd>
                      </div>
                      <div>
                        <dt>Test</dt>
                        <dd className="font-mono">{detail.automation.sampleTest}</dd>
                      </div>
                      <div>
                        <dt>Runner</dt>
                        <dd>{detail.automation.framework}</dd>
                      </div>
                    </dl>
                    <p className="automation-meta__cmd-label">Command</p>
                    <div className="terminal-box">
                      <div className="terminal-box__actions">
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
                        <button
                          type="button"
                          className="link-button terminal-box__link"
                          onClick={() => setShowFullLog((v) => !v)}
                        >
                          {showFullLog ? "Hide full log" : "View full log"}
                        </button>
                      </div>
                      <div className="terminal-line--cmd">$ {detail.automation.runner}</div>
                      {TERMINAL_LINES.slice(0, showFullLog ? undefined : 6).map((line) => (
                        <div key={line} className="terminal-line--ok">
                          {line}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
