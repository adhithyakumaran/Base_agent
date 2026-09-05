"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bot,
  Download,
  FileText,
  Loader2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge, Textarea } from "@/components/ui/input";
import type { AgentRun } from "@/lib/types";

type AgentInsights = {
  executionMode?: string;
  capability?: string;
  confidence?: number;
  reasoning?: string;
  flowIds?: string[];
  supportingFlows?: string[];
  suiteIds?: string[];
  commands?: string[];
  discoverySuggestions?: string[];
  findings?: { severity: string; code: string; message: string }[];
  executor?: string;
};

function parseInsights(run: AgentRun | null): AgentInsights {
  if (!run?.report?.json) return {};
  const agent = run.report.json.agent as Record<string, unknown> | null | undefined;
  const local = (agent?.local as Record<string, unknown>) || {};
  const intent = (local.intent as Record<string, unknown>) || {};
  const suite = (local.suite_plan as Record<string, unknown>) || {};
  const discovery = (local.discovery as Record<string, unknown>) || {};
  const validation = (local.validation as Record<string, unknown>) || {};
  const findings = Array.isArray(validation.findings)
    ? (validation.findings as { severity: string; code: string; message: string }[])
    : [];

  return {
    executionMode: String(intent.execution_mode || ""),
    capability: intent.capability ? String(intent.capability) : undefined,
    confidence: typeof intent.confidence === "number" ? intent.confidence : undefined,
    reasoning: intent.reasoning ? String(intent.reasoning) : undefined,
    flowIds: Array.isArray(intent.flow_ids) ? intent.flow_ids.map(String) : [],
    supportingFlows: Array.isArray(intent.supporting_flow_ids)
      ? intent.supporting_flow_ids.map(String)
      : [],
    suiteIds: Array.isArray(suite.suite_ids) ? suite.suite_ids.map(String) : [],
    commands: Array.isArray(suite.commands) ? suite.commands.map(String) : [],
    discoverySuggestions: Array.isArray(discovery.suggestions)
      ? discovery.suggestions.map(String)
      : [],
    findings,
    executor: local.executor ? String(local.executor) : undefined,
  };
}

function tone(conclusion?: string) {
  if (conclusion === "PASS") return "ok" as const;
  if (conclusion === "FAIL") return "bad" as const;
  if (conclusion === "NEEDS_REVIEW") return "warn" as const;
  return "neutral" as const;
}

