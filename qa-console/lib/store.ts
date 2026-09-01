import { promises as fs } from "fs";
import path from "path";
import type { AppState, HistoryItem } from "@/lib/types";
import { MODEL_OPTIONS } from "@/lib/types";
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
      action: "Console initialized",
      actor: "system",
      meta: { note: "Enterprise QA console ready" },
    },
  ],
  schedule: {
    enabled: true,
    timeLocal: "08:00",
    timezone: "Asia/Kolkata",
    goal: "sanity check endless aisle morning health",
    channels: ["email"],
  },
  channels: {
    email: ["qa-lead@client.example"],
    teamsWebhook: "",
    whatsapp: "",
    slackWebhook: "",
  },
  selectedModel: MODEL_OPTIONS[0].id,
  usageTotal: { tokensIn: 0, tokensOut: 0, runs: 0 },
});

export async function readState(): Promise<AppState> {
  await fs.mkdir(DATA_DIR, { recursive: true });
  try {
    const raw = await fs.readFile(STATE_FILE, "utf8");
    return { ...defaultState(), ...JSON.parse(raw) } as AppState;
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
