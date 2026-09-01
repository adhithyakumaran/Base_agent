"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowUp,
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
  locked?: boolean;
};

const NAV = [
  { id: "run", label: "Command center", icon: Play },
  { id: "knowledge", label: "Context library", icon: BookOpen },
  { id: "schedule", label: "Morning patrol", icon: Clock },
  { id: "channels", label: "Alert routes", icon: Mail },
  { id: "history", label: "Activity history", icon: HistoryIcon },
  { id: "usage", label: "Token usage", icon: Activity },
  { id: "settings", label: "Model gateway", icon: Settings2 },
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
  const [goal, setGoal] = useState("health check endless aisle technical readiness");
  const [selectedPills, setSelectedPills] = useState<string[]>([]);
  const [notifyChannels, setNotifyChannels] = useState<string[]>(["email", "whatsapp"]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [pillTitle, setPillTitle] = useState("");
  const [pillFormat, setPillFormat] = useState<KnowledgePill["format"]>("text");
  const [pillContent, setPillContent] = useState("");

  const refresh = useCallback(async () => {
    const res = await fetch("/api/state", { cache: "no-store" });
    const json = (await res.json()) as StatePayload;
    const locked = json.runs?.some((r) => r.status === "running" || r.status === "queued");
    setData({ ...json, locked });
    return { ...json, locked };
  }, []);

  useEffect(() => {
    refresh().catch((e) => setError(String(e)));
  }, [refresh]);

  useEffect(() => {
    if (!activeRunId && !busy) return;
    const t = setInterval(() => {
      refresh().catch(() => undefined);
    }, 1200);
    return () => clearInterval(t);
  }, [activeRunId, busy, refresh]);

  const locked = Boolean(busy || data?.locked);
  const activeRun: AgentRun | null = useMemo(() => {
    if (!data) return null;
    return data.runs.find((r) => r.id === activeRunId) || data.runs[0] || null;
  }, [data, activeRunId]);

  async function triggerRun(opts: {
    goal: string;
    type: AgentRun["type"];
    channels?: string[];
  }) {
    if (locked) {
      setError("A command is already in progress. Wait for it to finish.");
      return;
    }
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
      if (res.status === 409) {
        setError(json.error || "Another command is running.");
        await refresh();
        return;
      }
      if (!res.ok) throw new Error(json.error || "Command failed");
      setActiveRunId(json.run.id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      await refresh();
    }
  }

  async function addKnowledge() {
    setBusy(true);
    try {
      const res = await fetch("/api/knowledge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: pillTitle || "Client context",
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
      <div className="flex min-h-screen items-center justify-center text-sm text-zinc-400">
        Booting command center…
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
            <div className="qa-brand-sub">Enterprise Agent Console</div>
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
          <div className="text-xs text-zinc-500">Tokens consumed</div>
          <div className="font-mono text-sm text-zinc-100">
            {formatTokens(data.usageTotal.tokensIn + data.usageTotal.tokensOut)}
          </div>
          <div className="text-[11px] text-zinc-500">{data.usageTotal.runs} missions</div>
        </div>
      </aside>

      <main className="qa-main">
        <header className="qa-top">
          <div>
            <h1 className="qa-title">{NAV.find((n) => n.id === tab)?.label}</h1>
            <p className="qa-desc">
              Deterministic-first QA · live traces · report delivery · no loop-until-success
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="info">Gateway: {data.selectedModel}</Badge>
            <Badge tone={data.schedule.enabled ? "ok" : "neutral"}>
              Patrol {data.schedule.timeLocal} {data.schedule.timezone}
            </Badge>
            <Button
              size="sm"
              disabled={locked}
              onClick={() =>
                triggerRun({
                  goal: data.schedule.goal,
                  type: "scheduled",
                  channels: data.schedule.channels,
                })
              }
            >
              <Radio size={14} /> Run morning patrol
            </Button>
          </div>
        </header>

        {locked && (
          <div className="qa-lock">
            Execution lock active — finish the current command before starting another.
          </div>
        )}
        {error && <div className="qa-error">{error}</div>}

        <div className="qa-body">
          <section className="qa-content">
            {tab === "run" && (
              <div className="space-y-6">
                <div className="qa-panel">
                  <div className="qa-panel-h">
                    <Sparkles size={16} /> Issue a command
                  </div>
                  <div className="qa-prompt-wrap">
                    <Textarea
                      value={goal}
                      onChange={(e) => setGoal(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && !locked && goal.trim()) {
                          e.preventDefault();
                          triggerRun({ goal, type: "adhoc" });
                        }
                      }}
                      placeholder="Example: health check endless aisle · replay flow find_price · component probe P6_SKU"
                      className="min-h-[120px]"
                      disabled={locked}
                    />
                    <button
                      className="qa-go"
                      title="Run command"
                      aria-label="Run command"
                      disabled={locked || !goal.trim()}
                      onClick={() => triggerRun({ goal, type: "adhoc" })}
                    >
                      <ArrowUp size={18} strokeWidth={2.5} />
                    </button>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      variant="secondary"
                      disabled={locked}
                      onClick={() =>
                        triggerRun({
                          goal: goal.includes("sanity") ? goal : `sanity check ${goal}`,
                          type: "sanity",
                        })
                      }
                    >
                      Quick sanity
                    </Button>
                    <Button
                      variant="outline"
                      disabled={locked}
                      onClick={() =>
                        triggerRun({ goal: "discover the application map", type: "discover" })
                      }
                    >
                      Map application
                    </Button>
                    <Button
                      variant="outline"
                      disabled={locked}
                      onClick={() =>
                        triggerRun({
                          goal: "health check endless aisle technical readiness",
                          type: "sanity",
                        })
                      }
                    >
                      Full health pack
                    </Button>
                  </div>
                  <p className="mt-2 text-[11px] text-zinc-500">⌘/Ctrl + Enter also launches the command.</p>
                </div>

                <div className="qa-panel">
                  <div className="qa-panel-h">Mission presets</div>
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {data.prebuiltFlows.map((f) => (
                      <button
                        key={f.id}
                        className="qa-flow-btn"
                        disabled={locked}
                        onClick={() => triggerRun({ goal: f.goal, type: "flow" })}
                      >
                        <span className="font-medium">{f.label}</span>
                        <span className="text-[11px] text-zinc-500">{f.id}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="qa-panel">
                  <div className="qa-panel-h">Attach context packets</div>
                  {data.knowledge.length === 0 ? (
                    <p className="text-sm text-zinc-500">
                      Add specs, tables, or URLs in Context library. Before each mission the agent
                      extracts them as structured packets (not KB-only).
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {data.knowledge.map((k) => {
                        const on = selectedPills.includes(k.id);
                        return (
                          <label key={k.id} className={`qa-pill ${on ? "on" : ""}`}>
                            <input
                              type="checkbox"
                              className="mr-1"
                              checked={on}
                              disabled={locked}
                              onChange={(e) =>
                                setSelectedPills((prev) =>
                                  e.target.checked
                                    ? [...prev.filter((id) => id !== k.id), k.id]
                                    : prev.filter((id) => id !== k.id)
                                )
                              }
                            />
                            {k.title}
                            <span className="opacity-60">· {k.format}</span>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>

                <div className="qa-panel">
                  <div className="qa-panel-h">Deliver report to</div>
                  <div className="flex flex-wrap gap-3 text-sm text-zinc-300">
                    {["email", "whatsapp", "teams", "slack"].map((c) => (
                      <label key={c} className="inline-flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={notifyChannels.includes(c)}
                          disabled={locked}
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
                  <p className="mt-2 text-[11px] text-zinc-500">
                    Test routes: {data.channels.email.join(", ")} · WhatsApp {data.channels.whatsapp}
                  </p>
                </div>
              </div>
            )}

            {tab === "knowledge" && (
              <div className="space-y-6">
                <div className="qa-panel">
                  <div className="qa-panel-h">
                    <Upload size={16} /> Ingest client context
                  </div>
                  <p className="mb-3 text-sm text-zinc-500">
                    Drop operational truth here — SOPs, SKU lists, URLs, JSON contracts. The agent
                    turns each upload into a context packet before automation starts.
                  </p>
                  <div className="grid gap-3">
                    <Input
                      placeholder="Packet title"
                      value={pillTitle}
                      onChange={(e) => setPillTitle(e.target.value)}
                    />
                    <select
                      className="h-9 rounded-md border border-zinc-800 bg-zinc-950 px-3 text-sm text-zinc-100"
                      value={pillFormat}
                      onChange={(e) => setPillFormat(e.target.value as KnowledgePill["format"])}
                    >
                      <option value="text">Plain notes</option>
                      <option value="markdown">Markdown brief</option>
                      <option value="json">JSON contract</option>
                      <option value="csv">CSV table</option>
                      <option value="url">URL list</option>
                      <option value="pdf_note">PDF excerpt (paste)</option>
                    </select>
                    <Textarea
                      placeholder="Paste content…"
                      value={pillContent}
                      onChange={(e) => setPillContent(e.target.value)}
                      className="min-h-[160px] font-mono text-xs"
                    />
                    <Button disabled={!pillContent.trim()} onClick={addKnowledge}>
                      Extract context packet
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
                      <pre className="mt-2 max-h-28 overflow-auto text-[11px] text-zinc-500">
                        {k.content.slice(0, 500)}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {tab === "schedule" && (
              <div className="qa-panel space-y-4">
                <div className="qa-panel-h">Morning patrol schedule</div>
                <p className="text-sm text-zinc-500">
                  Azure Pipelines cron on OCI fires this mission daily and routes the report to your
                  alert channels.
                </p>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={data.schedule.enabled}
                    onChange={(e) => saveSettings({ schedule: { enabled: e.target.checked } })}
                  />
                  Armed
                </label>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-xs text-zinc-500">Local time</label>
                    <Input
                      type="time"
                      value={data.schedule.timeLocal}
                      onChange={(e) => saveSettings({ schedule: { timeLocal: e.target.value } })}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-zinc-500">Timezone</label>
                    <Input
                      value={data.schedule.timezone}
                      onChange={(e) => saveSettings({ schedule: { timezone: e.target.value } })}
                    />
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-zinc-500">Mission goal</label>
                  <Textarea
                    value={data.schedule.goal}
                    onChange={(e) => saveSettings({ schedule: { goal: e.target.value } })}
                  />
                </div>
              </div>
            )}

            {tab === "channels" && (
              <div className="qa-panel space-y-4">
                <div className="qa-panel-h">
                  <MessageSquare size={16} /> Alert routes
                </div>
                <p className="text-sm text-zinc-500">
                  Test destinations are prefilled. Swap to client production values later. Teams
                  needs a webhook URL from Azure/OCI secrets.
                </p>
                <div>
                  <label className="mb-1 block text-xs text-zinc-500">Email</label>
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
                  <label className="mb-1 block text-xs text-zinc-500">WhatsApp</label>
                  <Input
                    value={data.channels.whatsapp}
                    onChange={(e) => saveSettings({ channels: { whatsapp: e.target.value } })}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-zinc-500">Microsoft Teams webhook</label>
                  <Input
                    placeholder="https://outlook.office.com/webhook/… (from Azure/OCI secret)"
                    value={data.channels.teamsWebhook}
                    onChange={(e) => saveSettings({ channels: { teamsWebhook: e.target.value } })}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-zinc-500">Slack webhook</label>
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
                    <div className="font-mono text-[11px] text-zinc-500">
                      {new Date(h.at).toLocaleString()}
                    </div>
                    <div className="text-sm font-medium">{h.action}</div>
                    <div className="text-xs text-zinc-500">by {h.actor}</div>
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
                  <div className="qa-stat-l">Missions</div>
                  <div className="qa-stat-v">{data.usageTotal.runs}</div>
                </div>
                <div className="qa-panel sm:col-span-3">
                  <div className="qa-panel-h">Per-mission usage</div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead className="text-xs text-zinc-500">
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
                          <tr key={r.id} className="border-t border-zinc-800">
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
                <div className="qa-panel-h">Model gateway (API only)</div>
                <p className="text-sm text-zinc-500">
                  Pick the consultant model. Crawl, health, and sanity stay deterministic-first.
                  Default for demo: Deterministic only.
                </p>
                <div className="grid gap-2">
                  {data.models.map((m) => (
                    <button
                      key={m.id}
                      className={`qa-model ${data.selectedModel === m.id ? "on" : ""}`}
                      onClick={() => saveSettings({ selectedModel: m.id })}
                    >
                      <div className="font-medium">{m.label}</div>
                      <div className="text-xs text-zinc-500">
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
              <p className="p-4 text-sm text-zinc-500">
                Launch a command to watch every control-plane step here.
              </p>
            ) : (
              <>
                <div className="border-b border-zinc-800 px-4 py-3 text-xs">
                  <div className="font-mono text-zinc-500">{activeRun.id}</div>
                  <div className="mt-1 line-clamp-2 text-sm text-zinc-200">{activeRun.goal}</div>
                </div>
                <div className="qa-traces">
                  {activeRun.traces.map((t) => (
                    <div key={t.id} className="qa-trace">
                      <div className="qa-trace-k">{t.kind}</div>
                      <div className="text-sm text-zinc-200">{t.message}</div>
                      {t.detail && (
                        <pre className="mt-1 max-h-24 overflow-auto text-[10px] text-zinc-500">
                          {t.detail.slice(0, 600)}
                        </pre>
                      )}
                      <div className="mt-1 font-mono text-[10px] text-zinc-600">
                        {new Date(t.at).toLocaleTimeString()}
                      </div>
                    </div>
                  ))}
                </div>
                {activeRun.report && (
                  <div className="border-t border-zinc-800 p-3">
                    <div className="mb-2 text-xs font-medium text-zinc-300">Export evidence</div>
                    <div className="flex flex-wrap gap-2">
                      {(["json", "md", "csv", "txt"] as const).map((fmt) => (
                        <a key={fmt} className="inline-flex" href={`/api/export?runId=${activeRun.id}&format=${fmt}`}>
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

            <div className="border-t border-zinc-800 p-3">
              <div className="mb-2 text-xs font-medium text-zinc-300">Recent missions</div>
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
