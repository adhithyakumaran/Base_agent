import { NextResponse } from "next/server";
import { requireApiAuth } from "@/lib/api-auth";
import { runAgentTools, type AgentToolAudit } from "@/lib/agent-chat-tools";

export async function POST(req: Request) {
  const denied = requireApiAuth(req);
  if (denied) return denied;

  const body = await req.json().catch(() => ({}));
  const message = String(body.message || "").trim();
  if (!message) return NextResponse.json({ error: "message required" }, { status: 400 });

  const audit: AgentToolAudit[] = [];
  try {
    const { context, links } = await runAgentTools(message, audit);
    const reply = formatReply(context, links);
    return NextResponse.json({ reply, audit, links });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}

function formatReply(
  context: string,
  links: { type: "flow" | "run"; id: string }[]
): string {
  const intro = context.includes("\n") ? context : `${context}`;
  const linkHints =
    links.length > 0
      ? `\n\nReferences: ${links.map((l) => (l.type === "flow" ? `[[flow:${l.id}]]` : `[[run:${l.id}]]`)).join(" ")}`
      : "";
  return `${intro}${linkHints}`.trim();
}
