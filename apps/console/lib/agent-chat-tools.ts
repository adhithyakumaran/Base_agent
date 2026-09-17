import { promises as fs } from "fs";
import path from "path";
import { evaluateFlowExecution } from "@/lib/approval-store";
import { repoRoot } from "@/lib/repo-root";
import { readState } from "@/lib/store";
import type { AgentRun } from "@/lib/types";

const REPO = repoRoot();
const KB_ROOT = path.join(REPO, "data", "discovery-kb", "flows");
const DESIGN_ROOT = path.join(REPO, "apps", "automation", "test-design", "flows");
const INDEX = path.join(KB_ROOT, "index.yaml");

const SOURCE_ALLOW_PREFIXES = [
  "apps/automation/test-design/",
  "apps/automation/tests/",
  "data/discovery-kb/",
  "docs/",
].map((p) => path.normalize(p));

const SECRET_PATTERNS = [/\.env/i, /credentials/i, /secret/i, /password/i, /api[_-]?key/i, /\.pem$/i];

export type AgentToolAudit = { tool: string; args: Record<string, string>; at: string };

function assertSafeRelative(rel: string): string {
  const normalized = path.normalize(rel).replace(/^(\.\.(\/|\\|$))+/, "");
  if (normalized.includes("..")) throw new Error("path not allowed");
  for (const pat of SECRET_PATTERNS) {
    if (pat.test(normalized)) throw new Error("path not allowed");
  }
  const posix = normalized.split(path.sep).join("/");
  if (!SOURCE_ALLOW_PREFIXES.some((prefix) => posix.startsWith(prefix))) {
    throw new Error("path not allowed");
  }
  return posix;
}

function parseSmeReady(raw: string): Set<string> {
  const ready = new Set<string>();
  let inBlock = false;
  for (const line of raw.split("\n")) {
    if (/^sme_ready:\s*$/.test(line)) {
      inBlock = true;
      continue;
    }
    if (inBlock) {
      const hit = line.match(/^\s+-\s+(BF-[A-Z0-9-]+)\s*$/);
      if (hit) ready.add(hit[1]);
      else if (line.trim() && !/^\s/.test(line)) break;
    }
  }
  return ready;
}

function parseFlowIds(raw: string): { id: string; name: string; status: string }[] {
  const flows: { id: string; name: string; status: string }[] = [];
  let current: { id?: string; name?: string; status?: string } | null = null;
  let inFlows = false;
  for (const line of raw.split("\n")) {
    if (/^flows:\s*$/.test(line)) {
      inFlows = true;
      continue;
    }
    if (!inFlows) continue;
    const idMatch = line.match(/^\s+-\s+id:\s*(.+)\s*$/);
    if (idMatch) {
      if (current?.id) flows.push(current as (typeof flows)[number]);
      current = { id: idMatch[1].trim() };
      continue;
    }
    if (!current) continue;
    const name = line.match(/^\s+name:\s*(.+)\s*$/);
    const status = line.match(/^\s+status:\s*(.+)\s*$/);
    if (name) current.name = name[1].trim();
    if (status) current.status = status[1].trim();
  }
  if (current?.id) flows.push(current as (typeof flows)[number]);
  return flows;
}

export async function searchFlows(query: string, filter?: string) {
  const raw = await fs.readFile(INDEX, "utf8");
  const smeReady = parseSmeReady(raw);
  const flows = parseFlowIds(raw);
  const q = query.trim().toLowerCase();

  const rows = [];
  for (const flow of flows) {
    const gate = await evaluateFlowExecution(flow.id).catch(() => ({ executable: false, message: "" }));
    const approval = await readApprovalStatus(flow.id);
    const row = {
      id: flow.id,
      name: flow.name,
      status: flow.status,
      smeReady: smeReady.has(flow.id),
      executable: gate.executable,
      approvalStatus: approval,
    };
    if (filter === "sme_ready" && !row.smeReady) continue;
    if (filter === "approved" && approval !== "APPROVED") continue;
    if (filter === "needs_review" && approval !== "PENDING_SME_APPROVAL") continue;
    if (q && !row.id.toLowerCase().includes(q) && !row.name.toLowerCase().includes(q)) continue;
    rows.push(row);
  }
  return rows.slice(0, 40);
}

