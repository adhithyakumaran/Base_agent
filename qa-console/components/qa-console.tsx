"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  BookOpen,
  Clock,
  Download,
  History as HistoryIcon,
  Mail,
  MessageSquare,
  Play,
  Radio,
  Settings2,
  Sparkles,
  Upload,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge, Input, Textarea } from "@/components/ui/input";
import type {
  AgentRun,
  AppState,
  ChannelConfig,
  KnowledgePill,
  ModelOption,
  ScheduleConfig,
} from "@/lib/types";
import { formatTokens } from "@/lib/utils";

type StatePayload = AppState & {
  models: ModelOption[];
  prebuiltFlows: { id: string; label: string; goal: string }[];
};

const NAV = [
  { id: "run", label: "Automate", icon: Play },
  { id: "knowledge", label: "Knowledge dump", icon: BookOpen },
  { id: "schedule", label: "Daily sanity", icon: Clock },
  { id: "channels", label: "Report channels", icon: Mail },
  { id: "history", label: "History", icon: HistoryIcon },
  { id: "usage", label: "Usage", icon: Activity },
  { id: "settings", label: "Models", icon: Settings2 },
] as const;

type NavId = (typeof NAV)[number]["id"];

function conclusionTone(c?: string): "ok" | "bad" | "warn" | "info" | "neutral" {
  if (c === "PASS") return "ok";
  if (c === "FAIL") return "bad";
  if (c === "BLOCKED") return "warn";
  if (c === "UNKNOWN" || c === "INSUFFICIENT_EVIDENCE") return "info";
  return "neutral";
}

