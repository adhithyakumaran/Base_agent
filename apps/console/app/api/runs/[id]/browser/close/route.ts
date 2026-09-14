import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { repoRoot } from "@/lib/repo-root";

const REPO = repoRoot();

export async function POST(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const signal = path.join(REPO, "reports", "browser-profiles", id, "close.signal");
  await fs.mkdir(path.dirname(signal), { recursive: true });
  await fs.writeFile(signal, new Date().toISOString(), "utf8");
  return NextResponse.json({ ok: true, run_id: id, status: "CLOSE_REQUESTED" });
}
