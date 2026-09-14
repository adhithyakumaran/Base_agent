"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Monitor, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

export type LiveEvent = {
  sequence?: number;
  phase?: string;
  action?: string;
  target?: string;
  value_summary?: string;
  status?: string;
  duration_ms?: number;
  timestamp?: string;
};

type Props = {
  runId: string | null;
  goal?: string;
  flowId?: string;
  runStatus?: string;
  conclusion?: string;
  liveMode?: boolean;
};

export function LiveRunPanel({ runId, goal, flowId, runStatus, conclusion, liveMode }: Props) {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [session, setSession] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const active = runStatus === "running" || runStatus === "queued";

  useEffect(() => {
    if (!runId || !liveMode) return;
    let cancelled = false;
    const source = new EventSource(`/api/runs/${runId}/stream`);
    source.onmessage = (msg) => {
      if (cancelled) return;
      try {
        const row = JSON.parse(msg.data) as LiveEvent;
        setEvents((prev) => {
          const key = row.sequence ?? prev.length;
          if (prev.some((p) => p.sequence === key)) return prev;
          return [...prev, row].slice(-200);
        });
      } catch {
        /* ignore */
      }
    };
    source.onerror = () => {
      if (!cancelled) setError("Live stream disconnected");
    };
    return () => {
      cancelled = true;
      source.close();
    };
  }, [runId, liveMode]);

  const refreshSession = useCallback(async () => {
    if (!runId) return;
    try {
      const res = await fetch(`/api/runs/${runId}/browser`, { cache: "no-store" });
      if (res.ok) setSession(await res.json());
    } catch {
      setSession(null);
    }
  }, [runId]);

  useEffect(() => {
    if (!runId || !liveMode) return;
    refreshSession();
    const t = setInterval(refreshSession, 3000);
    return () => clearInterval(t);
  }, [runId, liveMode, refreshSession]);

  async function closeBrowser() {
    if (!runId) return;
    await fetch(`/api/runs/${runId}/browser/close`, { method: "POST" });
    await refreshSession();
  }

  const keepOpenMessage = useMemo(() => {
    if (conclusion === "PASS" && session?.keep_open) {
      return "Browser remains open for inspection.";
    }
    return null;
  }, [conclusion, session]);

  if (!liveMode || !runId) return null;

  return (
    <section className="panel live-run-panel" aria-label="Live browser run">
      <header className="live-run-header">
        <div>
          <p className="live-run-kicker">{active ? "RUNNING" : "RUN COMPLETE"}</p>
          <h2>{goal || "Live QA run"}</h2>
          {flowId ? <p className="live-run-flow">{flowId}</p> : null}
        </div>
        <div className="live-run-badges">
          <span className="badge-live">
            <Monitor size={14} aria-hidden /> LIVE BROWSER
          </span>
          <span>{String(session?.channel || "Chrome")} • APEX</span>
        </div>
      </header>

      <ul className="live-event-list">
        {events.map((ev, idx) => (
          <li key={`${ev.sequence ?? idx}-${ev.action}`}>
            <span className={`live-event-status live-event-${(ev.status || "OK").toLowerCase()}`}>
              {ev.status === "OK" || !ev.status ? "✓" : "●"}
            </span>
            <span className="live-event-phase">{ev.phase}</span>
            <span className="live-event-action">{ev.action}</span>
            {ev.value_summary ? <span className="live-event-value">{ev.value_summary}</span> : null}
            {ev.duration_ms ? <span className="live-event-duration">{ev.duration_ms}ms</span> : null}
          </li>
        ))}
        {active && events.length === 0 ? (
          <li className="live-event-wait">
            <Loader2 className="spin" size={16} aria-hidden /> Waiting for live browser actions…
          </li>
        ) : null}
      </ul>

      <footer className="live-run-footer">
        <div>
          <strong>Browser session:</strong> {String(session?.status || "UNKNOWN")}
          {session?.current_url ? (
            <div className="live-run-url">Current URL: {String(session.current_url)}</div>
          ) : null}
        </div>
        {keepOpenMessage ? <p className="live-run-complete">{keepOpenMessage}</p> : null}
        {error ? <p className="live-run-error">{error}</p> : null}
        <Button type="button" variant="secondary" onClick={closeBrowser}>
          <XCircle size={16} aria-hidden /> Close Browser
        </Button>
      </footer>
    </section>
  );
}
