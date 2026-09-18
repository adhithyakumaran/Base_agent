import { NextResponse } from "next/server";
import { requireApiAuth } from "@/lib/api-auth";
import { readState } from "@/lib/store";
import { MODEL_OPTIONS, PREBUILT_FLOWS } from "@/lib/types";

export async function GET(req: Request) {
  const denied = requireApiAuth(req);
  if (denied) return denied;
  const state = await readState();
  return NextResponse.json({
    ...state,
    models: MODEL_OPTIONS,
    prebuiltFlows: PREBUILT_FLOWS,
  });
}
