export type ReportBlock =
  | { type: "h1"; text: string }
  | { type: "h2"; text: string }
  | { type: "h3"; text: string }
  | { type: "p"; text: string }
  | { type: "li"; text: string }
  | { type: "code"; text: string }
  | { type: "img"; src: string; alt: string };

/** Strip markdown to clean plain text (no stray * or ` artifacts). */
export function markdownToPlainText(markdown: string): string {
  return parseReportMarkdown(markdown)
    .map((block) => {
      if (block.type === "h1") return block.text.toUpperCase();
      if (block.type === "h2") return `\n${block.text}\n`;
      if (block.type === "h3") return block.text;
      if (block.type === "li") return `• ${block.text}`;
      if (block.type === "code") return block.text;
      if (block.type === "img") return `[image: ${block.alt}]`;
      return block.text;
    })
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function markdownToPlainLines(markdown: string): string[] {
  return markdownToPlainText(markdown)
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function cleanInline(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/_([^_]+)_/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

/** Parse markdown into structured blocks for HTML preview and export. */
export function parseReportMarkdown(markdown: string): ReportBlock[] {
  const blocks: ReportBlock[] = [];
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) continue;

    if (line.startsWith("### ")) {
      blocks.push({ type: "h3", text: cleanInline(line.slice(4)) });
      continue;
    }
    if (line.startsWith("## ")) {
      blocks.push({ type: "h2", text: cleanInline(line.slice(3)) });
      continue;
    }
    if (line.startsWith("# ")) {
      blocks.push({ type: "h1", text: cleanInline(line.slice(2)) });
      continue;
    }
    if (/^\d+\.\s+/.test(line)) {
      blocks.push({ type: "li", text: cleanInline(line.replace(/^\d+\.\s+/, "")) });
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      blocks.push({ type: "li", text: cleanInline(line.replace(/^[-*]\s+/, "")) });
      continue;
    }
    if (line.startsWith("```")) continue;

    blocks.push({ type: "p", text: cleanInline(line) });
  }

  return blocks;
}
