import test from "node:test";
import assert from "node:assert/strict";

import { assertRunAccessible } from "../../apps/console/lib/run-access.ts";

test("assertRunAccessible rejects path traversal run ids", async () => {
  assert.equal(await assertRunAccessible("../etc"), false);
  assert.equal(await assertRunAccessible("run/foo"), false);
});

test("assertRunAccessible rejects unknown run without artifacts", async () => {
  assert.equal(await assertRunAccessible("run_does_not_exist_p11_4"), false);
});
