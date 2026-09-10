import { NextResponse } from "next/server";
import { readState } from "@/lib/store";

export async function GET(_: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const state = await readState();
  const run = state.runs.find((r) => r.id === id);
  if (!run) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json({ run });
}
