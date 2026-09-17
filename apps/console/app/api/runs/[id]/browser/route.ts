import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { requireRunAccess } from "@/lib/api-auth";
import { repoRoot } from "@/lib/repo-root";

const REPO = repoRoot();

export async function GET(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const denied = await requireRunAccess(req, id);
  if (denied) return denied;
  const metaPath = path.join(REPO, "reports", "browser-profiles", id, "session.json");
  try {
    const raw = await fs.readFile(metaPath, "utf8");
    return NextResponse.json(JSON.parse(raw));
  } catch {
    return NextResponse.json({
      run_id: id,
      status: "UNKNOWN",
      keep_open: process.env.QA_KEEP_BROWSER_OPEN === "true",
      channel: process.env.QA_BROWSER_CHANNEL || "chrome",
    });
  }
}