export function QaConsole() {
  const [tab, setTab] = useState<NavId>("run");
  const [data, setData] = useState<StatePayload | null>(null);
  const [goal, setGoal] = useState("sanity check endless aisle home and login");
  const [selectedPills, setSelectedPills] = useState<string[]>([]);
  const [notifyChannels, setNotifyChannels] = useState<string[]>(["email"]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Knowledge form
  const [pillTitle, setPillTitle] = useState("");
  const [pillFormat, setPillFormat] = useState<KnowledgePill["format"]>("text");
  const [pillContent, setPillContent] = useState("");

  const refresh = useCallback(async () => {
    const res = await fetch("/api/state", { cache: "no-store" });
    const json = (await res.json()) as StatePayload;
    setData(json);
    return json;
  }, []);

  useEffect(() => {
    refresh().catch((e) => setError(String(e)));
  }, [refresh]);

  // Poll active run traces lightly
  useEffect(() => {
    if (!activeRunId) return;
    const t = setInterval(() => {
      refresh().catch(() => undefined);
    }, 1500);
    return () => clearInterval(t);
  }, [activeRunId, refresh]);

  const activeRun: AgentRun | null = useMemo(() => {
    if (!data) return null;
    return data.runs.find((r) => r.id === activeRunId) || data.runs[0] || null;
  }, [data, activeRunId]);

  async function triggerRun(opts: {
    goal: string;
    type: AgentRun["type"];
    channels?: string[];
  }) {
    setBusy(true);
    setError(null);
    setTab("run");
    try {
      const res = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          goal: opts.goal,
          type: opts.type,
          knowledgeIds: selectedPills,
          channels: opts.channels ?? notifyChannels,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Run failed");
      setActiveRunId(json.run.id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function addKnowledge() {
    setBusy(true);
    try {
      const res = await fetch("/api/knowledge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: pillTitle || "Client dump",
          format: pillFormat,
          content: pillContent,
          tags: ["client"],
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Upload failed");
      setPillTitle("");
      setPillContent("");
      setSelectedPills((prev) => [json.pill.id, ...prev]);
      await refresh();
      setTab("run");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function saveSettings(patch: {
    schedule?: Partial<ScheduleConfig>;
    channels?: Partial<ChannelConfig>;
    selectedModel?: string;
  }) {
    setBusy(true);
    try {
      await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  if (!data) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-[var(--muted-foreground)]">
        Loading QA console…
      </div>
    );
  }

  return (
    <div className="qa-shell">
      <aside className="qa-nav">
        <div className="qa-brand">
          <div className="qa-mark" aria-hidden />
          <div>
            <div className="qa-brand-name">Apex QA</div>
            <div className="qa-brand-sub">Base Agent Console</div>
          </div>
        </div>
        <nav className="qa-nav-list">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = tab === item.id;
            return (
              <button
                key={item.id}
                className={`qa-nav-item ${active ? "active" : ""}`}
                onClick={() => setTab(item.id)}
              >
                <Icon size={16} />
                {item.label}
              </button>
            );
          })}
        </nav>
        <div className="qa-nav-foot">
          <div className="text-xs text-[var(--muted-foreground)]">Token usage</div>
          <div className="font-mono text-sm">
            {formatTokens(data.usageTotal.tokensIn + data.usageTotal.tokensOut)}
          </div>
          <div className="text-[11px] text-[var(--muted-foreground)]">{data.usageTotal.runs} runs</div>
        </div>
      </aside>

      <main className="qa-main">
        <header className="qa-top">
          <div>
            <h1 className="qa-title">
              {NAV.find((n) => n.id === tab)?.label}
            </h1>
            <p className="qa-desc">
              Deterministic-first automation · Sanity & ad-hoc · Live traces · Report delivery
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="info">Model: {data.selectedModel}</Badge>
            <Badge tone={data.schedule.enabled ? "ok" : "neutral"}>
              Daily {data.schedule.timeLocal} {data.schedule.timezone}
            </Badge>
            <Button
              size="sm"
              disabled={busy}
              onClick={() =>
                triggerRun({
                  goal: data.schedule.goal,
                  type: "scheduled",
                  channels: data.schedule.channels,
                })
              }
            >
              <Radio size={14} /> Run morning sanity now
            </Button>
          </div>
        </header>

        {error && <div className="qa-error">{error}</div>}

        <div className="qa-body">
          <section className="qa-content">
            {tab === "run" && (
              <div className="space-y-6">
                <div className="qa-panel">
                  <div className="qa-panel-h">
                    <Sparkles size={16} /> Prompt automation
                  </div>
                  <Textarea
                    value={goal}
                    onChange={(e) => setGoal(e.target.value)}
                    placeholder="Describe what to automate — e.g. sanity check find-price with sample SKU…"
                    className="min-h-[110px] font-[family-name:var(--font-geist-sans)]"
                  />
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      disabled={busy || !goal.trim()}
                      onClick={() => triggerRun({ goal, type: "adhoc" })}
                    >
                      <Play size={14} /> Run ad-hoc
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={busy}
                      onClick={() =>
                        triggerRun({
                          goal: goal.includes("sanity") ? goal : `sanity check ${goal}`,
                          type: "sanity",
                        })
                      }
                    >
                      Sanity check
                    </Button>
                    <Button
                      variant="outline"
                      disabled={busy}
                      onClick={() =>
                        triggerRun({ goal: "discover the application map", type: "discover" })
                      }
                    >
                      Discover map
                    </Button>
                  </div>
                </div>

                <div className="qa-panel">
                  <div className="qa-panel-h">Prebuilt flow CTAs</div>
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {data.prebuiltFlows.map((f) => (
                      <button
                        key={f.id}
                        className="qa-flow-btn"
                        disabled={busy}
                        onClick={() => triggerRun({ goal: f.goal, type: "flow" })}
                      >
                        <span className="font-medium">{f.label}</span>
                        <span className="text-[11px] text-[var(--muted-foreground)]">{f.id}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="qa-panel">
                  <div className="qa-panel-h">Attach knowledge pills</div>
                  {data.knowledge.length === 0 ? (
                    <p className="text-sm text-[var(--muted-foreground)]">
                      Dump specs, CSVs, JSON, or URLs in Knowledge dump — they become data pills before
                      runs.
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {data.knowledge.map((k) => {
                        const on = selectedPills.includes(k.id);
                        return (
                          <button
                            key={k.id}
                            className={`qa-pill ${on ? "on" : ""}`}
                            onClick={() =>
                              setSelectedPills((prev) =>
                                on ? prev.filter((id) => id !== k.id) : [...prev, k.id]
                              )
                            }
                          >
                            {k.title}
                            <span className="opacity-60">· {k.format}</span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>

                <div className="qa-panel">
                  <div className="qa-panel-h">Notify channels on report</div>
                  <div className="flex flex-wrap gap-3 text-sm">
                    {["email", "teams", "whatsapp", "slack"].map((c) => (
                      <label key={c} className="inline-flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={notifyChannels.includes(c)}
                          onChange={(e) =>
                            setNotifyChannels((prev) =>
                              e.target.checked ? [...prev, c] : prev.filter((x) => x !== c)
                            )
                          }
                        />
                        {c}
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {tab === "knowledge" && (
              <div className="space-y-6">
                <div className="qa-panel">
                  <div className="qa-panel-h">
                    <Upload size={16} /> Client knowledge dump
                  </div>
                  <p className="mb-3 text-sm text-[var(--muted-foreground)]">
                    Feed data in multiple formats. Before automation, the agent extracts each dump as a
                    data pill and uses it with KB — not KB-only.
                  </p>
                  <div className="grid gap-3">
                    <Input
                      placeholder="Title"
                      value={pillTitle}
                      onChange={(e) => setPillTitle(e.target.value)}
                    />
                    <select
                      className="h-9 rounded-md border border-[var(--border)] bg-transparent px-3 text-sm"
                      value={pillFormat}
                      onChange={(e) => setPillFormat(e.target.value as KnowledgePill["format"])}
                    >
                      <option value="text">Text / prompt notes</option>
                      <option value="markdown">Markdown</option>
                      <option value="json">JSON</option>
                      <option value="csv">CSV</option>
                      <option value="url">URL list</option>
                      <option value="pdf_note">PDF notes (paste)</option>
                    </select>
                    <Textarea
                      placeholder="Paste content, JSON, CSV rows, or URLs…"
                      value={pillContent}
                      onChange={(e) => setPillContent(e.target.value)}
                      className="min-h-[160px] font-mono text-xs"
                    />
                    <Button disabled={busy || !pillContent.trim()} onClick={addKnowledge}>
                      Extract as data pill
                    </Button>
                  </div>
                </div>
                <div className="space-y-2">
                  {data.knowledge.map((k) => (
                    <div key={k.id} className="qa-panel !p-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="font-medium">{k.title}</div>
                        <Badge>{k.format}</Badge>
                      </div>
                      <pre className="mt-2 max-h-28 overflow-auto text-[11px] text-[var(--muted-foreground)]">
                        {k.content.slice(0, 500)}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {tab === "schedule" && (
              <div className="qa-panel space-y-4">
                <div className="qa-panel-h">Daily morning sanity (client-set)</div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={data.schedule.enabled}
                    onChange={(e) => saveSettings({ schedule: { enabled: e.target.checked } })}
                  />
                  Enabled
                </label>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-xs text-[var(--muted-foreground)]">Time</label>
                    <Input
                      type="time"
                      value={data.schedule.timeLocal}
                      onChange={(e) =>
                        saveSettings({ schedule: { timeLocal: e.target.value } })
                      }
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-[var(--muted-foreground)]">Timezone</label>
                    <Input
                      value={data.schedule.timezone}
                      onChange={(e) =>
                        saveSettings({ schedule: { timezone: e.target.value } })
                      }
                    />
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-[var(--muted-foreground)]">Goal</label>
                  <Textarea
                    value={data.schedule.goal}
                    onChange={(e) => saveSettings({ schedule: { goal: e.target.value } })}
                  />
                </div>
                <p className="text-sm text-[var(--muted-foreground)]">
                  Azure Pipeline / OCI cron will fire at this time; reports go to configured channels
                  automatically.
                </p>
              </div>
            )}

            {tab === "channels" && (
              <div className="qa-panel space-y-4">
                <div className="qa-panel-h">
                  <MessageSquare size={16} /> Communication points
                </div>
                <div>
                  <label className="mb-1 block text-xs text-[var(--muted-foreground)]">
                    Email (comma-separated)
                  </label>
                  <Input
                    value={data.channels.email.join(", ")}
                    onChange={(e) =>
                      saveSettings({
                        channels: {
                          email: e.target.value
                            .split(",")
                            .map((x) => x.trim())
                            .filter(Boolean),
                        },
                      })
                    }
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-[var(--muted-foreground)]">
                    Microsoft Teams webhook
                  </label>
                  <Input
                    placeholder="https://…"
                    value={data.channels.teamsWebhook}
                    onChange={(e) => saveSettings({ channels: { teamsWebhook: e.target.value } })}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-[var(--muted-foreground)]">
                    WhatsApp destination
                  </label>
                  <Input
                    placeholder="+91…"
                    value={data.channels.whatsapp}
                    onChange={(e) => saveSettings({ channels: { whatsapp: e.target.value } })}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-[var(--muted-foreground)]">
                    Slack webhook
                  </label>
                  <Input
                    value={data.channels.slackWebhook}
                    onChange={(e) => saveSettings({ channels: { slackWebhook: e.target.value } })}
                  />
                </div>
              </div>
            )}

            {tab === "history" && (
              <div className="space-y-2">
                {data.history.map((h) => (
                  <div key={h.id} className="qa-hist">
                    <div className="font-mono text-[11px] text-[var(--muted-foreground)]">
                      {new Date(h.at).toLocaleString()}
                    </div>
                    <div className="text-sm font-medium">{h.action}</div>
                    <div className="text-xs text-[var(--muted-foreground)]">by {h.actor}</div>
                  </div>
                ))}
              </div>
            )}

            {tab === "usage" && (
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="qa-stat">
                  <div className="qa-stat-l">Tokens in</div>
                  <div className="qa-stat-v">{formatTokens(data.usageTotal.tokensIn)}</div>
                </div>
                <div className="qa-stat">
                  <div className="qa-stat-l">Tokens out</div>
                  <div className="qa-stat-v">{formatTokens(data.usageTotal.tokensOut)}</div>
                </div>
                <div className="qa-stat">
                  <div className="qa-stat-l">Runs</div>
                  <div className="qa-stat-v">{data.usageTotal.runs}</div>
                </div>
                <div className="qa-panel sm:col-span-3">
                  <div className="qa-panel-h">Per-run usage</div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead className="text-xs text-[var(--muted-foreground)]">
                        <tr>
                          <th className="py-2">Run</th>
                          <th>Model</th>
                          <th>LLM</th>
                          <th>In</th>
                          <th>Out</th>
                          <th>Tools</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.runs.map((r) => (
                          <tr key={r.id} className="border-t border-[var(--border)]">
                            <td className="py-2 font-mono text-xs">{r.id}</td>
                            <td>{r.model}</td>
                            <td>{r.usage.llmCalls}</td>
                            <td>{r.usage.tokensIn}</td>
                            <td>{r.usage.tokensOut}</td>
                            <td>{r.usage.toolCalls}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {tab === "settings" && (
              <div className="qa-panel space-y-3">
                <div className="qa-panel-h">LLM models (API gateway)</div>
                <p className="text-sm text-[var(--muted-foreground)]">
                  Enterprise posture: API-only via gateway (Azure OpenAI / OpenAI / Anthropic / OCI).
                  Crawl & sanity stay deterministic-first; LLM is consultant when enabled.
                </p>
                <div className="grid gap-2">
                  {data.models.map((m) => (
                    <button
                      key={m.id}
                      className={`qa-model ${data.selectedModel === m.id ? "on" : ""}`}
                      onClick={() => saveSettings({ selectedModel: m.id })}
                    >
                      <div className="font-medium">{m.label}</div>
                      <div className="text-xs text-[var(--muted-foreground)]">
                        {m.provider} · role {m.role}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </section>

          <aside className="qa-side">
            <div className="qa-side-h">
              <span>Live pipeline</span>
              {activeRun && (
                <Badge tone={activeRun.status === "running" ? "warn" : conclusionTone(activeRun.conclusion)}>
                  {activeRun.status}
                  {activeRun.conclusion ? ` · ${activeRun.conclusion}` : ""}
                </Badge>
              )}
            </div>
            {!activeRun ? (
              <p className="p-4 text-sm text-[var(--muted-foreground)]">
                Trigger a run to watch agent steps here — like a CI pipeline panel.
              </p>
            ) : (
              <>
                <div className="border-b border-[var(--border)] px-4 py-3 text-xs">
                  <div className="font-mono text-[var(--muted-foreground)]">{activeRun.id}</div>
                  <div className="mt-1 line-clamp-2 text-sm">{activeRun.goal}</div>
                </div>
                <div className="qa-traces">
                  {activeRun.traces.map((t) => (
                    <div key={t.id} className="qa-trace">
                      <div className="qa-trace-k">{t.kind}</div>
                      <div className="text-sm">{t.message}</div>
                      {t.detail && (
                        <pre className="mt-1 max-h-24 overflow-auto text-[10px] text-[var(--muted-foreground)]">
                          {t.detail.slice(0, 600)}
                        </pre>
                      )}
                      <div className="mt-1 font-mono text-[10px] text-[var(--muted-foreground)]">
                        {new Date(t.at).toLocaleTimeString()}
                      </div>
                    </div>
                  ))}
                </div>
                {activeRun.report && (
                  <div className="border-t border-[var(--border)] p-3">
                    <div className="mb-2 text-xs font-medium">Export report</div>
                    <div className="flex flex-wrap gap-2">
                      {(["json", "md", "csv", "txt"] as const).map((fmt) => (
                        <a
                          key={fmt}
                          className="inline-flex"
                          href={`/api/export?runId=${activeRun.id}&format=${fmt}`}
                        >
                          <Button size="sm" variant="outline">
                            <Download size={12} /> {fmt.toUpperCase()}
                          </Button>
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            <div className="border-t border-[var(--border)] p-3">
              <div className="mb-2 text-xs font-medium">Recent runs</div>
              <div className="space-y-1">
                {data.runs.slice(0, 8).map((r) => (
                  <button
                    key={r.id}
                    className={`qa-run-row ${activeRun?.id === r.id ? "on" : ""}`}
                    onClick={() => setActiveRunId(r.id)}
                  >
                    <span className="truncate">{r.type}</span>
                    <Badge tone={conclusionTone(r.conclusion)}>{r.conclusion || r.status}</Badge>
                  </button>
                ))}
              </div>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
