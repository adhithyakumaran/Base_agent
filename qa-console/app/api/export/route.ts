import { NextResponse } from "next/server";
import { readState } from "@/lib/store";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const format = (searchParams.get("format") || "json").toLowerCase();
  const runId = searchParams.get("runId");
  const state = await readState();
  const run = runId ? state.runs.find((r) => r.id === runId) : state.runs[0];
  if (!run?.report) {
    return NextResponse.json({ error: "No report available" }, { status: 404 });
  }

  if (format === "md" || format === "markdown") {
    return new NextResponse(run.report.markdown, {
      headers: {
        "Content-Type": "text/markdown; charset=utf-8",
        "Content-Disposition": `attachment; filename="${run.id}.md"`,
      },
    });
  }
  if (format === "txt") {
    return new NextResponse(run.report.summary + "\n\n" + run.report.markdown, {
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Disposition": `attachment; filename="${run.id}.txt"`,
      },
    });
  }
  if (format === "csv") {
    const rows = [
      ["field", "value"],
      ["run_id", run.id],
      ["conclusion", run.conclusion || ""],
      ["reason", run.reasonCode || ""],
      ["goal", run.goal],
      ["tokens_in", String(run.usage.tokensIn)],
      ["tokens_out", String(run.usage.tokensOut)],
      ["llm_calls", String(run.usage.llmCalls)],
    ];
    const csv = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
    return new NextResponse(csv, {
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": `attachment; filename="${run.id}.csv"`,
      },
    });
  }

  return new NextResponse(JSON.stringify(run.report.json, null, 2), {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Content-Disposition": `attachment; filename="${run.id}.json"`,
    },
  });
}
