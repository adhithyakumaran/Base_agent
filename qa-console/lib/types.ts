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
  { id: "gpt-4o-mini", label: "GPT-4o mini (fast)", role: "fast", provider: "OpenAI API" },
  { id: "gpt-4o", label: "GPT-4o (reasoning)", role: "reasoning", provider: "OpenAI API" },
  { id: "claude-sonnet-4", label: "Claude Sonnet (reasoning)", role: "reasoning", provider: "Anthropic API" },
  { id: "azure-gpt-4o", label: "Azure OpenAI GPT-4o", role: "reasoning", provider: "Azure OpenAI" },
  { id: "oci-cohere-command", label: "OCI Generative AI", role: "fast", provider: "Oracle OCI" },
  { id: "disabled", label: "Deterministic only (LLM off)", role: "fast", provider: "None" },
];

export const PREBUILT_FLOWS = [
  {
    id: "skill.health",
    label: "Morning health pack",
    goal: "health check endless aisle technical readiness",
  },
  {
    id: "skill.login",
    label: "Login readiness",
    goal: "login probe for endless aisle",
  },
  {
    id: "flow.item_sku_search",
    label: "Item SKU search",
    goal: "component probe P6_SKU",
  },
  {
    id: "flow.find_price",
    label: "Find Price",
    goal: "replay flow find_price",
  },
  {
    id: "flow.stock_visibility",
    label: "Stock visibility",
    goal: "component probe P47_SKU",
  },
  {
    id: "flow.standard_product_browse",
    label: "Product browse map",
    goal: "discover standard product browse map",
  },
  {
    id: "skill.report",
    label: "Evidence report",
    goal: "assemble report bundle for endless aisle",
  },
  {
    id: "flow.rivaah_trousseau",
    label: "Rivaah trousseau",
    goal: "replay flow rivaah_trousseau",
  },
];
