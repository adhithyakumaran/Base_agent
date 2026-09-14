import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { repoRoot } from "@/lib/repo-root";

const REPO = repoRoot();

function eventsFile(runId: string) {
  return path.join(REPO, "reports", "live-events", `${runId}.jsonl`);
}

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const file = eventsFile(id);
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      let cursor = 0;
      let idle = 0;
      while (idle < 120) {
        try {
          const raw = await fs.readFile(file, "utf8");
          const lines = raw.split("\n").filter(Boolean);
          for (const line of lines) {
            try {
              const row = JSON.parse(line) as { sequence?: number };
              const seq = Number(row.sequence || 0);
              if (seq <= cursor) continue;
              cursor = seq;
              controller.enqueue(encoder.encode(`data: ${line}\n\n`));
            } catch {
              /* skip */
            }
          }
        } catch {
          /* file may not exist yet */
        }
        idle += 1;
        await new Promise((r) => setTimeout(r, 500));
      }
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
