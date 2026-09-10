import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { repoRoot } from "@/lib/repo-root";

const REPO = repoRoot();
const INDEX = path.join(REPO, "data", "discovery-kb", "flows", "index.yaml");
const TESTS = path.join(REPO, "apps", "automation", "tests");

async function countSpecs(dir: string, tag?: string): Promise<number> {
  let count = 0;
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) count += await countSpecs(full, tag);
    else if (e.name.endsWith(".spec.ts")) {
      if (!tag) count += 1;
      else {
        const text = await fs.readFile(full, "utf8");
        if (text.includes(tag)) count += 1;
      }
    }
  }
  return count;
}

export async function GET() {
  try {
    const raw = await fs.readFile(INDEX, "utf8");
    const ready = (raw.match(/status: READY/g) || []).length;
    const draft = (raw.match(/status: DRAFT/g) || []).length;
    const negativeTests = await countSpecs(TESTS, "@negative");
    const allSpecs = await countSpecs(TESTS);
    return NextResponse.json({
      readyFlows: ready,
      draftFlows: draft,
      automatedFlows: allSpecs,
      negativeTests,
      sanityCases: ready,
      note: "Expand @negative coverage in apps/automation/tests/ — template: BF-LOGIN-001-negative.spec.ts",
    });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
