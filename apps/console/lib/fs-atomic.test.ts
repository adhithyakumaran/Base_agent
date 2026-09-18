import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { atomicWriteJson, readTextWithRetry } from "./fs-atomic.ts";

test("atomicWriteJson replaces target and readers see valid JSON", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "fs-atomic-"));
  const target = path.join(dir, "state.json");
  await atomicWriteJson(target, { runs: [{ id: "run_a" }] });
  const raw = await readTextWithRetry(target);
  assert.equal(JSON.parse(raw).runs[0].id, "run_a");
});

test("readTextWithRetry tolerates brief missing file during replace", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "fs-atomic-"));
  const target = path.join(dir, "state.json");
  await atomicWriteJson(target, { v: 1 });
  await atomicWriteJson(target, { v: 2 });
  const raw = await readTextWithRetry(target);
  assert.equal(JSON.parse(raw).v, 2);
});
