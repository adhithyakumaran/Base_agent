import test from "node:test";
import assert from "node:assert/strict";

import { getSkuParam, getRunParam } from "../../apps/automation/src/core/run-params.ts";

test("getSkuParam reads QA_PARAM_SKU", () => {
  process.env.QA_PARAM_SKU = "ABC123";
  assert.equal(getSkuParam(), "ABC123");
  delete process.env.QA_PARAM_SKU;
});

test("getSkuParam rejects unsafe values", () => {
  process.env.QA_PARAM_SKU = "bad;drop";
  assert.throws(() => getSkuParam(), /unsafe characters/);
  delete process.env.QA_PARAM_SKU;
});

test("getRunParam validates SKU pattern", () => {
  process.env.QA_PARAM_SKU = "AB";
  assert.throws(() => getRunParam("SKU"), /failed validation/);
  delete process.env.QA_PARAM_SKU;
});
