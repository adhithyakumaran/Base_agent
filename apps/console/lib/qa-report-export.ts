import { spawn } from "child_process";
import { mkdtemp, writeFile, rm } from "fs/promises";
import os from "os";
import path from "path";
import type { AgentRun } from "@/lib/types";
import { repoRoot } from "@/lib/repo-root";

export type QaReportFormat = "json" | "html" | "pdf" | "docx" | "bundle";

const BINARY_FORMATS = new Set<QaReportFormat>(["pdf", "docx", "bundle"]);

function pythonBin() {
  return process.platform === "win32" ? "python" : "python3";
}

function pythonPathEnv(root: string) {
  return [
    path.join(root, "services", "agent-runtime"),
    path.join(root, "services", "qa-orchestrator"),
    root,
  ].join(path.delimiter);
}

export function reportContentType(format: QaReportFormat): string {
  switch (format) {
    case "json":
      return "application/json; charset=utf-8";
    case "html":
      return "text/html; charset=utf-8";
    case "pdf":
      return "application/pdf";
    case "docx":
      return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    case "bundle":
      return "application/zip";
    default:
      return "application/octet-stream";
  }
}

export function reportFilename(runId: string, format: QaReportFormat): string {
  const ext = format === "bundle" ? "zip" : format;
  return `qa-report-${runId}.${ext}`;
}

export async function exportCanonicalQaReport(
  runId: string,
  format: QaReportFormat,
  consoleRun: AgentRun
): Promise<Buffer> {
  const root = repoRoot();
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "scout-qa-report-"));
  const runJsonPath = path.join(tmpDir, "run.json");

  try {
    await writeFile(runJsonPath, JSON.stringify(consoleRun), "utf8");
    const args = [
      "-m",
      "qa_orchestrator.qa_report_cli",
      "--run-id",
      runId,
      "--format",
      format,
      "--console-run-json",
      runJsonPath,
      "--repo-root",
      root,
      "--journal-dir",
      path.join(root, "reports", "agent"),
    ];
    const env = {
      ...process.env,
      PYTHONPATH: pythonPathEnv(root),
      QA_ENV: process.env.QA_ENV || "UAT",
    };

    return await new Promise((resolve, reject) => {
      const proc = spawn(pythonBin(), args, {
        cwd: root,
        env,
        stdio: ["ignore", "pipe", "pipe"],
      });
      const chunks: Buffer[] = [];
      const errChunks: Buffer[] = [];
      proc.stdout.on("data", (d: Buffer) => chunks.push(d));
      proc.stderr.on("data", (d: Buffer) => errChunks.push(d));
      proc.on("error", (err) => reject(err));
      proc.on("close", (code) => {
        if (code !== 0) {
          const msg = Buffer.concat(errChunks).toString("utf8") || `exit ${code}`;
          reject(new Error(msg.trim() || `qa_report_cli exit ${code}`));
          return;
        }
        const out = Buffer.concat(chunks);
        if (!BINARY_FORMATS.has(format) && out.length === 0) {
          reject(new Error("Empty report output"));
          return;
        }
        resolve(out);
      });
    });
  } finally {
    await rm(tmpDir, { recursive: true, force: true });
  }
}