export function QaConsole() {
  const [prompt, setPrompt] = useState(
    "Check login, home navigation, and product search on Endless Aisle UAT"
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeRun, setActiveRun] = useState<AgentRun | null>(null);
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);

  const insights = useMemo(() => parseInsights(activeRun), [activeRun]);

  const refreshHealth = useCallback(async () => {
    try {
      const base = process.env.NEXT_PUBLIC_AGENT_URL || "http://127.0.0.1:43124";
      const res = await fetch(`${base}/health`, { cache: "no-store" });
      if (res.ok) setHealth(await res.json());
    } catch {
      setHealth(null);
    }
  }, []);

  useEffect(() => {
    refreshHealth();
  }, [refreshHealth]);

  async function runAgent(goal: string, type: "adhoc" | "sanity") {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal, type, channels: [] }),
      });
      const json = await res.json();
      if (res.status === 409) {
        setError(json.error || "Another run is in progress.");
        return;
      }
      if (!res.ok) throw new Error(json.error || "Run failed");
      setActiveRun(json.run as AgentRun);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const reportReady = Boolean(activeRun?.report?.markdown);

  return (
    <div className="ea-shell">
      <header className="ea-header">
        <div className="ea-brand">
          <div className="ea-logo" aria-hidden>
            <ShieldCheck size={22} strokeWidth={2.2} />
          </div>
          <div>
            <h1 className="ea-title">Apex QA Agent</h1>
            <p className="ea-subtitle">Enterprise test orchestration · Groq intent · Playwright execution</p>
          </div>
        </div>
        <div className="ea-meta">
          <Badge tone="info">{String(health?.primary_ready_flows ?? 19)} READY flows</Badge>
          <Badge tone={health?.llm_enabled ? "ok" : "warn"}>
            {health?.llm_enabled ? "Groq LLM on" : "Deterministic classify"}
          </Badge>
          <Badge tone="neutral">{String(health?.executor ?? "playwright")}</Badge>
        </div>
      </header>

      {error && <div className="ea-alert">{error}</div>}

      <main className="ea-grid">
        <section className="ea-panel ea-command">
          <div className="ea-panel-head">
            <Sparkles size={18} />
            <span>Natural language command</span>
          </div>
          <Textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe what to test — e.g. morning sanity, check SKU search, new banner on product page…"
            className="ea-prompt"
            disabled={busy}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && prompt.trim()) {
                e.preventDefault();
                runAgent(prompt, "adhoc");
              }
            }}
          />
          <div className="ea-actions">
            <Button
              disabled={busy || !prompt.trim()}
              onClick={() => runAgent(prompt, "adhoc")}
              className="ea-btn-primary"
            >
              {busy ? <Loader2 size={16} className="ea-spin" /> : <Bot size={16} />}
              Run agent
            </Button>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() =>
                runAgent(
                  prompt.includes("sanity") ? prompt : `morning sanity check — ${prompt}`,
                  "sanity"
                )
              }
            >
              Generate sanity report
            </Button>
          </div>
          <p className="ea-hint">⌘/Ctrl + Enter runs the agent. Sanity uses all 19 approved Playwright suites.</p>

          {reportReady && activeRun && (
            <div className="ea-report-block">
              <div className="ea-panel-head">
                <FileText size={18} />
                <span>Combined report</span>
                <Badge tone={tone(activeRun.conclusion)}>{activeRun.conclusion || activeRun.status}</Badge>
              </div>
              <pre className="ea-report-preview">{activeRun.report!.markdown.slice(0, 3200)}</pre>
              <div className="ea-export-row">
                <span className="ea-export-label">
                  <Download size={14} /> Export
                </span>
                {(["md", "pdf", "docx"] as const).map((fmt) => (
                  <a
                    key={fmt}
                    href={`/api/export?runId=${activeRun.id}&format=${fmt}`}
                    className="ea-export-link"
                  >
                    {fmt.toUpperCase()}
                  </a>
                ))}
              </div>
            </div>
          )}
        </section>

        <aside className="ea-panel ea-output">
          <div className="ea-panel-head">
            <Bot size={18} />
            <span>Agent output</span>
            {activeRun && (
              <Badge tone={tone(activeRun.conclusion)}>{activeRun.conclusion || activeRun.status}</Badge>
            )}
          </div>

          {!activeRun ? (
            <div className="ea-empty">
              Run the agent to see intent classification, suite selection, discovery suggestions, and LLM
              analysis here.
            </div>
          ) : (
            <div className="ea-output-scroll">
              <OutputBlock title="Intent" badge={insights.executionMode}>
                {insights.reasoning && <p>{insights.reasoning}</p>}
                <ul>
                  {insights.capability && <li>Capability: {insights.capability}</li>}
                  {insights.confidence != null && (
                    <li>Confidence: {Math.round(insights.confidence * 100)}%</li>
                  )}
                  {insights.flowIds?.length ? (
                    <li>Primary flows: {insights.flowIds.join(", ")}</li>
                  ) : null}
                  {insights.supportingFlows?.length ? (
                    <li>Supporting (DRAFT): {insights.supportingFlows.join(", ")}</li>
                  ) : null}
                </ul>
              </OutputBlock>

              <OutputBlock title="Suite selection" badge={insights.executor}>
                {insights.suiteIds?.length ? (
                  <p>Suites: {insights.suiteIds.join(", ")}</p>
                ) : null}
                {insights.commands?.map((cmd) => (
                  <code key={cmd} className="ea-code">
                    {cmd}
                  </code>
                ))}
              </OutputBlock>

              {insights.discoverySuggestions && insights.discoverySuggestions.length > 0 && (
                <OutputBlock title="Discovery & new feature insights" badge="crawl">
                  <ul>
                    {insights.discoverySuggestions.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                </OutputBlock>
              )}

              {insights.findings && insights.findings.length > 0 && (
                <OutputBlock title="Findings" badge={`${insights.findings.length}`}>
                  <ul>
                    {insights.findings.map((f) => (
                      <li key={f.code}>
                        <strong>{f.severity}</strong> {f.message}
                      </li>
                    ))}
                  </ul>
                </OutputBlock>
              )}

              <OutputBlock title="Live trace">
                {activeRun.traces.map((t) => (
                  <div key={t.id} className="ea-trace">
                    <span className="ea-trace-kind">{t.kind}</span>
                    <span>{t.message}</span>
                  </div>
                ))}
              </OutputBlock>

              <OutputBlock title="Usage">
                <ul>
                  <li>LLM calls: {activeRun.usage.llmCalls}</li>
                  <li>Suite runs: {activeRun.usage.steps}</li>
                  <li>Tokens: {activeRun.usage.tokensIn} in / {activeRun.usage.tokensOut} out</li>
                </ul>
              </OutputBlock>
            </div>
          )}
        </aside>
      </main>
    </div>
  );
}

function OutputBlock({
  title,
  badge,
  children,
}: {
  title: string;
  badge?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="ea-out-block">
      <div className="ea-out-head">
        <span>{title}</span>
        {badge && <span className="ea-out-badge">{badge}</span>}
      </div>
      <div className="ea-out-body">{children}</div>
    </div>
  );
}
