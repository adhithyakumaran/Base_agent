import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

export async function GET(req: Request) {
  const rel = new URL(req.url).searchParams.get("path");
  if (!rel || rel.includes("..")) {
    return NextResponse.json({ error: "Invalid path" }, { status: 400 });
  }

  const automationCandidates = [
    path.resolve(process.cwd(), "..", "apps", "automation"),
    path.resolve(process.cwd(), "..", "automation"),
  ];
  let automationRoot = automationCandidates[0];
  for (const candidate of automationCandidates) {
    try {
      await fs.access(candidate);
      automationRoot = candidate;
      break;
    } catch {
      /* try next */
    }
  }

  const file = path.resolve(automationRoot, rel);
  if (!file.startsWith(automationRoot)) {
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
