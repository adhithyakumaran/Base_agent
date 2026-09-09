import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

const AUTOMATION = path.resolve(process.cwd(), "..", "automation");

export async function GET(req: Request) {
  const rel = new URL(req.url).searchParams.get("path");
  if (!rel || rel.includes("..")) {
    return NextResponse.json({ error: "Invalid path" }, { status: 400 });
  }
  const file = path.resolve(AUTOMATION, rel);
  if (!file.startsWith(AUTOMATION)) {
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
