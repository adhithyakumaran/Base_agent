import { parseReportMarkdown } from "@/lib/markdown-format";

export function ReportPreview({ markdown }: { markdown: string }) {
  const blocks = parseReportMarkdown(markdown.slice(0, 4800));

  return (
    <div className="ea-report-rendered">
      {blocks.map((block, index) => {
        if (block.type === "h1") {
          return (
            <h1 key={index} className="ea-report-h1">
              {block.text}
            </h1>
          );
        }
        if (block.type === "h2") {
          return (
            <h2 key={index} className="ea-report-h2">
              {block.text}
            </h2>
          );
        }
        if (block.type === "h3") {
          return (
            <h3 key={index} className="ea-report-h3">
              {block.text}
            </h3>
          );
        }
        if (block.type === "li") {
          return (
            <p key={index} className="ea-report-li">
              {block.text}
            </p>
          );
        }
        return (
          <p key={index} className="ea-report-p">
            {block.text}
          </p>
        );
      })}
    </div>
  );
}
