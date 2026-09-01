import { NextResponse } from "next/server";
import { mutateState, pushHistory, readState } from "@/lib/store";
import type { KnowledgePill } from "@/lib/types";
import { uid } from "@/lib/utils";

export async function GET() {
  const state = await readState();
  return NextResponse.json({ knowledge: state.knowledge });
}

export async function POST(req: Request) {
  const body = await req.json();
  const title = String(body.title || "Untitled dump").trim();
  const format = (body.format || "text") as KnowledgePill["format"];
  const content = String(body.content || "");
  const tags = Array.isArray(body.tags) ? body.tags.map(String) : [];
  if (!content.trim()) return NextResponse.json({ error: "content required" }, { status: 400 });

  const pill: KnowledgePill = {
    id: uid("pill"),
    title,
    format,
    content,
    createdAt: new Date().toISOString(),
    tags,
  };

  // Extract data pill summary immediately
  const extracted: Record<string, unknown> = { format, length: content.length };
  if (format === "json") {
    try {
      extracted.preview = JSON.parse(content);
    } catch {
      extracted.parse_error = true;
    }
  }
  pill.extracted = extracted;

  await mutateState((state) => {
    state.knowledge = [pill, ...state.knowledge].slice(0, 200);
    pushHistory(state, `Knowledge dump added: ${title}`, "client", { pillId: pill.id, format });
  });

  return NextResponse.json({ pill });
}

export async function DELETE(req: Request) {
  const { searchParams } = new URL(req.url);
  const id = searchParams.get("id");
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });
  await mutateState((state) => {
    state.knowledge = state.knowledge.filter((k) => k.id !== id);
    pushHistory(state, `Knowledge pill removed`, "client", { pillId: id });
  });
  return NextResponse.json({ ok: true });
}
