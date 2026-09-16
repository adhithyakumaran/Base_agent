import type { AgentRun } from "@/lib/types";

export type AgentInsights = {
  executionMode?: string;
  capability?: string;
  confidence?: number;
  reasoning?: string;
  suiteTopic?: string;
  flowIds?: string[];
  supportingFlows?: string[];
  suiteIds?: string[];
  commands?: string[];
  discoverySuggestions?: string[];
  automationSuggestions?: string[];
  evidence?: { path: string; label?: string; dom_path?: string }[];
  findings?: { severity: string; code: string; message: string }[];
  executor?: string;
  classifier?: string;
  decision?: {
    action?: string;
    source?: string;
    confidence?: number;
    iteration?: number;
    recoveryCount?: number;
    reason?: string;
  };
};

export function parseInsights(run: AgentRun | null): AgentInsights {
  if (!run?.report?.json) return {};
  const agent = run.report.json.agent as Record<string, unknown> | null | undefined;
  const local = (agent?.local as Record<string, unknown>) || {};
  const intent = (local.intent as Record<string, unknown>) || {};
  const suite = (local.suite_plan as Record<string, unknown>) || {};
  const discovery = (local.discovery as Record<string, unknown>) || {};
  const validation = (local.validation as Record<string, unknown>) || {};
  const execution = (local.execution as Record<string, unknown>) || {};
  const state = (local.state as Record<string, unknown>) || {};
  const findings = Array.isArray(validation.findings)
    ? (validation.findings as { severity: string; code: string; message: string }[])
    : [];

  const evidence: AgentInsights["evidence"] = [];
  const observations = Array.isArray(execution.observations)
    ? (execution.observations as { meta?: { evidence?: AgentInsights["evidence"] } }[])
    : [];
  for (const obs of observations) {
    for (const ev of obs.meta?.evidence || []) {
      evidence.push(ev);
    }
  }

  const discoverySuggestions = Array.isArray(discovery.suggestions)
    ? discovery.suggestions.map(String)
    : [];
  const automationSuggestions = discoverySuggestions.filter(
    (s) => s.includes("automation") || s.includes("Playwright") || s.includes("Browser Recorder")
  );

  const journal = Array.isArray(state.decision_journal)
    ? (state.decision_journal as Record<string, unknown>[])
    : [];
  const lastDecision = journal[journal.length - 1];

  return {
    executionMode: String(intent.execution_mode || ""),
    capability: intent.capability ? String(intent.capability) : undefined,
    confidence: typeof intent.confidence === "number" ? intent.confidence : undefined,
    reasoning: intent.reasoning ? String(intent.reasoning) : undefined,
    suiteTopic: intent.suite_topic ? String(intent.suite_topic) : undefined,
    flowIds: Array.isArray(intent.flow_ids) ? intent.flow_ids.map(String) : [],
    supportingFlows: Array.isArray(intent.supporting_flow_ids)
      ? intent.supporting_flow_ids.map(String)
      : [],
    suiteIds: Array.isArray(suite.suite_ids) ? suite.suite_ids.map(String) : [],
    commands: Array.isArray(suite.commands) ? suite.commands.map(String) : [],
    discoverySuggestions,
    automationSuggestions,
    evidence: evidence.slice(0, 24),
    findings,
    executor: local.executor ? String(local.executor) : undefined,
    classifier: local.classifier ? String(local.classifier) : undefined,
    decision: lastDecision
      ? {
          action: String(lastDecision.decision || lastDecision.final_action || ""),
          source: String(lastDecision.source || lastDecision.decision_source || ""),
          confidence:
            typeof lastDecision.confidence === "number" ? lastDecision.confidence : undefined,
          iteration: typeof state.iteration === "number" ? state.iteration : undefined,
          recoveryCount: typeof state.recovery_count === "number" ? state.recovery_count : undefined,
          reason: lastDecision.reason ? String(lastDecision.reason) : undefined,
        }
      : undefined,
  };
}

export function greetingForHour(date = new Date()) {
  const hour = date.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}
