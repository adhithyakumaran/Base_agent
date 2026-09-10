import { NextResponse } from "next/server";
import { readState } from "@/lib/store";
import { MODEL_OPTIONS, PREBUILT_FLOWS } from "@/lib/types";

export async function GET() {
  const state = await readState();
  return NextResponse.json({
    ...state,
    models: MODEL_OPTIONS,
    prebuiltFlows: PREBUILT_FLOWS,
  });
}
