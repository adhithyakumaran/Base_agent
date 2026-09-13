"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { DataTable, StatusCell } from "@/components/ui/data-table";
import { ErrorState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";

type ApprovalArtifact = {
  flowId: string;
  artifact: string;
  status: string;
  executionGate?: { reasonCode?: string; message?: string };
};

type ApprovalRow = ApprovalArtifact & { id: string };

function riskFor(item: ApprovalArtifact): "Low" | "Medium" | "High" {
  if (item.artifact.includes("suite")) return "High";
  if (item.artifact.includes("scenario")) return "Medium";
  return "Medium";
}

function typeFor(item: ApprovalArtifact): string {
  if (/healing|overlay|locator/i.test(item.executionGate?.message || "")) return "Healing";
  if (item.artifact === "test-cases.yaml") return "Test";
  if (item.artifact === "scenarios.yaml") return "Scenario";
  return "Flow";
}

export function ApprovalsView() {
  const [items, setItems] = useState<ApprovalRow[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [approver, setApprover] = useState("SME Reviewer");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/approval", { cache: "no-store" });
      if (!res.ok) throw new Error(`Approval service responded with ${res.status}`);
      const json = await res.json();
      const artifacts = (json.artifacts || []) as ApprovalArtifact[];
      setItems(
        artifacts
          .filter((a: ApprovalArtifact) => a.status === "PENDING_SME_APPROVAL")
          .map((a: ApprovalArtifact) => ({ ...a, id: `${a.flowId}:${a.artifact}` }))
      );
      setPendingCount(Number(json.pendingCount || 0));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function act(item: ApprovalArtifact, action: "approve" | "reject") {
    const key = `${item.flowId}:${item.artifact}`;
    setBusyId(key);
    try {
      const res = await fetch("/api/approval", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          flowId: item.flowId,
          artifact: item.artifact,
          action,
          approver,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Approval action failed");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  }

  if (error && !items.length && !loading) {
    return (
      <ErrorState
        title="Unable to load approvals"
        description="The approval queue could not be retrieved."
        onRetry={load}
        details={error}
      />
    );
  }

  return (
    <div className="view-stack">
      <header className="view-header">
        <div>
          <h1>Approvals</h1>
          <p className="view-subtitle">{pendingCount} pending SME decisions</p>
        </div>
        <StatusBadge status="PENDING" />
      </header>

      <section className="panel">
        <div className="toolbar">
          <label className="approver-field">
            <span>Reviewer identity</span>
            <input
              value={approver}
              onChange={(e) => setApprover(e.target.value)}
              aria-label="Approver identity"
            />
          </label>
        </div>

        <DataTable<ApprovalRow>
          columns={[
            { key: "type", header: "Type", render: (r) => typeFor(r) },
            { key: "flowId", header: "Asset", mono: true, render: (r) => `${r.flowId} · ${r.artifact}` },
            {
              key: "reason",
              header: "Reason",
              render: (r) => r.executionGate?.message || "Awaiting SME review before execution",
            },
            { key: "risk", header: "Risk", render: (r) => riskFor(r) },
            { key: "status", header: "Status", render: (r) => <StatusCell status={r.status} /> },
            {
              key: "actions",
              header: "Actions",
              render: (r) => {
                const key = `${r.flowId}:${r.artifact}`;
                const busy = busyId === key;
                return (
                  <div className="row-actions">
                    <Button variant="secondary" disabled={busy} onClick={() => act(r, "reject")}>
                      Reject
                    </Button>
                    <Button disabled={busy || !approver.trim()} onClick={() => act(r, "approve")}>
                      Approve
                    </Button>
                  </div>
                );
              },
            },
          ]}
          rows={items}
          loading={loading}
          emptyTitle="No pending approvals"
          emptyDescription="All artifacts are approved or no approval artifacts require review."
        />
      </section>
    </div>
  );
}
