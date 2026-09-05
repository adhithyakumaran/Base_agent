import {
  Document,
  HeadingLevel,
  Packer,
  Paragraph,
  TextRun,
} from "docx";
import { jsPDF } from "jspdf";

export function markdownToPlainLines(markdown: string): string[] {
  return markdown
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => line.replace(/^#+\s*/, "").replace(/\*\*/g, "").replace(/`/g, "").trim())
    .filter(Boolean);
}

export async function buildDocxBuffer(title: string, markdown: string): Promise<Buffer> {
  const lines = markdownToPlainLines(markdown);
  const children: Paragraph[] = [
    new Paragraph({
      text: title,
      heading: HeadingLevel.HEADING_1,
    }),
    new Paragraph({
      children: [new TextRun({ text: `Generated ${new Date().toISOString()}`, italics: true })],
    }),
    new Paragraph({ text: "" }),
  ];

  for (const line of lines) {
    children.push(new Paragraph({ text: line.replace(/^##\s*/, "") }));
  }

  const doc = new Document({
    sections: [{ properties: {}, children }],
  });
  return Packer.toBuffer(doc);
}

export async function buildPdfBuffer(title: string, markdown: string): Promise<Buffer> {
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const margin = 48;
  const pageWidth = doc.internal.pageSize.getWidth() - margin * 2;
  let y = margin;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.setTextColor(234, 88, 12);
  const titleLines = doc.splitTextToSize(title, pageWidth);
  doc.text(titleLines, margin, y);
  y += titleLines.length * 20 + 8;

  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(82, 82, 82);
  doc.text(`Generated ${new Date().toLocaleString()}`, margin, y);
  y += 22;

  doc.setFontSize(10);
  doc.setTextColor(10, 10, 10);

  for (const line of markdownToPlainLines(markdown)) {
    const wrapped = doc.splitTextToSize(line, pageWidth);
    const blockHeight = wrapped.length * 13;
    if (y + blockHeight > doc.internal.pageSize.getHeight() - margin) {
      doc.addPage();
      y = margin;
    }
    doc.text(wrapped, margin, y);
    y += blockHeight + 4;
  }

  const arrayBuffer = doc.output("arraybuffer");
  return Buffer.from(arrayBuffer);
}
