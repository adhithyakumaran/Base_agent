import { NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";
import { repoRoot } from "@/lib/repo-root";

const REPO = repoRoot();
const SCRIPT = path.join(REPO, "scripts", "browser_recorder.py");

function pythonBin() {
  return process.platform === "win32" ? "python" : "python3";
}

function runPython(args: string[]): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const proc = spawn(pythonBin(), [SCRIPT, ...args], {
      cwd: REPO,
      env: {
        ...process.env,
        PYTHONPATH: [
          path.join(REPO, "services", "agent-runtime"),
          path.join(REPO, "services", "qa-orchestrator"),
          REPO,
        ].join(path.delimiter),
      },
    });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d) => {
      stdout += d.toString();
    });
    proc.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    proc.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(stderr || `recorder exit ${code}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout.trim()));
      } catch {
        reject(new Error("Invalid recorder JSON"));
      }
    });
  });
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const sessionId = url.searchParams.get("sessionId") || "scout-default";
  const offset = url.searchParams.get("offset");

  if (offset != null) {
    try {
      const events = await runPython(["events", "--session-id", sessionId, "--offset", offset]);
      return NextResponse.json(events);
    } catch (e) {
      return NextResponse.json({ events: [], error: e instanceof Error ? e.message : String(e) });
    }
  }

  try {
    const status = await runPython(["status", "--session-id", sessionId]);
    return NextResponse.json({ status });
  } catch (e) {
    return NextResponse.json(
      { status: { session_id: sessionId, status: "idle" }, error: e instanceof Error ? e.message : String(e) },
      { status: 200 }
    );
  }
}

export async function PUT(req: Request) {
  const body = await req.json();
  const sessionId = String(body.sessionId || "scout-default");
  const config = body.config || {};
  try {
    const result = await runPython([
      "configure",
      "--session-id",
      sessionId,
      "--config-json",
      JSON.stringify(config),
    ]);
    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 500 });
  }
}

export async function POST(req: Request) {
  const body = await req.json();
  const sessionId = String(body.sessionId || "scout-default");
  const maxSeconds = Number(body.maxSeconds || 30);
  const config = body.config || {};
  try {
    await runPython(["configure", "--session-id", sessionId, "--config-json", JSON.stringify(config)]);
    const result = await runPython([
      "record",
      "--session-id",
      sessionId,
      "--max-seconds",
      String(maxSeconds),
    ]);
    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 500 });
  }
}
