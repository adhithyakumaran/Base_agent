import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { navigationPathForFlow } from "@/lib/flow-navigation-paths";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");

function read(rel: string) {
  return readFileSync(path.join(root, rel), "utf8");
}

describe("P13.1 UI layout contracts", () => {
  it("flows view uses master/detail panels (not drawer below grid)", () => {
    const src = read("components/views/flows-view.tsx");
    assert.match(src, /flows-master-detail/);
    assert.match(src, /flows-list-panel/);
    assert.match(src, /flows-detail-panel/);
    assert.doesNotMatch(src, /flow-card-grid/);
    assert.doesNotMatch(src, /flow-drawer/);
    assert.match(src, /flow-card--selected/);
  });

  it("scout CSS defines selected flow gradient and command workspace", () => {
    const css = read("styles/scout-v2.css");
    assert.match(css, /\.flow-card--selected[\s\S]*var\(--gradient-accent-strong\)/);
    assert.match(css, /\.flows-master-detail/);
    assert.match(css, /\.command-workspace/);
    assert.match(css, /#090b0f/);
  });

  it("ask agent view exposes command workspace and readiness strip", () => {
    const src = read("components/views/ask-agent-view.tsx");
    assert.match(src, /command-workspace/);
    assert.match(src, /readiness-strip/);
    assert.match(src, /latest-run-timeline/);
  });

  it("connectors view uses sectioned dashboard layout", () => {
    const src = read("components/views/connectors-view.tsx");
    assert.match(src, /connectors-sections/);
    assert.match(src, /connector-modal-backdrop/);
    assert.match(src, /Report Channels/);
  });

  it("navigation path helper returns verified nodes for canonical flows", () => {
    const path003 = navigationPathForFlow("BF-PRODUCT-003");
    assert.ok(path003.length >= 4);
    assert.equal(path003.every((n) => n.status === "verified"), true);
    const path004 = navigationPathForFlow("BF-PRODUCT-004");
    assert.equal(path004[path004.length - 1]?.label, "Product Detail");
  });
});
