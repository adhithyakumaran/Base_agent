import { promises as fs } from "fs";
import path from "path";
import { requireRunAccess } from "@/lib/api-auth";
import { repoRoot } from "@/lib/repo-root";

const REPO = repoRoot();

function eventsFile(runId: string) {
  return path.join(REPO, "reports", "live-events", `${runId}.jsonl`);
}

function sessionFile(runId: string) {
  return path.join(REPO, "reports", "browser-profiles", runId, "session.json");
}

async function readSessionStatus(runId: string): Promise<string | null> {
  try {
    const raw = await fs.readFile(sessionFile(runId), "utf8");
    const parsed = JSON.parse(raw) as { status?: string };
    return parsed.status || null;
  } catch {
    return null;
  }
}

export async function GET(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const denied = await requireRunAccess(req, id);
  if (denied) return denied;
  const file = eventsFile(id);
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      let cursor = 0;
      let idle = 0;
      let lastSize = -1;
      while (idle < 120 && !req.signal.aborted) {
        const sessionStatus = await readSessionStatus(id);
        if (sessionStatus === "CLOSED" || sessionStatus === "BROWSER_DISCONNECTED") {
          controller.enqueue(
            encoder.encode(
              `data: ${JSON.stringify({ phase: "BROWSER", action: "SESSION", status: sessionStatus, run_id: id })}\n\n`
            )
          );
          break;
        }
        try {
          const stat = await fs.stat(file);
          if (stat.size !== lastSize) {
            lastSize = stat.size;
            const raw = await fs.readFile(file, "utf8");
            for (const line of raw.split("\n").filter(Boolean)) {
              try {
                const row = JSON.parse(line) as { sequence?: number };
                const seq = Number(row.sequence || 0);
                if (seq <= cursor) continue;
                cursor = seq;
                controller.enqueue(encoder.encode(`data: ${line}\n\n`));
                idle = 0;
              } catch {
                /* skip */
              }
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
