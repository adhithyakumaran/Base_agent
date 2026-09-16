"use client";

import { useCallback, useEffect, useState } from "react";

export type OrchestratorStatus = {
  connected: boolean;
  environment: string;
  executor: string;
  llmEnabled: boolean;
  flowCounts: {
    total: number;
    smeReady: number;
    approved: number;
    executable: number;
    awaitingApproval: number;
    pendingArtifacts: number;
  };
  pendingApprovals: number;
  safetyGate: string;
  agentMode: string;
};

export function useOrchestratorStatus(pollMs = 30000) {
  const [status, setStatus] = useState<OrchestratorStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/orchestrator", { cache: "no-store" });
      if (!res.ok) throw new Error(`Orchestrator status ${res.status}`);
      setStatus(await res.json());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, pollMs);
    return () => window.clearInterval(id);
  }, [refresh, pollMs]);

  return { status, error, loading, refresh };
}
