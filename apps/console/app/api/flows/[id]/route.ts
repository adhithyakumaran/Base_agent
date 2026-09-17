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

    const scenarios: { id: string; title: string; description: string }[] = [];
    try {
      const scRaw = await fs.readFile(path.join(DESIGN_ROOT, id, "scenarios.yaml"), "utf8");
      const scBlocks = scRaw.split(/^- id:\s/m).slice(1);
      for (const block of scBlocks) {
        const scId = block.match(/^SC-[^\n]+/)?.[0]?.trim();
        const title = block.match(/^\s+title:\s*(.+)\s*$/m)?.[1]?.trim() || "";
        const steps = block.match(/^\s+steps:\s*\n((?:\s+-\s+.+\n)+)/m)?.[1] || "";
        if (scId) scenarios.push({ id: scId, title, description: steps.replace(/^\s+-\s+/gm, " · ").trim() });
      }
    } catch {
      /* optional */
    }

    const suites: { name: string; count: number; status: string }[] = [];
    try {
      const suRaw = await fs.readFile(path.join(DESIGN_ROOT, id, "suite.yaml"), "utf8");
      const positive = (testCases.filter((t) => t.type === "positive").length);
      const negative = testCases.filter((t) => t.type === "negative").length;
      const status = suRaw.match(/^status:\s*(.+)\s*$/m)?.[1]?.trim() || approvalStatus;
      suites.push({ name: "Positive suite", count: positive, status });
      suites.push({ name: "Negative suite", count: negative, status });
      suites.push({ name: "Regression coverage", count: testCases.length, status });
    } catch {
      /* optional */
    }

    const automation = {
      framework: "Playwright",
      runner: `npm run test:flow:positive -- ${id}`,
      sampleTest: testCases[0]?.id || `TC-${id}-P01`,
      parameters: "sku = runtime parameter (QA_PARAM_SKU)",
    };

    return NextResponse.json({
      flow: {
        id,
        name: flowName,
        purpose,
        approvalStatus,
        kbStatus: kbRaw.match(/^status:\s*(.+)\s*$/m)?.[1]?.trim() || "READY",
        testCases,
        scenarios,
        suites,
        automation,
        coverage,
        businessRules: [...new Set(businessRules)].slice(0, 8),
        executionGate: gate,
        artifacts: ["scenarios.yaml", "test-cases.yaml", "suite.yaml"],
        overview: {
          businessPurpose: purpose,
          preconditions: "Authenticated user with access to flow pages (see test cases).",
          expectedOutcomes: businessRules.slice(0, 3).join("; ") || "Flow completes with validated business rules.",
          pagesInvolved: kbRaw.match(/pages?:\s*\n((?:\s+-\s+.+\n)+)/i)?.[1]?.replace(/^\s+-\s+/gm, ", ").trim() || "See discovery KB",
          navigation: "Primary business path per scenarios.yaml",
          testData: "Runtime parameters (e.g. SKU) via QA_PARAM_SKU",
          apexMetadata: kbRaw.match(/^flow_name:\s*(.+)\s*$/m)?.[1]?.trim() || flowName,
        },
      },
    });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 404 });
  }
}
