import { spawn } from "child_process";
import path from "path";
import type { AgentRun, KnowledgePill, TraceEvent } from "@/lib/types";
import { uid } from "@/lib/utils";

const REPO_ROOT = path.resolve(process.cwd(), "..");
const LOCAL_AGENT_URL = process.env.LOCAL_AGENT_URL || "http://127.0.0.1:43124";

function extractPills(pills: KnowledgePill[]) {
  return pills.map((p) => {
    const extracted: Record<string, unknown> = {
      format: p.format,
      chars: p.content.length,
      tags: p.tags,
    };
    if (p.format === "json") {
      try {
        extracted.json = JSON.parse(p.content);
      } catch {
        extracted.parse_error = true;
      }
    }
    if (p.format === "csv") {
      const lines = p.content.trim().split(/\r?\n/);
      extracted.rows = Math.max(0, lines.length - 1);
      extracted.headers = lines[0]?.split(",").map((h) => h.trim()) || [];
    }
    if (p.format === "url") {
      extracted.urls = p.content
        .split(/\s+/)
        .map((u) => u.trim())
        .filter((u) => /^https?:\/\//i.test(u));
    }
    return { ...p, extracted };
  });
}

async function invokeWarmAgent(goal: string): Promise<{
  ok: boolean;
  result?: Record<string, unknown>;
  error?: string;
  via?: string;
}> {
  try {
    const res = await fetch(`${LOCAL_AGENT_URL}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal }),
      signal: AbortSignal.timeout(45_000),
    });
    if (!res.ok) {
      return { ok: false, error: `warm_agent_http_${res.status}`, via: "warm" };
    }
    const json = (await res.json()) as { ok?: boolean; result?: Record<string, unknown>; error?: string };
    if (!json.ok || !json.result) {
      return { ok: false, error: json.error || "warm_agent_bad_payload", via: "warm" };
    }
    return { ok: true, result: json.result, via: "warm" };
  } catch (e) {
    return {
      ok: false,
      error: e instanceof Error ? e.message : String(e),
      via: "warm",
    };
  }
}

async function invokePythonAgentSpawn(goal: string): Promise<{
  ok: boolean;
  result?: Record<string, unknown>;
  error?: string;
  via?: string;
}> {
  return new Promise((resolve) => {
    const py = spawn(
      "python3",
      ["-m", "base_agent.api", goal, "--kb-dir", "discovery/uat_ea/kb"],
      {
        cwd: REPO_ROOT,
        env: {
          ...process.env,
          LLM_ENABLED: "false",
          PYTHONPATH: path.join(REPO_ROOT, "src") + ":" + REPO_ROOT,
        },
      }
    );
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      py.kill("SIGKILL");
      resolve({ ok: false, error: "spawn_timeout", via: "spawn" });
    }, 60_000);
    py.stdout.on("data", (d) => {
      stdout += d.toString();
    });
    py.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    py.on("error", (err) => {
      clearTimeout(timer);
      resolve({ ok: false, error: err.message, via: "spawn" });
    });
    py.on("close", (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        resolve({ ok: false, error: stderr || `exit ${code}`, via: "spawn" });
        return;
      }
      try {
        const jsonStart = stdout.indexOf("{");
        const parsed = JSON.parse(jsonStart >= 0 ? stdout.slice(jsonStart) : stdout);
        resolve({ ok: true, result: parsed, via: "spawn" });
      } catch {
        resolve({ ok: false, error: "Failed to parse agent JSON", result: { raw: stdout }, via: "spawn" });
      }
    });
  });
}

async function invokePythonAgent(goal: string) {
  const warm = await invokeWarmAgent(goal);
  if (warm.ok) return warm;
  return invokePythonAgentSpawn(goal);
}

export async function executeRun(
  run: AgentRun,
  pills: KnowledgePill[],
  onUpdate: (run: AgentRun) => Promise<void>
): Promise<AgentRun> {
  const push = async (kind: TraceEvent["kind"], message: string, detail?: string) => {
    run.traces.push({
      id: uid("tr"),
      at: new Date().toISOString(),
      kind,
      message,
      detail,
    });
    run.updatedAt = new Date().toISOString();
    await onUpdate({ ...run, traces: [...run.traces] });
  };

  run.status = "running";
  await onUpdate(run);
  await push("info", "Run accepted — local deterministic control plane (LLM off by default)");

  const extracted = extractPills(pills);
  run.knowledgePillIds = extracted.map((p) => p.id);
  if (extracted.length) {
    await push(
      "info",
      `Extracted ${extracted.length} context packet(s) before automation`,
      JSON.stringify(
        extracted.map((p) => ({ id: p.id, title: p.title, extracted: p.extracted })),
        null,
        2
      )
    );
  } else {
    await push("info", "No context packets attached — proceeding with KB + rules");
  }

  await push("decision", "Route skill deterministically (no LLM kernel)");
  await push("tool", `Goal → ${run.goal.slice(0, 100)}`);

  const agentGoal =
    run.type === "sanity"
      ? run.goal.includes("sanity") || run.goal.includes("health")
        ? run.goal
        : `sanity check ${run.goal}`
      : run.goal;

  await push("tool", "Invoking local Base Agent", agentGoal);
  const invoked = await invokePythonAgent(agentGoal);
  await push("info", `Agent bridge via ${invoked.via || "unknown"}`);

  if (invoked.ok && invoked.result) {
    const r = invoked.result;
    run.conclusion = String(r.conclusion || "UNKNOWN");
    run.reasonCode = String(r.reason_code || "");
    run.usage.toolCalls = Number(r.tool_calls || 0);
    run.usage.steps = Number(r.steps || 0);
    run.usage.llmCalls = Number(r.llm_calls || 0);
    run.usage.tokensIn = Number(r.tokens_in || 0);
    run.usage.tokensOut = Number(r.tokens_out || 0);
    const local = (r.local as Record<string, unknown> | undefined) || undefined;
    await push(
      "observe",
      `Observation complete → ${run.conclusion}`,
      JSON.stringify({ reason: run.reasonCode, local }, null, 2)
    );
    await push("decision", "Complete — no loop-until-success");
  } else {
    run.conclusion = "UNKNOWN";
    run.reasonCode = "console.agent_bridge_fallback";
    run.usage = {
      tokensIn: 0,
      tokensOut: 0,
      toolCalls: 0,
      steps: 1,
      llmCalls: 0,
    };
    await push(
      "error",
      "Local agent bridge failed — start scripts/local_agent_server.py for fast path",
      invoked.error
    );
  }

  const md = [
    `# QA Agent Report`,
    ``,
    `- **Run ID:** ${run.id}`,
    `- **Type:** ${run.type}`,
    `- **Goal:** ${run.goal}`,
    `- **Conclusion:** ${run.conclusion}`,
    `- **Reason:** ${run.reasonCode || "n/a"}`,
    `- **Model mode:** deterministic (LLM off unless gateway enabled)`,
    `- **Tool calls:** ${run.usage.toolCalls} · **Steps:** ${run.usage.steps} · **LLM calls:** ${run.usage.llmCalls}`,
    `- **Tokens:** in ${run.usage.tokensIn} / out ${run.usage.tokensOut}`,
    ``,
    `## Context packets`,
    extracted.length
      ? extracted.map((p) => `- **${p.title}** (\`${p.format}\`) — ${p.content.slice(0, 120)}…`).join("\n")
      : "_None attached_",
    ``,
    `## Trace`,
    ...run.traces.map((t) => `- \`${t.at}\` **${t.kind}** — ${t.message}`),
    ``,
    `## Policy`,
    `- No loop-until-success`,
    `- Business PASS/FAIL requires approved Ground Truth`,
    `- Technical failures use deterministic rules`,
  ].join("\n");

  run.report = {
    summary: `${run.conclusion}: ${run.goal}`,
    markdown: md,
    json: {
      runId: run.id,
      conclusion: run.conclusion,
      reasonCode: run.reasonCode,
      usage: run.usage,
      traces: run.traces,
      knowledgePillIds: run.knowledgePillIds,
      agent: invoked.result || null,
      bridgeError: invoked.error || null,
      bridgeVia: invoked.via || null,
    },
  };

  await push("report", "Report generated");
  run.status =
    run.conclusion === "FAIL"
      ? "failed"
      : run.conclusion === "BLOCKED"
        ? "blocked"
        : "completed";
  run.updatedAt = new Date().toISOString();
  await onUpdate(run);
  return run;
}
