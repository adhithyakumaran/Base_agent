import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { requireApiAuth, requireMutationAuth } from "@/lib/api-auth";
import { repoRoot } from "@/lib/repo-root";

const REPO = repoRoot();
const ENV_PATH = path.join(REPO, "apps", "automation", "config", ".env");

const ALLOWED_KEYS = new Set([
  "EA_BASE_URL",
  "EA_USER_USERNAME",
  "EA_USER_PASSWORD",
  "EA_VALID_ITEM_CODE",
  "EA_HEADLESS",
  "EA_USE_SYSTEM_CHROME",
]);

function parseEnv(raw: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const [key, ...rest] = trimmed.split("=");
    out[key.trim()] = rest.join("=").trim();
  }
  return out;
}

function serializeEnv(values: Record<string, string>, original: string): string {
  const lines = original.split(/\r?\n/);
  const seen = new Set<string>();
  const updated = lines.map((line) => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) return line;
    const key = trimmed.split("=")[0].trim();
    if (!ALLOWED_KEYS.has(key) || !(key in values)) return line;
    seen.add(key);
    return `${key}=${values[key]}`;
  });
  for (const key of ALLOWED_KEYS) {
    if (key in values && !seen.has(key)) {
      updated.push(`${key}=${values[key]}`);
    }
  }
  return updated.join("\n") + "\n";
}

export async function GET(req: Request) {
  const denied = requireApiAuth(req);
  if (denied) return denied;

  try {
    const raw = await fs.readFile(ENV_PATH, "utf8");
    const parsed = parseEnv(raw);
    const safe: Record<string, string> = {};
    for (const key of ALLOWED_KEYS) {
      if (key in parsed) {
        safe[key] = key.includes("PASSWORD") ? "********" : parsed[key];
      }
    }
    return NextResponse.json({ configured: true, keys: Object.keys(safe), values: safe });
  } catch {
    return NextResponse.json({ configured: false, keys: [], values: {} });
  }
}

export async function PUT(req: Request) {
  const denied = requireMutationAuth(req);
  if (denied) return denied;

  const body = await req.json();
  const incoming = body.values || body;
  if (!incoming || typeof incoming !== "object") {
    return NextResponse.json({ error: "values object required" }, { status: 400 });
  }

  let original = "";
  try {
    original = await fs.readFile(ENV_PATH, "utf8");
  } catch {
    original = "";
  }
  const current = parseEnv(original);
  for (const [key, value] of Object.entries(incoming)) {
    if (!ALLOWED_KEYS.has(key)) {
      return NextResponse.json({ error: `key not allowed: ${key}` }, { status: 400 });
    }
    if (typeof value !== "string") {
      return NextResponse.json({ error: `value must be string for ${key}` }, { status: 400 });
    }
    if (key.includes("PASSWORD") && value === "********") continue;
    current[key] = value;
  }

  await fs.mkdir(path.dirname(ENV_PATH), { recursive: true });
  await fs.writeFile(ENV_PATH, serializeEnv(current, original), "utf8");
  return NextResponse.json({ ok: true });
}