async function readApprovalStatus(flowId: string): Promise<string> {
  try {
    const raw = await fs.readFile(path.join(DESIGN_ROOT, flowId, "test-cases.yaml"), "utf8");
    return raw.match(/^status:\s*(.+)\s*$/m)?.[1]?.trim() || "UNKNOWN";
  } catch {
    return "UNKNOWN";
  }
}

export async function getFlow(flowId: string) {
  if (!/^BF-[A-Z0-9-]+$/.test(flowId)) throw new Error("invalid flow id");
  const kbPath = path.join(KB_ROOT, `${flowId}.yaml`);
  const kbRaw = await fs.readFile(kbPath, "utf8");
  const purpose = kbRaw.match(/^purpose:\s*(.+)\s*$/m)?.[1]?.trim() || "";
  const flowName = kbRaw.match(/^flow_name:\s*(.+)\s*$/m)?.[1]?.trim() || flowId;
  const gate = await evaluateFlowExecution(flowId);
  const tcPath = path.join(DESIGN_ROOT, flowId, "test-cases.yaml");
  const tcRaw = await fs.readFile(tcPath, "utf8").catch(() => "");
  const testCaseIds = (tcRaw.match(/^- id:\s*(TC-[^\n]+)/gm) || []).map((m) =>
    m.replace(/^- id:\s*/, "").trim()
  );
  return {
    id: flowId,
    name: flowName,
    purpose,
    approvalStatus: tcRaw.match(/^status:\s*(.+)\s*$/m)?.[1]?.trim() || "UNKNOWN",
    executable: gate.executable,
    gateMessage: gate.message,
    testCaseIds,
  };
}

export async function getTestCase(flowId: string, testCaseId: string) {
  const tcPath = path.join(DESIGN_ROOT, flowId, "test-cases.yaml");
  const raw = await fs.readFile(tcPath, "utf8");
  const block = raw.split(/^- id:\s/m).find((b) => b.startsWith(testCaseId));
  if (!block) throw new Error("test case not found");
  const title = block.match(/^\s+title:\s*(.+)\s*$/m)?.[1]?.trim() || "";
  const type = block.match(/^\s+type:\s*(.+)\s*$/m)?.[1]?.trim() || "";
  const automationMatch = block.match(/automation:\s*\n((?:\s+.+\n)+)/);
  const automation = automationMatch?.[1] || "";
  return { id: testCaseId, flowId, title, type, automationSnippet: automation.slice(0, 600) };
}

export async function searchRuns(query: string, limit = 15) {
  const state = await readState();
  const q = query.trim().toLowerCase();
  let runs = state.runs as AgentRun[];
  if (q) {
    runs = runs.filter(
      (r) =>
        r.id.toLowerCase().includes(q) ||
        r.goal.toLowerCase().includes(q) ||
        (r.conclusion || "").toLowerCase().includes(q) ||
        r.status.toLowerCase().includes(q)
    );
  }
  return runs.slice(0, limit).map((r) => ({
    id: r.id,
    goal: r.goal,
    status: r.status,
    conclusion: r.conclusion,
    createdAt: r.createdAt,
    executionMode: r.executionMode,
  }));
}

export async function getRun(runId: string) {
  const state = await readState();
  const run = state.runs.find((r) => r.id === runId || r.id.startsWith(runId));
  if (!run) throw new Error("run not found");
  const agent = run.report?.json?.agent as Record<string, unknown> | undefined;
  const local = (agent?.local as Record<string, unknown>) || {};
  const intent = (local.intent as Record<string, unknown>) || {};
  const flowIds = Array.isArray(intent.flow_ids) ? intent.flow_ids.map(String) : [];
  return {
    id: run.id,
    goal: run.goal,
    status: run.status,
    conclusion: run.conclusion,
    flowIds,
    traceCount: run.traces.length,
    decisionDiagnostics: run.decisionDiagnostics,
    updatedAt: run.updatedAt,
  };
}

