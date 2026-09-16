import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { requireApiAuth } from "@/lib/api-auth";
import { assertEvidencePathAllowed } from "@/lib/run-access";
import { repoRoot } from "@/lib/repo-root";

export async function GET(req: Request) {
  const denied = requireApiAuth(req);
  if (denied) return denied;
  const url = new URL(req.url);
  const rel = url.searchParams.get("path");
  const runId = url.searchParams.get("runId");
  if (!rel || rel.includes("..")) {
    return NextResponse.json({ error: "Invalid path" }, { status: 400 });
  }

  const allowed = await assertEvidencePathAllowed(rel, runId);
  if (!allowed) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const root = repoRoot();
  const automationCandidates = [
    path.join(root, "apps", "automation"),
    path.join(root, "automation"),
    root,
  ];
  let baseRoot = automationCandidates[0];
  for (const candidate of automationCandidates) {
    try {
      await fs.access(candidate);
      baseRoot = candidate;
      break;
    } catch {
      /* try next */
    }
  }

  const file = path.resolve(baseRoot, rel);
  const reportsRoot = path.resolve(root, "reports");
  const automationRoot = path.resolve(baseRoot);
  if (!file.startsWith(reportsRoot) && !file.startsWith(automationRoot)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }
  try {
    const data = await fs.readFile(file);
    const ext = path.extname(file).toLowerCase();
    const type =
      ext === ".png"
        ? "image/png"
        : ext === ".html"
          ? "text/html"
          : ext === ".json"
            ? "application/json"
            : "application/octet-stream";
    return new NextResponse(data, { headers: { "Content-Type": type, "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
}
