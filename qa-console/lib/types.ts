export type TraceEvent = {
  id: string;
  at: string;
  kind: "info" | "tool" | "decision" | "observe" | "report" | "error";
  message: string;
  detail?: string;
};

export type AgentRun = {
  id: string;
  createdAt: string;
  updatedAt: string;
  type: "sanity" | "adhoc" | "flow" | "discover" | "scheduled";
  goal: string;
  status: "queued" | "running" | "completed" | "failed" | "blocked";
  conclusion?: string;
  reasonCode?: string;
  model: string;
  llmEnabled: boolean;
  traces: TraceEvent[];
  report?: {
    summary: string;
    markdown: string;
    json: Record<string, unknown>;
  };
  usage: { tokensIn: number; tokensOut: number; toolCalls: number; steps: number; llmCalls: number };
  channelsNotified?: string[];
  knowledgePillIds?: string[];
};

export type KnowledgePill = {
  id: string;
  title: string;
  format: "text" | "markdown" | "json" | "csv" | "url" | "pdf_note";
  content: string;
  createdAt: string;
  tags: string[];
  extracted?: Record<string, unknown>;
};

export type HistoryItem = {
  id: string;
  at: string;
  action: string;
  actor: string;
  meta?: Record<string, unknown>;
};

export type ScheduleConfig = {
  enabled: boolean;
  timeLocal: string; // HH:MM
  timezone: string;
  goal: string;
  channels: string[];
};

export type ChannelConfig = {
  email: string[];
  teamsWebhook: string;
  whatsapp: string;
  slackWebhook: string;
};

export type ModelOption = {
  id: string;
  label: string;
  role: "fast" | "reasoning" | "fallback";
  provider: string;
};

export type AppState = {
  runs: AgentRun[];
  knowledge: KnowledgePill[];
  history: HistoryItem[];
  schedule: ScheduleConfig;
  channels: ChannelConfig;
  selectedModel: string;
  usageTotal: { tokensIn: number; tokensOut: number; runs: number };
};

export const MODEL_OPTIONS: ModelOption[] = [
  { id: "groq/qwen/qwen3.6-27b", label: "Groq Qwen 3.6 27B (fast classify)", role: "fast", provider: "Groq" },
  { id: "groq/openai/gpt-oss-120b", label: "Groq GPT-OSS 120B (reasoning)", role: "reasoning", provider: "Groq" },
  { id: "groq/qwen/qwen3.8-27b", label: "Groq Qwen 3.8 27B (balanced)", role: "reasoning", provider: "Groq" },
  { id: "groq/llama-3.1-8b-instant", label: "Groq Llama 3.1 8B (legacy fast)", role: "fast", provider: "Groq" },
  { id: "claude-sonnet-4-20250514", label: "Claude Sonnet (reasoning)", role: "reasoning", provider: "Anthropic API" },
  { id: "gpt-4o-mini", label: "GPT-4o mini (fast)", role: "fast", provider: "OpenAI API" },
  { id: "gpt-4o", label: "GPT-4o (reasoning)", role: "reasoning", provider: "OpenAI API" },
  { id: "azure-gpt-4o", label: "Azure OpenAI GPT-4o", role: "reasoning", provider: "Azure OpenAI" },
  { id: "oci-cohere-command", label: "OCI Generative AI", role: "fast", provider: "Oracle OCI" },
  { id: "disabled", label: "Deterministic only (LLM off)", role: "fast", provider: "None" },
];

export const PREBUILT_FLOWS = [
  {
    id: "sanity.morning",
    label: "Morning sanity",
    goal: "sanity check endless aisle login and home modules",
  },
  {
    id: "adhoc.find_price",
    label: "Find Price",
    goal: "check find price module on endless aisle",
  },
  {
    id: "adhoc.sku_search",
    label: "Item SKU search",
    goal: "check item sku search on endless aisle",
  },
  {
    id: "adhoc.stock",
    label: "Stock visibility",
    goal: "check stock visibility module",
  },
  {
    id: "adhoc.login",
    label: "Login readiness",
    goal: "verify login page and authentication flow",
  },
];