export async function getEvidenceForRun(runId: string) {
  const state = await readState();
  const run = state.runs.find((r) => r.id === runId || r.id.startsWith(runId));
  if (!run) throw new Error("run not found");
  const agent = run.report?.json?.agent as Record<string, unknown> | undefined;
  const local = (agent?.local as Record<string, unknown>) || {};
  const execution = (local.execution as Record<string, unknown>) || {};
  const observations = Array.isArray(execution.observations)
    ? (execution.observations as { meta?: { evidence?: { path: string; label?: string }[] } }[])
    : [];
  const evidence: { path: string; label?: string }[] = [];
  for (const obs of observations) {
    for (const ev of obs.meta?.evidence || []) {
      evidence.push({ path: ev.path, label: ev.label });
    }
  }
  return { runId: run.id, evidence: evidence.slice(0, 30) };
}

export async function searchKnowledgeBase(query: string) {
  const state = await readState();
  const q = query.trim().toLowerCase();
  return state.knowledge
    .filter(
      (k) =>
        !q ||
        k.title.toLowerCase().includes(q) ||
        k.content.toLowerCase().includes(q) ||
        k.tags.some((t) => t.toLowerCase().includes(q))
    )
    .slice(0, 10)
    .map((k) => ({ id: k.id, title: k.title, format: k.format, preview: k.content.slice(0, 200) }));
}

export async function searchRepository(query: string, maxHits = 12) {
  const q = query.trim().toLowerCase();
  if (!q || q.length < 3) return [];
  const hits: { path: string; line: number; text: string }[] = [];
  const roots = [
    path.join(REPO, "apps/automation/test-design"),
    path.join(REPO, "data/discovery-kb/flows"),
  ];

  async function walk(dir: string) {
    if (hits.length >= maxHits) return;
    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const ent of entries) {
      if (hits.length >= maxHits) break;
      const full = path.join(dir, ent.name);
      if (ent.isDirectory()) {
        if (ent.name === "node_modules" || ent.name.startsWith(".")) continue;
        await walk(full);
      } else if (/\.(yaml|yml|ts|md|json)$/i.test(ent.name)) {
        const rel = path.relative(REPO, full).split(path.sep).join("/");
        try {
          assertSafeRelative(rel);
        } catch {
          continue;
        }
        const content = await fs.readFile(full, "utf8");
        const lines = content.split("\n");
        for (let i = 0; i < lines.length; i++) {
          if (lines[i].toLowerCase().includes(q)) {
            hits.push({ path: rel, line: i + 1, text: lines[i].trim().slice(0, 160) });
            if (hits.length >= maxHits) break;
          }
        }
      }
    }
  }

  for (const root of roots) await walk(root);
  return hits;
}

export async function readSourceFile(relPath: string, maxChars = 8000) {
  const safe = assertSafeRelative(relPath);
  const full = path.join(REPO, safe);
  const content = await fs.readFile(full, "utf8");
  return { path: safe, content: content.slice(0, maxChars) };
}

