"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bot,
  Download,
  FileText,
  Loader2,
  Radar,
  Sparkles,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge, Textarea } from "@/components/ui/input";
import { ReportPreview } from "@/components/report-preview";
import { BrowserRecorderPanel } from "@/components/browser-recorder";
import { ScoutBackground } from "@/components/scout-background";
import { CoveragePanel, RunHistoryPanel, SmeApprovalQueue } from "@/components/enterprise-panels";
import { DeliveryInbox, SettingsPanel } from "@/components/settings-panel";
import type { AgentRun } from "@/lib/types";

type AgentInsights = {
  executionMode?: string;
  capability?: string;
  confidence?: number;
  reasoning?: string;
  suiteTopic?: string;
  flowIds?: string[];
  supportingFlows?: string[];
  suiteIds?: string[];
  commands?: string[];
  discoverySuggestions?: string[];
  automationSuggestions?: string[];
  evidence?: { path: string; label?: string; dom_path?: string }[];
  findings?: { severity: string; code: string; message: string }[];
  executor?: string;
  classifier?: string;
};

function parseInsights(run: AgentRun | null): AgentInsights {
  if (!run?.report?.json) return {};
  const agent = run.report.json.agent as Record<string, unknown> | null | undefined;
  const local = (agent?.local as Record<string, unknown>) || {};
  const intent = (local.intent as Record<string, unknown>) || {};
  const suite = (local.suite_plan as Record<string, unknown>) || {};
  const discovery = (local.discovery as Record<string, unknown>) || {};
  const validation = (local.validation as Record<string, unknown>) || {};
  const execution = (local.execution as Record<string, unknown>) || {};
  const findings = Array.isArray(validation.findings)
    ? (validation.findings as { severity: string; code: string; message: string }[])
    : [];

  const evidence: AgentInsights["evidence"] = [];
  const observations = Array.isArray(execution.observations)
    ? (execution.observations as { meta?: { evidence?: AgentInsights["evidence"] } }[])
    : [];
  for (const obs of observations) {
    for (const ev of obs.meta?.evidence || []) {
      evidence.push(ev);
    }
  }

  const discoverySuggestions = Array.isArray(discovery.suggestions)
    ? discovery.suggestions.map(String)
    : [];
  const automationSuggestions = discoverySuggestions.filter(
    (s) => s.includes("automation") || s.includes("Playwright") || s.includes("Browser Recorder")
  );

  return {
    executionMode: String(intent.execution_mode || ""),
    capability: intent.capability ? String(intent.capability) : undefined,
    confidence: typeof intent.confidence === "number" ? intent.confidence : undefined,
    reasoning: intent.reasoning ? String(intent.reasoning) : undefined,
    suiteTopic: intent.suite_topic ? String(intent.suite_topic) : undefined,
    flowIds: Array.isArray(intent.flow_ids) ? intent.flow_ids.map(String) : [],
    supportingFlows: Array.isArray(intent.supporting_flow_ids)
      ? intent.supporting_flow_ids.map(String)
      : [],
    suiteIds: Array.isArray(suite.suite_ids) ? suite.suite_ids.map(String) : [],
    commands: Array.isArray(suite.commands) ? suite.commands.map(String) : [],
    discoverySuggestions,
    automationSuggestions,
    evidence: evidence.slice(0, 12),
    findings,
    executor: local.executor ? String(local.executor) : undefined,
    classifier: local.classifier ? String(local.classifier) : undefined,
  };
}

