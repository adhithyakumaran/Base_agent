"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { GroundTruthDoc } from "@/lib/ground-truth-approve";
import type { AgentRun } from "@/lib/types";
import { parseInsights } from "@/lib/parse-run-insights";

export function GroundTruthApprovalModal({
  open,
  run,
  gt,
  busy,
  error,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  run: AgentRun;
  gt: GroundTruthDoc;
  busy?: boolean;
  error?: string | null;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const [checked, setChecked] = useState(false);
  const insights = parseInsights(run);
  const contracts = gt.business_contract || [];
  const flowLabel = gt.flow_id || insights.flowIds?.[0] || "Flow";
  const subject = gt.subject || "Ground Truth";

  if (!open) return null;

  return (
    <div className="modal-backdrop" role="presentation" onClick={onCancel}>
      <div
        className="modal-card gt-approval-modal"
        role="dialog"
        aria-labelledby="gt-approve-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="gt-approval-modal__head">
          <h2 id="gt-approve-title">Approve Ground Truth</h2>
          <p className="text-sm text-muted">SME review — execution evidence is already captured on this run.</p>
        </header>

        <dl className="gt-approval-modal__meta">
          <div>
            <dt>GT</dt>
            <dd className="font-mono">{gt.id}</dd>
          </div>
          <div>
            <dt>Flow</dt>
            <dd className="font-mono">
              {flowLabel} · {subject}
            </dd>
          </div>
        </dl>

        <section className="gt-approval-modal__section">
          <h3>Business contract</h3>
          <ul className="gt-checklist">
            {contracts.map((line) => (
              <li key={line}>
                <span aria-hidden>✓</span> {line}
              </li>
            ))}
          </ul>
        </section>

        <section className="gt-approval-modal__section">
          <h3>Execution evidence</h3>
          <ul className="gt-checklist">
            <li>
              <span aria-hidden>✓</span> Playwright execution successful
            </li>
            {(run.decisionDiagnostics as { evidence?: { execution_ok?: boolean } } | undefined)?.evidence
              ?.execution_ok !== false ? (
              <li>
                <span aria-hidden>✓</span> Structured execution results captured for revalidation
              </li>
            ) : null}
            <li>
              <span aria-hidden>✓</span>{" "}
              {(run.decisionDiagnostics as { selected_test_case_ids?: string[] } | undefined)
                ?.selected_test_case_ids?.[0] || "Selected test case executed"}
            </li>
            {(insights.evidence?.length || 0) > 0 ? (
              <li>
                <span aria-hidden>✓</span> {insights.evidence?.length} evidence captures on record
              </li>
            ) : null}
          </ul>
        </section>

        <label className="gt-approval-modal__confirm">
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
            disabled={busy}
          />
          I reviewed the evidence and approve this Ground Truth.
        </label>

        {error ? (
          <div className="inline-alert" role="alert">
            {error}
          </div>
        ) : null}

        <footer className="gt-approval-modal__actions">
          <Button variant="secondary" className="btn-outline-dark" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button className="btn-black" disabled={!checked || busy} onClick={onConfirm}>
            Approve &amp; Validate
          </Button>
        </footer>
      </div>
    </div>
  );
}
