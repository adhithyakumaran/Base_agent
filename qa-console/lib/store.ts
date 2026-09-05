import { promises as fs } from "fs";
import path from "path";
import type { AppState, HistoryItem } from "@/lib/types";
import { MODEL_OPTIONS } from "@/lib/types";
import { TEST_REPORT_EMAIL, TEST_REPORT_WHATSAPP } from "@/lib/notify";
import { uid } from "@/lib/utils";

const DATA_DIR = path.join(process.cwd(), "data");
const STATE_FILE = path.join(DATA_DIR, "state.json");

const defaultState = (): AppState => ({
  runs: [],
  knowledge: [],
  history: [
    {
      id: uid("hist"),
      at: new Date().toISOString(),
      action: "Command center online",
      actor: "system",
      meta: { note: "Enterprise QA console ready for demo" },
    },
  ],
  schedule: {
    enabled: true,
    timeLocal: "08:00",
    timezone: "Asia/Kolkata",
    goal: "sanity check endless aisle login and home modules",
    channels: ["email", "whatsapp"],
  },
  channels: {
    email: [TEST_REPORT_EMAIL],
    teamsWebhook: process.env.TEAMS_WEBHOOK_URL || "",
    whatsapp: TEST_REPORT_WHATSAPP,
    slackWebhook: "",
  },
  selectedModel: MODEL_OPTIONS.find((m) => m.id === "groq/llama-3.3-70b-versatile")?.id || "groq/llama-3.3-70b-versatile",
  usageTotal: { tokensIn: 0, tokensOut: 0, runs: 0 },
});

function migrate(state: AppState): AppState {
  const placeholder = "qa-lead@client.example";
  state.channels = {
    email: [TEST_REPORT_EMAIL],
    teamsWebhook: state.channels?.teamsWebhook || process.env.TEAMS_WEBHOOK_URL || "",
    whatsapp: TEST_REPORT_WHATSAPP,
    slackWebhook: state.channels?.slackWebhook || "",
    ...((state.channels?.email && !state.channels.email.includes(placeholder)
      ? { email: state.channels.email }
      : {}) as Partial<AppState["channels"]>),
    ...(state.channels?.whatsapp && state.channels.whatsapp.replace(/\D/g, "").length >= 10
      ? { whatsapp: state.channels.whatsapp }
      : {}),
  };
  // Force demo test targets unless explicitly customized away from empty
  if (!state.channels.email?.length || state.channels.email.includes(placeholder)) {
    state.channels.email = [TEST_REPORT_EMAIL];
  }
  if (!state.channels.whatsapp || state.channels.whatsapp.replace(/\D/g, "").length < 10) {
    state.channels.whatsapp = TEST_REPORT_WHATSAPP;
  }
  if (!state.schedule.channels?.includes("whatsapp")) {
    state.schedule.channels = Array.from(new Set([...(state.schedule.channels || []), "email", "whatsapp"]));
  }
  return state;
}

export async function readState(): Promise<AppState> {
  await fs.mkdir(DATA_DIR, { recursive: true });
  try {
    const raw = JSON.parse(await fs.readFile(STATE_FILE, "utf8")) as Partial<AppState>;
    const base = defaultState();
    const merged: AppState = {
      ...base,
      ...raw,
      channels: { ...base.channels, ...(raw.channels || {}) },
      schedule: { ...base.schedule, ...(raw.schedule || {}) },
      usageTotal: { ...base.usageTotal, ...(raw.usageTotal || {}) },
      runs: raw.runs || [],
      knowledge: raw.knowledge || [],
      history: raw.history || base.history,
    };
    return migrate(merged);
  } catch {
    const s = defaultState();
    await fs.writeFile(STATE_FILE, JSON.stringify(s, null, 2));
    return s;
  }
}

export async function writeState(state: AppState): Promise<void> {
  await fs.mkdir(DATA_DIR, { recursive: true });
  await fs.writeFile(STATE_FILE, JSON.stringify(state, null, 2));
}

export async function mutateState(fn: (s: AppState) => void | Promise<void>): Promise<AppState> {
  const state = await readState();
  await fn(state);
  await writeState(state);
  return state;
}

export function pushHistory(
  state: AppState,
  action: string,
  actor = "client",
  meta?: Record<string, unknown>
) {
  const item: HistoryItem = {
    id: uid("hist"),
    at: new Date().toISOString(),
    action,
    actor,
    meta,
  };
  state.history = [item, ...state.history].slice(0, 200);
  return item;
}

export function hasActiveRun(state: AppState): boolean {
  return state.runs.some((r) => r.status === "running" || r.status === "queued");
}
