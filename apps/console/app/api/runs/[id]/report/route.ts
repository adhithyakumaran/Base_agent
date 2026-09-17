import { NextResponse } from "next/server";
import { requireRunAccess } from "@/lib/api-auth";
import {
  exportCanonicalQaReport,
  reportContentType,
  reportFilename,
  type QaReportFormat,
} from "@/lib/qa-report-export";
import { isTerminalRunStatus } from "@/lib/run-resume";
import { readState } from "@/lib/store";

const FORMATS = new Set<QaReportFormat>(["json", "html", "pdf", "docx", "bundle"]);

export async function GET(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const denied = await requireRunAccess(req, id);
  if (denied) return denied;

  const state = await readState();
  const run = state.runs.find((r) => r.id === id);
  if (!run) {
    return NextResponse.json({ error: "not found", run_id: id }, { status: 404 });
  }

  if (!isTerminalRunStatus(run.status)) {
    return NextResponse.json(
      { error: "Report available when execution completes.", run_id: id, status: run.status },
      { status: 409 }
    );
  }

  const { searchParams } = new URL(req.url);
  const rawFormat = (searchParams.get("format") || "html").toLowerCase();
  if (!FORMATS.has(rawFormat as QaReportFormat)) {
    return NextResponse.json({ error: "Invalid format", allowed: [...FORMATS] }, { status: 400 });
  }
  const format = rawFormat as QaReportFormat;

  try {
    const buffer = await exportCanonicalQaReport(id, format, run);
    const filename = reportFilename(id, format);
    const inline = format === "html" && searchParams.get("download") !== "1";
    const disposition = inline ? "inline" : "attachment";

    return new NextResponse(new Uint8Array(buffer), {
      headers: {
        "Content-Type": reportContentType(format),
        "Content-Disposition": `${disposition}; filename="${filename}"`,
        "Cache-Control": "no-store",
        "X-Report-Schema": "qa-report-v1",
      },
    });
  } catch (e) {
    return NextResponse.json(
      {
        error: "Report export failed",
        detail: e instanceof Error ? e.message : String(e),
        run_id: id,
        format,
      },
      { status: 500 }
    );
  }
}
