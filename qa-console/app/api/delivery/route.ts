import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

const LOG = path.join(process.cwd(), "data", "delivery.log.jsonl");

export async function GET() {
  try {
    const raw = await fs.readFile(LOG, "utf8");
    const entries = raw
      .trim()
      .split("\n")
      .filter(Boolean)
      .map((line) => JSON.parse(line))
      .reverse()
      .slice(0, 30);
    return NextResponse.json({ entries });
  } catch {
    return NextResponse.json({ entries: [] });
  }
}