export async function runAgentTools(
  message: string,
  audit: AgentToolAudit[]
): Promise<{ context: string; links: { type: "flow" | "run"; id: string }[] }> {
  const links: { type: "flow" | "run"; id: string }[] = [];
  const parts: string[] = [];
  const lower = message.toLowerCase();

  const flowIdMatch = message.match(/BF-[A-Z0-9-]+/);
  const tcMatch = message.match(/TC-BF-[A-Z0-9-]+/);
  const runMatch = message.match(/run_[a-z0-9]+/i);

  if (/sme.?ready|executable flows|which flows/.test(lower)) {
    audit.push({ tool: "search_flows", args: { filter: "sme_ready" }, at: new Date().toISOString() });
    const flows = await searchFlows("", "sme_ready");
    parts.push(
      `SME-ready flows (${flows.length}): ${flows.map((f) => f.id).join(", ") || "none"}`
    );
    flows.slice(0, 8).forEach((f) => links.push({ type: "flow", id: f.id }));
  }

  if (/no executable|without automation|not executable/.test(lower)) {
    audit.push({ tool: "search_flows", args: {}, at: new Date().toISOString() });
    const flows = await searchFlows("");
    const blocked = flows.filter((f) => !f.executable);
    parts.push(
      `Non-executable flows (${blocked.length}): ${blocked.map((f) => `${f.id} (${f.approvalStatus})`).join("; ") || "none"}`
    );
  }

  if (flowIdMatch) {
    const id = flowIdMatch[0];
    audit.push({ tool: "get_flow", args: { id }, at: new Date().toISOString() });
    const flow = await getFlow(id);
    links.push({ type: "flow", id });
    parts.push(
      `Flow ${flow.id}: ${flow.name}. Purpose: ${flow.purpose}. Approval: ${flow.approvalStatus}. Executable: ${flow.executable}. Test cases: ${flow.testCaseIds.join(", ")}`
    );
    if (/automation|playwright|npm run/.test(lower)) {
      parts.push(
        `Automation runner example: npm run test:flow:positive -- ${flow.id} (Playwright). Primary spec glob under apps/automation/tests.`
      );
    }
  }

  if (tcMatch && flowIdMatch) {
    audit.push({
      tool: "get_test_case",
      args: { flowId: flowIdMatch[0], testCaseId: tcMatch[0] },
      at: new Date().toISOString(),
    });
    const tc = await getTestCase(flowIdMatch[0], tcMatch[0]);
    parts.push(`Test case ${tc.id}: ${tc.title} (${tc.type}).`);
  } else if (/test case|product search/.test(lower) && flowIdMatch) {
    audit.push({ tool: "get_flow", args: { id: flowIdMatch[0] }, at: new Date().toISOString() });
    const flow = await getFlow(flowIdMatch[0]);
    parts.push(`Test cases for ${flow.id}: ${flow.testCaseIds.join(", ")}`);
  }

  if (/failed run|last run|needs_review|needs review/.test(lower)) {
    audit.push({ tool: "search_runs", args: {}, at: new Date().toISOString() });
    const runs = await searchRuns("");
    const failed = runs.find((r) => /fail|needs_review|blocked/i.test(r.conclusion || r.status));
    const target = failed || runs[0];
    if (target) {
      links.push({ type: "run", id: target.id });
      audit.push({ tool: "get_run", args: { id: target.id }, at: new Date().toISOString() });
      const detail = await getRun(target.id);
      parts.push(
        `Recent run [[run:${target.id}]]: goal "${target.goal}". Status ${detail.status}, conclusion ${detail.conclusion || "—"}. Flows: ${detail.flowIds.join(", ") || "—"}.`
      );
      if (detail.decisionDiagnostics) {
        const d = detail.decisionDiagnostics as { reason_code?: string; message?: string };
        parts.push(`Diagnostics: ${d.reason_code || "—"} — ${(d.message || "").slice(0, 200)}`);
      }
    }
  }

  if (/evidence/.test(lower)) {
    audit.push({ tool: "search_runs", args: {}, at: new Date().toISOString() });
    const runs = await searchRuns("");
    const target = runMatch ? runs.find((r) => r.id.startsWith(runMatch[0])) : runs[0];
    if (target) {
      audit.push({ tool: "get_evidence", args: { runId: target.id }, at: new Date().toISOString() });
      const ev = await getEvidenceForRun(target.id);
      links.push({ type: "run", id: ev.runId });
      parts.push(
        `Evidence for run [[run:${ev.runId}]]: ${ev.evidence.length} capture(s). ${ev.evidence
          .slice(0, 5)
          .map((e) => e.label || e.path.split("/").pop())
          .join(", ")}`
      );
    }
  }

  if (/define|source file|files define/.test(lower)) {
    const q = flowIdMatch ? flowIdMatch[0] : "product search";
    audit.push({ tool: "search_repository", args: { q }, at: new Date().toISOString() });
    const hits = await searchRepository(q);
    parts.push(
      hits.length
        ? `Repository matches:\n${hits.map((h) => `- ${h.path}:${h.line} ${h.text}`).join("\n")}`
        : "No repository matches in allowed QA paths."
    );
  }

  if (!parts.length) {
    audit.push({ tool: "search_flows", args: { query: message.slice(0, 80) }, at: new Date().toISOString() });
    const flows = await searchFlows(message.slice(0, 80));
    if (flows.length) {
      parts.push(
        `Matching flows: ${flows
          .slice(0, 6)
          .map((f) => `[[flow:${f.id}]] ${f.name} (${f.executable ? "executable" : "blocked"})`)
          .join("\n")}`
      );
      flows.slice(0, 3).forEach((f) => links.push({ type: "flow", id: f.id }));
    } else {
      parts.push(
        "I can help with flows, test cases, runs, evidence, and automation metadata. Try asking which flows are SME-ready, or explain a specific flow ID."
      );
    }
  }

  return { context: parts.join("\n\n"), links };
}
