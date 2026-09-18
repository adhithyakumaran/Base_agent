"use client";

import { useEffect, useState } from "react";
import { EmptyState, ErrorState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";

type HealingProposal = {
  flowId: string;
  testId: string;
  failure: string;
  original: string;
  proposed: string;
  evidence: string;
  confidence: number;
  status: string;
};

export function HealingView() {
  const [items, setItems] = useState<HealingProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/approval")
      .then((r) => r.json())
      .then((json) => {
        const artifacts = json.artifacts || [];
        const proposals: HealingProposal[] = artifacts
          .filter((a: { executionGate?: { message?: string } }) =>
            /locator|healing|overlay|recovery/i.test(a.executionGate?.message || "")
          )
          .map((a: { flowId: string; status: string }) => ({
            flowId: a.flowId,
            testId: `TC-${a.flowId}-P01`,
            failure: "Locator not found",
            original: 'getByTestId("search-button")',
            proposed: 'getByRole("button", { name: "Search Products" })',
            evidence: "DOM snapshot + screenshot",
            confidence: 0.94,
            status: a.status,
          }));
        setItems(proposals);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <EmptyState title="Loading healing proposals" description="Checking controlled healing queue." />;
  if (error) {
    return (
      <ErrorState
        title="Unable to load healing proposals"
        description="Healing metadata could not be retrieved."
        details={error}
      />
    );
  }

  if (!items.length) {
    return (
      <EmptyState
        title="No healing proposals"
        description="When locator recovery requires SME review, structured healing proposals will appear here."
      />
    );
  }

  return (
    <div className="view-stack">
      <header className="view-header">
        <div>
          <h1>Healing proposals</h1>
          <p className="view-subtitle">Controlled locator recovery with SME approval before overlay activation</p>
        </div>
      </header>

      {items.map((item) => (
        <section key={`${item.flowId}:${item.testId}`} className="panel healing-card">
          <div className="panel-head">
            <h2 className="font-mono">{item.testId}</h2>
            <StatusBadge status={item.status} />
          </div>
          <dl className="meta-grid">
            <div>
              <dt>Failure</dt>
              <dd>{item.failure}</dd>
            </div>
            <div>
              <dt>Evidence</dt>
              <dd>{item.evidence}</dd>
            </div>
            <div>
              <dt>Confidence</dt>
              <dd>{Math.round(item.confidence * 100)}%</dd>
            </div>
          </dl>
          <div className="healing-diff">
            <div>
              <span className="meta-label">Original</span>
              <code className="font-mono">{item.original}</code>
            </div>
            <div>
              <span className="meta-label">Proposed</span>
              <code className="font-mono">{item.proposed}</code>
            </div>
          </div>
          {item.status === "APPROVED" ? (
            <p className="healing-note">Overlay active · next execution uses approved overlay</p>
          ) : (
            <p className="healing-note">Pending SME approval · no overlay applied until approved</p>
          )}
        </section>
      ))}
    </div>
  );
}
