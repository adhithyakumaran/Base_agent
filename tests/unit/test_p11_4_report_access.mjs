import test from "node:test";
import assert from "node:assert/strict";

/** Mirrors run id validation in apps/console/lib/run-access.ts (P10.1). */
function runIdAllowed(runId) {
  if (!runId || runId.includes("..") || runId.includes("/")) return false;
  return true;
}

test("run id path traversal blocked for report URLs", () => {
  assert.equal(runIdAllowed("../etc"), false);
  assert.equal(runIdAllowed("run/foo"), false);
  assert.equal(runIdAllowed("run_m54p"), true);
});
