"use client";

import { useEffect, useRef } from "react";
import type { AgentRun } from "@/lib/types";
import { isRunTerminal } from "@/lib/run-display";

const POLL_MS = 2500;

async function fetchRun(id: string): Promise<AgentRun | null> {
  const res = await fetch(`/api/runs/${id}`, { cache: "no-store" });
  if (!res.ok) return null;
  const json = (await res.json()) as { run?: AgentRun };
  return json.run || null;
}

async function fetchLatestRun(): Promise<AgentRun | null> {
  const res = await fetch("/api/runs", { cache: "no-store" });
  if (!res.ok) return null;
  const json = (await res.json()) as { runs?: AgentRun[] };
  return json.runs?.[0] || null;
}

/** Keep latest-run card aligned with persisted run state (poll until terminal). */
export function useLatestRunSync(
  activeRun: AgentRun | null,
  setActiveRun: (run: AgentRun | null) => void
) {
  const runId = activeRun?.id;
  const terminal = isRunTerminal(activeRun);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      if (activeRun?.id) return;
      const latest = await fetchLatestRun();
      if (!cancelled && mounted.current && latest) {
        setActiveRun(latest);
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [activeRun?.id, setActiveRun]);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;

    async function poll() {
      const fresh = await fetchRun(runId as string);
      if (!cancelled && mounted.current && fresh) {
        setActiveRun(fresh);
      }
    }

    poll();
    if (terminal) {
      return () => {
        cancelled = true;
      };
    }

    const timer = window.setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [runId, terminal, setActiveRun]);
}

export function syncRunFromApi(runId: string, setActiveRun: (run: AgentRun) => void) {
  return fetchRun(runId).then((run) => {
    if (run) setActiveRun(run);
    return run;
  });
}