function clarityTone(confidence?: number) {
  if (confidence == null) return "neutral" as const;
  if (confidence >= 0.85) return "ok" as const;
  if (confidence >= 0.65) return "warn" as const;
  return "bad" as const;
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
  const [notifyChannels] = useState(["email", "whatsapp"]);

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
        body: JSON.stringify({ goal, type, channels: notifyChannels }),
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
    <div className="scout-shell">
      <ScoutBackground />

      <header className="scout-header">
        <div className="scout-brand">
          <div className="scout-logo">
            <Radar size={22} strokeWidth={2.2} />
          </div>
          <div>
            <p className="scout-company">
              <span className="scout-company-mark">&gt;&gt;</span>
              <span className="scout-company-dash">-</span>
            </p>
            <h1 className="scout-title">ScoutAI</h1>
            <p className="scout-subtitle">
              Enterprise QA orchestration · intent classification · Playwright evidence
            </p>
          </div>
        </div>
        <div className="scout-meta">
          <Badge tone="info">{String(health?.primary_ready_flows ?? 19)} READY flows</Badge>
          <Badge tone={health?.llm_enabled ? "ok" : "warn"}>
            {health?.llm_enabled ? "LLM classify on" : "Deterministic classify"}
          </Badge>
          <Badge tone="neutral">{String(health?.executor ?? "playwright")}</Badge>
        </div>
      </header>

      <section className="scout-hero">
        <p className="scout-hero-kicker">BUILD AGENTS THAT THINK LIKE HUMANS</p>
        <h2 className="scout-hero-title">
          Synthetically trained. Symbolically steered.
          <br />
          Deploy QA agents that adapt, act, and learn.
        </h2>
      </section>

      {error && <div className="scout-alert">{error}</div>}

      <main className="scout-grid">
        <div className="scout-main-col">
          <section className="scout-panel scout-command">
            <div className="scout-panel-head">
              <Sparkles size={18} />
              <span>Natural language command</span>
            </div>
            <Textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe what to test — morning sanity, SKU search, new banner on product page…"
              className="scout-prompt"
              disabled={busy}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && prompt.trim()) {
                  e.preventDefault();
                  runAgent(prompt, "adhoc");
                }
              }}
            />
            <div className="scout-actions">
              <Button disabled={busy || !prompt.trim()} onClick={() => runAgent(prompt, "adhoc")} className="scout-btn-emerald">
                {busy ? <Loader2 size={16} className="scout-spin" /> : <Bot size={16} />}
                Run ScoutAI
              </Button>
              <Button variant="secondary" disabled={busy} onClick={() => runAgent(`morning sanity check — ${prompt}`, "sanity")}>
                <Zap size={16} />
                Run 19 sanity suites
              </Button>
            </div>
            <p className="scout-hint">⌘/Ctrl + Enter · Reports route to your saved email & WhatsApp inbox</p>

            {reportReady && activeRun && (
              <div className="scout-report-block">
                <div className="scout-panel-head">
                  <FileText size={18} />
                  <span>Enterprise report</span>
                  <Badge tone={tone(activeRun.conclusion)}>{activeRun.conclusion || activeRun.status}</Badge>
                </div>
                <ReportPreview markdown={activeRun.report!.markdown} evidence={insights.evidence} />
                <div className="scout-export-row">
                  <span className="scout-export-label">
                    <Download size={14} /> Export
                  </span>
                  {(["md", "pdf", "docx"] as const).map((fmt) => (
                    <a key={fmt} href={`/api/export?runId=${activeRun.id}&format=${fmt}`} className="scout-export-link">
                      {fmt.toUpperCase()}
                    </a>
                  ))}
                </div>
              </div>
            )}
          </section>

          <BrowserRecorderPanel />
          <SmeApprovalQueue />
          <CoveragePanel />
          <RunHistoryPanel />
          <SettingsPanel />
          <DeliveryInbox />
        </div>

        <aside className="scout-panel scout-output">
          <div className="scout-panel-head">
            <Bot size={18} />
            <span>ScoutAI output</span>
            {activeRun && <Badge tone={tone(activeRun.conclusion)}>{activeRun.conclusion || activeRun.status}</Badge>}
          </div>

          {!activeRun ? (
            <div className="scout-empty">
              Run ScoutAI to see high-clarity intent classification, suite selection, evidence captures, and
              automation suggestions for new features.
            </div>
          ) : (
            <div className="scout-output-scroll">
              <OutputBlock title="Intent classification" badge={insights.executionMode}>
                {insights.suiteTopic && <p className="scout-topic">{insights.suiteTopic}</p>}
                {insights.reasoning && <p>{insights.reasoning}</p>}
                <ul>
                  {insights.capability && <li>Capability: {insights.capability}</li>}
                  {insights.confidence != null && (
                    <li>
                      Clarity:{" "}
                      <Badge tone={clarityTone(insights.confidence)}>
                        {insights.confidence >= 0.85 ? "HIGH" : insights.confidence >= 0.65 ? "MEDIUM" : "LOW"}{" "}
                        {Math.round(insights.confidence * 100)}%
                      </Badge>
                    </li>
                  )}
                  {insights.classifier && <li>Classifier: {insights.classifier}</li>}
                  {insights.flowIds?.length ? <li>Primary flows: {insights.flowIds.join(", ")}</li> : null}
                </ul>
              </OutputBlock>

              <OutputBlock title="Suite selection" badge={insights.executor}>
                {insights.suiteIds?.length ? <p>Suites: {insights.suiteIds.join(", ")}</p> : null}
                {insights.commands?.map((cmd) => (
                  <code key={cmd} className="scout-code">
                    {cmd}
                  </code>
                ))}
              </OutputBlock>

              {insights.evidence && insights.evidence.length > 0 && (
                <OutputBlock title="Evidence captures" badge={`${insights.evidence.length}`}>
                  <div className="scout-evidence-grid">
                    {insights.evidence.slice(0, 6).map((ev) => (
                      <figure key={ev.path} className="scout-evidence-card">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={`/api/evidence?path=${encodeURIComponent(ev.path)}`}
                          alt={ev.label || "capture"}
                        />
                        <figcaption>{ev.label || ev.path.split("/").pop()}</figcaption>
                      </figure>
                    ))}
                  </div>
                </OutputBlock>
              )}

              {insights.automationSuggestions && insights.automationSuggestions.length > 0 && (
                <OutputBlock title="Automation script suggestions" badge="new feature">
                  <ul>
                    {insights.automationSuggestions.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                </OutputBlock>
              )}

              {insights.discoverySuggestions && insights.discoverySuggestions.length > 0 && (
                <OutputBlock title="Discovery insights" badge="crawl">
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
                  <div key={t.id} className="scout-trace">
                    <span className="scout-trace-kind">{t.kind}</span>
                    <span>{t.message}</span>
                  </div>
                ))}
              </OutputBlock>

              {activeRun.channelsNotified?.length ? (
                <OutputBlock title="Report delivery" badge="sent">
                  <ul>
                    {activeRun.channelsNotified.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                </OutputBlock>
              ) : null}
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
    <div className="scout-out-block">
      <div className="scout-out-head">
        <span>{title}</span>
        {badge && <span className="scout-out-badge">{badge}</span>}
      </div>
      <div className="scout-out-body">{children}</div>
    </div>
  );
}
