import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { repoRoot } from "@/lib/repo-root";

const REPO = repoRoot();

async function readSession(runId: string): Promise<Record<string, unknown>> {
  const metaPath = path.join(REPO, "reports", "browser-profiles", runId, "session.json");
  try {
    const raw = await fs.readFile(metaPath, "utf8");
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return { run_id: runId, status: "UNKNOWN" };
  }
}

export async function POST(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const profileDir = path.join(REPO, "reports", "browser-profiles", id);
  const signal = path.join(profileDir, "close.signal");
  const session = await readSession(id);
  if (session.status === "CLOSED") {
    return NextResponse.json({ ok: true, run_id: id, status: "CLOSED", idempotent: true });
  }
  await fs.mkdir(profileDir, { recursive: true });
  await fs.writeFile(signal, new Date().toISOString(), "utf8");
  return NextResponse.json({ ok: true, run_id: id, status: "CLOSE_REQUESTED" });
}
