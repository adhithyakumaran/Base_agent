import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  buildRunTimelineStages,
  executionSucceededForGtReview,
  isGroundTruthReviewReason,
  isRunTerminal,
  runDisplayBadge,
} from "@/lib/run-display";
import type { AgentRun } from "@/lib/types";

function run(partial: Partial<AgentRun> & Pick<AgentRun, "id">): AgentRun {
  return {
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:01:00.000Z",
    type: "adhoc",
    goal: "Search SKU 552811DUDABA00",
    status: "completed",
    model: "disabled",
    llmEnabled: false,
    traces: [],
    usage: { tokensIn: 0, tokensOut: 0, toolCalls: 0, steps: 0, llmCalls: 0 },
    ...partial,
  };
}

describe("runDisplayBadge", () => {
  it("shows PASS for completed PASS run", () => {
    assert.equal(runDisplayBadge(run({ id: "r1", conclusion: "PASS", status: "completed" })), "PASS");
  });

  it("shows NEEDS_REVIEW for needs_review status", () => {
    assert.equal(
      runDisplayBadge(run({ id: "r2", conclusion: "NEEDS_REVIEW", status: "needs_review" })),
      "NEEDS_REVIEW"
    );
  });

  it("shows RUNNING for running status", () => {
    assert.equal(runDisplayBadge(run({ id: "r3", status: "running" })), "RUNNING");
  });

  it("shows PENDING for queued status", () => {
    assert.equal(runDisplayBadge(run({ id: "r4", status: "queued" })), "PENDING");
  });
});

describe("buildRunTimelineStages", () => {
  it("marks verify PASS for terminal PASS run", () => {
    const stages = buildRunTimelineStages(
      run({
        id: "r5",
        conclusion: "PASS",
        status: "completed",
        report: {
          summary: "PASS",
          markdown: "# ok",
          json: {
            agent: {
              local: {
                intent: { flow_ids: ["BF-PRODUCT-003"], reasoning: "product search" },
                execution: {
                  ok: true,
                  mode: "playwright",
                  observations: [
                    {
                      step_index: 0,
                      action: "suite",
                      ok: true,
                      message: "ok",
                      meta: { evidence: [{ path: "a.png" }] },
                    },
                  ],
                },
              },
            },
          },
        },
      })
    );
    assert.equal(stages.every((s) => s.state === "done"), true);
    assert.equal(stages.find((s) => s.id === "verify")?.statusLabel, "PASS");
  });

  it("shows NEEDS_REVIEW on verify for GT review terminal", () => {
    const stages = buildRunTimelineStages(
      run({
        id: "r6",
        conclusion: "NEEDS_REVIEW",
        status: "needs_review",
        reasonCode: "validator.pre_gt_honest",
      })
    );
    assert.equal(stages.find((s) => s.id === "verify")?.statusLabel, "NEEDS_REVIEW");
  });
});

describe("ground truth helpers", () => {
  it("detects GT review reason codes", () => {
    assert.equal(isGroundTruthReviewReason("validator.pre_gt_honest", undefined), true);
    assert.equal(isGroundTruthReviewReason("execution.failed", undefined), false);
  });

  it("blocks GT approval when execution failed", () => {
    const failed = run({
      id: "r9",
      conclusion: "NEEDS_REVIEW",
      report: {
        summary: "x",
        markdown: "x",
        json: { agent: { local: { execution: { ok: false, mode: "playwright" } } } },
      },
    });
    assert.equal(executionSucceededForGtReview(failed), false);
  });

  it("treats PASS as terminal", () => {
    assert.equal(isRunTerminal(run({ id: "r8", conclusion: "PASS" })), true);
  });
});
