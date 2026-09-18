import { NextResponse } from "next/server";
import { requireRunAccess } from "@/lib/api-auth";
import { fetchInternalAgent } from "@/lib/internal-agent";

export async function GET(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const denied = await requireRunAccess(req, id);
  if (denied) return denied;

  try {
    const res = await fetchInternalAgent(`/agent/${encodeURIComponent(id)}`, { cache: "no-store" });
    const body = await res.json();
    if (!res.ok) {
      return NextResponse.json(body, { status: res.status === 404 ? 404 : 502 });
    }
    return NextResponse.json(body);
  } catch (e) {
    return NextResponse.json(
      { ok: false, error: e instanceof Error ? e.message : "agent_unreachable" },
      { status: 503 }
    );
  }
}
