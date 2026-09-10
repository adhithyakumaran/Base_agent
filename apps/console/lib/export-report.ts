import {
  Document,
  HeadingLevel,
  Packer,
  Paragraph,
  TextRun,
} from "docx";
import { jsPDF } from "jspdf";
import { parseReportMarkdown } from "./markdown-format";

export { markdownToPlainLines, markdownToPlainText } from "./markdown-format";

export async function buildDocxBuffer(title: string, markdown: string): Promise<Buffer> {
  const blocks = parseReportMarkdown(markdown);
  const children: Paragraph[] = [
    new Paragraph({
      children: [new TextRun({ text: title, font: "Calibri", bold: true, size: 32 })],
      heading: HeadingLevel.HEADING_1,
    }),
    new Paragraph({
      children: [
        new TextRun({
          text: `Generated ${new Date().toLocaleString()}`,
          font: "Calibri",
          italics: true,
          size: 20,
          color: "525252",
        }),
      ],
    }),
    new Paragraph({ text: "" }),
  ];

  for (const block of blocks) {
    if (block.type === "h1") {
      children.push(
        new Paragraph({
          children: [new TextRun({ text: block.text, font: "Calibri", bold: true, size: 28 })],
          heading: HeadingLevel.HEADING_1,
        })
      );
      continue;
    }
    if (block.type === "h2") {
      children.push(
        new Paragraph({
          children: [new TextRun({ text: block.text, font: "Calibri", bold: true, size: 24 })],
          heading: HeadingLevel.HEADING_2,
        })
      );
      continue;
    }
    if (block.type === "h3") {
      children.push(
        new Paragraph({
          children: [new TextRun({ text: block.text, font: "Calibri", bold: true, size: 22 })],
          heading: HeadingLevel.HEADING_3,
        })
      );
      continue;
    }
    if (block.type === "img") {
      continue;
    }
    const prefix = block.type === "li" ? "• " : "";
    children.push(
      new Paragraph({
        children: [new TextRun({ text: `${prefix}${block.text}`, font: "Calibri", size: 22 })],
      })
    );
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

  doc.setTextColor(10, 10, 10);

  for (const block of parseReportMarkdown(markdown)) {
    if (block.type === "img") {
      continue;
    }
    if (block.type === "h1") {
      doc.setFont("helvetica", "bold");
      doc.setFontSize(14);
    } else if (block.type === "h2") {
      doc.setFont("helvetica", "bold");
      doc.setFontSize(12);
      y += 6;
    } else if (block.type === "h3") {
      doc.setFont("helvetica", "bold");
      doc.setFontSize(11);
    } else {
      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
    }

    const text = block.type === "li" ? `• ${block.text}` : block.text;
    const wrapped = doc.splitTextToSize(text, pageWidth);
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
