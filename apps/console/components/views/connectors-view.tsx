"use client";

import { useEffect, useState } from "react";
import {
  Clock,
  Mail,
  MessageCircle,
  Play,
  Save,
  Shield,
  Sparkles,
  Workflow,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { useOrchestratorStatus } from "@/lib/use-orchestrator";
import type { ChannelConfig, ScheduleConfig } from "@/lib/types";
import { TEST_REPORT_EMAIL, TEST_REPORT_WHATSAPP } from "@/lib/channel-defaults";
import { DeliveryInbox } from "@/components/settings-panel";

function maskEmail(email: string) {
  const [user, domain] = email.split("@");
  if (!domain) return "••••••";
  return `${user.slice(0, 2)}*****@${domain}`;
}

export function ConnectorsView() {
  const { status: orchestrator } = useOrchestratorStatus();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [email, setEmail] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [scheduleTime, setScheduleTime] = useState("08:00");
  const [scheduleGoal, setScheduleGoal] = useState("sanity check endless aisle login and home modules");
  const [editChannel, setEditChannel] = useState<"email" | "whatsapp" | "schedule" | null>(null);
  const [baseUrl, setBaseUrl] = useState("••••••••••••");

  useEffect(() => {
    Promise.all([
      fetch("/api/settings").then((r) => r.json()),
      fetch("/api/credentials").then((r) => r.json()),
    ])
      .then(([settingsJson, credJson]) => {
        const json = settingsJson as { schedule: ScheduleConfig; channels: ChannelConfig };
        setEmail(json.channels?.email?.[0] || TEST_REPORT_EMAIL);
        setWhatsapp(json.channels?.whatsapp || TEST_REPORT_WHATSAPP);
        setScheduleTime(json.schedule?.timeLocal || "08:00");
        setScheduleGoal(json.schedule?.goal || "sanity check endless aisle login and home modules");
        const url = credJson.values?.EA_BASE_URL;
        if (url && !String(url).includes("*")) setBaseUrl(String(url));
      })
      .finally(() => setLoading(false));
  }, []);

  async function saveChannels() {
    setSaving(true);
    try {
      await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          channels: { email: [email.trim()], whatsapp: whatsapp.trim() },
          schedule: {
            enabled: true,
            timeLocal: scheduleTime,
            timezone: "Asia/Kolkata",
            goal: scheduleGoal,
            channels: ["email", "whatsapp"],
          },
        }),
      });
      setEditChannel(null);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="text-muted">Loading connectors…</p>;

  return (
    <div className="view-stack">
      <header className="view-header">
        <div>
          <h1>Connectors & Policy</h1>
          <p className="view-subtitle">
            Environment, credentials, notifications, agent policy and integrations
          </p>
        </div>
      </header>

      <div className="connectors-sections">
        <section className="connectors-section">
          <h2>Environment</h2>
          <div className="connector-grid-2">
            <div className="policy-card">
              <h3>Environment</h3>
              <p className="text-muted">UAT</p>
              <dl className="connector-dl">
                <dt>Base URL</dt>
                <dd className="font-mono">{baseUrl}</dd>
                <dt>Status</dt>
                <dd>{orchestrator?.connected ? "Connected" : "Offline"}</dd>
              </dl>
            </div>
            <div className="policy-card">
              <h3>Execution</h3>
              <p className="text-muted">Playwright</p>
              <dl className="connector-dl">
                <dt>Runner</dt>
                <dd>Local / CI</dd>
                <dt>Status</dt>
                <dd>Ready</dd>
              </dl>
            </div>
          </div>
        </section>

        <section className="connectors-section">
          <h2>Report Channels</h2>
          <div className="connector-grid-3">
            <div className="policy-card">
              <Mail size={18} aria-hidden />
              <h3>Email Reports</h3>
              <p>
                Status: <strong>Configured</strong>
              </p>
              <p>Destination: {maskEmail(email)}</p>
              <Button variant="secondary" className="btn-outline-dark" size="sm" onClick={() => setEditChannel("email")}>
                Configure
              </Button>
            </div>
            <div className="policy-card">
              <MessageCircle size={18} aria-hidden />
              <h3>WhatsApp Reports</h3>
              <p>
                Status: <strong>Test configuration</strong>
              </p>
              <Button
                variant="secondary"
                className="btn-outline-dark"
                size="sm"
                onClick={() => setEditChannel("whatsapp")}
              >
                Configure
              </Button>
            </div>
            <div className="policy-card">
              <Clock size={18} aria-hidden />
              <h3>Scheduling</h3>
              <p>
                Time: <strong>{scheduleTime} IST</strong>
              </p>
              <p className="text-sm text-muted">{scheduleGoal.slice(0, 72)}…</p>
              <Button
                variant="secondary"
                className="btn-outline-dark"
                size="sm"
                onClick={() => setEditChannel("schedule")}
              >
                Configure schedule
              </Button>
            </div>
          </div>
        </section>

        <section className="connectors-section">
          <h2>Agent Policy</h2>
          <div className="connector-grid-2">
            {[
              { icon: Play, title: "Execution Policy", desc: "Controlled runs with execution gate enforcement." },
              { icon: Shield, title: "Approval Policy", desc: "SME approval required before executable flows." },
              { icon: Workflow, title: "Evidence Policy", desc: "Screenshots and traces captured on each run." },
              { icon: Sparkles, title: "Security Policy", desc: "Secrets never exposed to the workspace agent." },
            ].map((p) => (
              <div key={p.title} className="policy-card">
                <p.icon size={18} aria-hidden />
                <h3>{p.title}</h3>
                <p className="text-sm text-muted">{p.desc}</p>
                <p>
                  Status: <strong>Active</strong>
                </p>
                <Button variant="secondary" className="btn-outline-dark" size="sm">
                  View
                </Button>
              </div>
            ))}
          </div>
        </section>

        <section className="connectors-section">
          <h2>Integrations</h2>
          <div className="connector-grid-2">
            {[
              { name: "Playwright", status: "Connected", provider: "Local runner" },
              { name: "Qdrant", status: "Optional", provider: "Vector retrieval" },
              { name: "LLM Provider", status: orchestrator?.agentMode ? "Configured" : "Assisted", provider: "Orchestrator" },
              { name: "Notification Service", status: "Configured", provider: "Email / WhatsApp" },
            ].map((i) => (
              <div key={i.name} className="policy-card">
                <h3>{i.name}</h3>
                <p>
                  {i.provider} · <strong>{i.status}</strong>
                </p>
                <Button variant="secondary" className="btn-outline-dark" size="sm">
                  Configure
                </Button>
              </div>
            ))}
          </div>
        </section>

        <DeliveryInbox />
      </div>

      {editChannel ? (
        <div className="connector-modal-backdrop" role="dialog" aria-modal="true">
          <div className="connector-modal">
            <h2>Configure {editChannel}</h2>
            {editChannel === "email" ? (
              <label className="scout-field">
                Email destination
                <Input value={email} onChange={(e) => setEmail(e.target.value)} />
              </label>
            ) : null}
            {editChannel === "whatsapp" ? (
              <label className="scout-field">
                WhatsApp number
                <Input value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} />
              </label>
            ) : null}
            {editChannel === "schedule" ? (
              <>
                <label className="scout-field">
                  Time (IST)
                  <Input value={scheduleTime} onChange={(e) => setScheduleTime(e.target.value)} />
                </label>
                <label className="scout-field">
                  Prompt
                  <Textarea value={scheduleGoal} onChange={(e) => setScheduleGoal(e.target.value)} rows={3} />
                </label>
              </>
            ) : null}
            <div className="command-actions-v2">
              <Button className="btn-black" disabled={saving} onClick={saveChannels}>
                <Save size={14} />
                Save
              </Button>
              <Button variant="secondary" className="btn-outline-dark" onClick={() => setEditChannel(null)}>
                Cancel
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
