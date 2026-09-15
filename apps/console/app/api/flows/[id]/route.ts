import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { requireApiAuth } from "@/lib/api-auth";
import { repoRoot } from "@/lib/repo-root";
import { evaluateFlowExecution } from "@/lib/approval-store";

const REPO = repoRoot();
const KB_ROOT = path.join(REPO, "data", "discovery-kb", "flows");
const DESIGN_ROOT = path.join(REPO, "apps", "automation", "test-design", "flows");

export async function GET(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const denied = requireApiAuth(req);
  if (denied) return denied;
  const { id } = await ctx.params;
  if (!/^BF-[A-Z0-9-]+$/.test(id)) {
    return NextResponse.json({ error: "invalid flow id" }, { status: 400 });
  }

  try {
    const kbPath = path.join(KB_ROOT, `${id}.yaml`);
    const kbRaw = await fs.readFile(kbPath, "utf8");
    const purpose = kbRaw.match(/^purpose:\s*(.+)\s*$/m)?.[1]?.trim() || "";
    const flowName = kbRaw.match(/^flow_name:\s*(.+)\s*$/m)?.[1]?.trim() || id;

    const tcPath = path.join(DESIGN_ROOT, id, "test-cases.yaml");
    const testCases: { id: string; title: string; type: string; priority: string }[] = [];
    let approvalStatus = "UNKNOWN";
    const businessRules: string[] = [];
    try {
      const tcRaw = await fs.readFile(tcPath, "utf8");
      approvalStatus = tcRaw.match(/^status:\s*(.+)\s*$/m)?.[1]?.trim() || "UNKNOWN";
      const blocks = tcRaw.split(/^- id:\s/m).slice(1);
      for (const block of blocks) {
        const tcId = block.match(/^TC-[^\n]+/)?.[0]?.trim();
        const title = block.match(/^\s+title:\s*(.+)\s*$/m)?.[1]?.trim() || "";
        const type = block.match(/^\s+type:\s*(.+)\s*$/m)?.[1]?.trim() || "positive";
        const priority = block.match(/^\s+priority:\s*(.+)\s*$/m)?.[1]?.trim() || "P1";
        if (tcId) testCases.push({ id: tcId, title, type, priority });
        const rules = block.match(/business_rules_validated:\s*\n((?:\s+-\s+.+\n)+)/);
        if (rules?.[1]) {
          for (const line of rules[1].split("\n")) {
            const rule = line.match(/^\s+-\s+(.+)\s*$/);
            if (rule) businessRules.push(rule[1]);
          }
        }
      }
    } catch {
      /* optional design artifacts */
    }

    const coverage = {
      positive: testCases.filter((t) => t.type === "positive").length,
      negative: testCases.filter((t) => t.type === "negative").length,
      parameterized: testCases.filter((t) => /sku|param/i.test(t.title)).length,
      edge: testCases.filter((t) => t.type === "edge").length,
    };

    const gate = await evaluateFlowExecution(id);

    return NextResponse.json({
      flow: {
        id,
        name: flowName,
        purpose,
        approvalStatus,
        kbStatus: kbRaw.match(/^status:\s*(.+)\s*$/m)?.[1]?.trim() || "READY",
        testCases,
        coverage,
        businessRules: [...new Set(businessRules)].slice(0, 8),
        executionGate: gate,
        artifacts: ["scenarios.yaml", "test-cases.yaml", "suite.yaml"],
      },
    });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 404 });
  }
}
