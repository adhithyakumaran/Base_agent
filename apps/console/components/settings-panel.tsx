"use client";

import { useEffect, useState } from "react";
import { Clock, Mail, MessageCircle, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import type { ChannelConfig, ScheduleConfig } from "@/lib/types";
import { TEST_REPORT_EMAIL, TEST_REPORT_WHATSAPP } from "@/lib/channel-defaults";

type SettingsPayload = {
  schedule: ScheduleConfig;
  channels: ChannelConfig;
  selectedModel: string;
};

export function SettingsPanel() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [email, setEmail] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [scheduleTime, setScheduleTime] = useState("08:00");
  const [scheduleEnabled, setScheduleEnabled] = useState(true);
  const [scheduleGoal, setScheduleGoal] = useState("morning sanity check — Endless Aisle UAT");

  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then((json: SettingsPayload) => {
        setEmail(json.channels?.email?.[0] || TEST_REPORT_EMAIL);
        setWhatsapp(json.channels?.whatsapp || TEST_REPORT_WHATSAPP);
        setScheduleTime(json.schedule?.timeLocal || "08:00");
        setScheduleEnabled(json.schedule?.enabled ?? true);
        setScheduleGoal(json.schedule?.goal || "morning sanity check — Endless Aisle UAT");
      })
      .finally(() => setLoading(false));
  }, []);

  async function save() {
    setSaving(true);
    setSaved(false);
    try {
      await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          channels: { email: [email.trim()], whatsapp: whatsapp.trim() },
          schedule: {
            enabled: scheduleEnabled,
            timeLocal: scheduleTime,
            timezone: "Asia/Kolkata",
            goal: scheduleGoal,
            channels: ["email", "whatsapp"],
          },
        }),
      });
      setSaved(true);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="scout-panel scout-settings">Loading settings…</div>;

  return (
    <section className="scout-panel scout-settings">
      <div className="scout-panel-head">
        <Mail size={16} />
        <span>Report channels & schedule</span>
      </div>
      <div className="scout-settings-body">
        <label className="scout-field">
          <span>
            <Mail size={14} /> Email inbox (test)
          </span>
          <Input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your-email@example.com"
          />
        </label>
        <label className="scout-field">
          <span>
            <MessageCircle size={14} /> WhatsApp mobile (test)
          </span>
          <Input
            value={whatsapp}
            onChange={(e) => setWhatsapp(e.target.value)}
            placeholder="+91XXXXXXXXXX"
          />
        </label>
        <label className="scout-field">
          <span>
            <Clock size={14} /> Scheduled sanity time (IST)
          </span>
          <div className="scout-inline">
            <Input value={scheduleTime} onChange={(e) => setScheduleTime(e.target.value)} />
            <button
              type="button"
              className={`scout-switch ${scheduleEnabled ? "on" : ""}`}
              aria-pressed={scheduleEnabled}
              onClick={() => setScheduleEnabled((v) => !v)}
            >
              <span />
            </button>
          </div>
        </label>
        <label className="scout-field">
          <span>Scheduled prompt</span>
          <Textarea value={scheduleGoal} onChange={(e) => setScheduleGoal(e.target.value)} rows={2} />
        </label>
        <Button className="scout-btn-emerald" disabled={saving} onClick={save}>
          <Save size={14} />
          {saving ? "Saving…" : saved ? "Saved" : "Save channels"}
        </Button>
        <p className="scout-rec-note">
          Reports are queued to your inbox after each run. Live SMTP/Twilio sends when configured on the server.
        </p>
      </div>
    </section>
  );
}

export function DeliveryInbox() {
  const [entries, setEntries] = useState<
    { at: string; channel: string; detail?: string; bodyPreview?: string }[]
  >([]);

  useEffect(() => {
    fetch("/api/delivery")
      .then((r) => r.json())
      .then((json) => setEntries(json.entries || []))
      .catch(() => setEntries([]));
  }, []);

  return (
    <section className="scout-panel scout-inbox">
      <div className="scout-panel-head">
        <MessageCircle size={16} />
        <span>Delivery inbox</span>
      </div>
      <div className="scout-inbox-body">
        {entries.length === 0 ? (
          <p className="scout-muted">No deliveries yet — run a suite with channels enabled.</p>
        ) : (
          <ul>
            {entries.slice(0, 8).map((e, i) => (
              <li key={`${e.at}-${i}`}>
                <strong>{e.channel}</strong>
                <span>{new Date(e.at).toLocaleString()}</span>
                <p>{e.detail || e.bodyPreview?.slice(0, 120)}</p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
