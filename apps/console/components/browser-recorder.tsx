"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Camera,
  Circle,
  Code2,
  MousePointer2,
  Network,
  Settings2,
  Video,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/input";

type RecorderConfig = {
  console: boolean;
  network: boolean;
  interactions: boolean;
  dom_snapshots: boolean;
  video: boolean;
  session_replay: boolean;
};

const DEFAULT_CONFIG: RecorderConfig = {
  console: true,
  network: true,
  interactions: true,
  dom_snapshots: true,
  video: false,
  session_replay: false,
};

type ToggleRow = {
  key: keyof RecorderConfig;
  label: string;
  hint: string;
  icon: React.ReactNode;
  experimental?: boolean;
};

const TOGGLES: ToggleRow[] = [
  { key: "console", label: "Console", hint: "Browser console logs", icon: <Code2 size={16} /> },
  { key: "network", label: "Network", hint: "HTTP requests & responses", icon: <Network size={16} /> },
  {
    key: "interactions",
    label: "Interactions",
    hint: "Clicks, fills, navigation",
    icon: <MousePointer2 size={16} />,
  },
  {
    key: "dom_snapshots",
    label: "DOM snapshots",
    hint: "Page HTML + screenshots",
    icon: <Camera size={16} />,
  },
  { key: "video", label: "Video recording", hint: "Session video capture", icon: <Video size={16} /> },
  {
    key: "session_replay",
    label: "Session replay",
    hint: "Playwright trace export",
    icon: <Circle size={16} />,
    experimental: true,
  },
];

export function BrowserRecorderPanel() {
  const [config, setConfig] = useState<RecorderConfig>(DEFAULT_CONFIG);
  const [sessionId] = useState(() => `scout-${Date.now().toString(36)}`);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [liveEvents, setLiveEvents] = useState<{ kind: string; at?: string; selector?: string; text?: string }[]>([]);
  const [eventOffset, setEventOffset] = useState(0);

  const refreshStatus = useCallback(async () => {
    try {
      const res = await fetch(`/api/recorder?sessionId=${sessionId}`, { cache: "no-store" });
      if (res.ok) {
        const json = await res.json();
        setStatus(String(json.status?.status || "idle"));
      }
    } catch {
      setStatus("offline");
    }
  }, [sessionId]);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  async function saveConfig(next: RecorderConfig) {
    setConfig(next);
    await fetch("/api/recorder", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId, config: next }),
    });
  }

  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/api/recorder?sessionId=${sessionId}&offset=${eventOffset}`, { cache: "no-store" });
        if (!res.ok) return;
        const json = await res.json();
        const batch = (json.events || []) as typeof liveEvents;
        if (batch.length) {
          setLiveEvents((prev) => [...prev, ...batch].slice(-40));
          setEventOffset(Number(json.offset ?? eventOffset + batch.length));
        }
        await refreshStatus();
      } catch {
        /* ignore poll errors */
      }
    }, 800);
    return () => clearInterval(timer);
  }, [busy, sessionId, eventOffset, refreshStatus]);

  async function startSession() {
    setBusy(true);
    setMessage(null);
    setLiveEvents([]);
    setEventOffset(0);
    try {
      const res = await fetch("/api/recorder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId, config, maxSeconds: 45 }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Recorder failed");
      setStatus(String(json.status || "completed"));
      setMessage(
        json.events
          ? `Captured ${json.events} events — saved to data/discovery-kb/recordings/sessions/${sessionId}`
          : "Recording session queued"
      );
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      refreshStatus();
    }
  }

  return (
    <section className="scout-panel scout-recorder">
      <div className="scout-panel-head">
        <Circle size={14} className="scout-rec-dot" />
        <span>Browser Recorder</span>
        <Badge tone={status === "recording" ? "warn" : "neutral"}>{status}</Badge>
        <Settings2 size={14} className="scout-muted-icon" />
      </div>

      <div className="scout-rec-body">
        <Button className="scout-btn-emerald scout-rec-start" disabled={busy} onClick={startSession}>
          <Circle size={12} fill="currentColor" />
          Start session
          <span className="scout-kbd">⌥⇧R</span>
        </Button>

        <p className="scout-rec-section">For this session</p>
        <ul className="scout-rec-toggles">
          {TOGGLES.map((row) => (
            <li key={row.key}>
              <div className="scout-rec-toggle-meta">
                {row.icon}
                <div>
                  <strong>
                    {row.label}
                    {row.experimental && <span className="scout-exp">EXPERIMENTAL</span>}
                  </strong>
                  <span>{row.hint}</span>
                </div>
              </div>
              <button
                type="button"
                className={`scout-switch ${config[row.key] ? "on" : ""}`}
                aria-pressed={config[row.key]}
                onClick={() => {
                  const next = { ...config, [row.key]: !config[row.key] };
                  void saveConfig(next);
                }}
              >
                <span />
              </button>
            </li>
          ))}
        </ul>

        <p className="scout-rec-note">
          Recordings feed ScoutAI KB discovery — DOM components, locators, and interaction paths for future
          Playwright script generation. SME approval required before promotion.
        </p>
        {message && <p className="scout-rec-msg">{message}</p>}
        {liveEvents.length > 0 && (
          <div className="scout-live-feed">
            <p className="scout-rec-section">Live session feed</p>
            <ul>
              {liveEvents.slice(-12).map((ev, i) => (
                <li key={`${ev.at}-${i}`}>
                  <strong>{ev.kind}</strong>{" "}
                  {ev.selector ? String(ev.selector) : ev.text ? String(ev.text).slice(0, 80) : ""}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
