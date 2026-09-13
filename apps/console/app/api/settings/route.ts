import { NextResponse } from "next/server";
import { requireApiAuth, requireMutationAuth } from "@/lib/api-auth";
import { mutateState, pushHistory, readState } from "@/lib/store";

export async function GET(req: Request) {
  const denied = requireApiAuth(req);
  if (denied) return denied;

  const state = await readState();
  return NextResponse.json({ schedule: state.schedule, channels: state.channels });
}

export async function PUT(req: Request) {
  const denied = requireMutationAuth(req);
  if (denied) return denied;
  const body = await req.json();
  const state = await mutateState((s) => {
    if (body.schedule) {
      s.schedule = { ...s.schedule, ...body.schedule };
      pushHistory(s, "Updated daily sanity schedule", "client", s.schedule);
    }
    if (body.channels) {
      s.channels = { ...s.channels, ...body.channels };
      pushHistory(s, "Updated report communication channels", "client");
    }
    if (body.selectedModel) {
      s.selectedModel = String(body.selectedModel);
      pushHistory(s, `Selected model ${s.selectedModel}`, "client");
    }
  });
  return NextResponse.json({
    schedule: state.schedule,
    channels: state.channels,
    selectedModel: state.selectedModel,
  });
}
