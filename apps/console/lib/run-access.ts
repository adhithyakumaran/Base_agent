import { promises as fs } from "fs";
import path from "path";
import { repoRoot } from "@/lib/repo-root";
import { readState } from "@/lib/store";

const REPO = repoRoot();

export async function assertRunAccessible(runId: string): Promise<boolean> {
  if (!runId || runId.includes("..") || runId.includes("/")) return false;
  const state = await readState();
  if (state.runs.some((r) => r.id === runId)) return true;

  const liveEvents = path.join(REPO, "reports", "live-events", `${runId}.jsonl`);
  const evidenceDir = path.join(REPO, "reports", "evidence", runId);
  const profileDir = path.join(REPO, "reports", "browser-profiles", runId);
  for (const candidate of [liveEvents, evidenceDir, profileDir]) {
    try {
      await fs.access(candidate);
      return true;
    } catch {
      /* continue */
    }
  }
  return false;
}

export async function assertEvidencePathAllowed(rel: string, runIdHint?: string | null): Promise<boolean> {
  if (!rel || rel.includes("..")) return false;
  const normalized = rel.replace(/\\/g, "/");
  const evidenceMatch = normalized.match(/reports\/evidence\/([^/]+)\//);
  const runFromPath = evidenceMatch?.[1];
  const runId = runIdHint || runFromPath;
  if (!runId) return false;
  if (runFromPath && runIdHint && runFromPath !== runIdHint) return false;
  return assertRunAccessible(runId);
}
