import { parseReportMarkdown } from "@/lib/markdown-format";

type EvidenceItem = { path: string; label?: string; dom_path?: string };

export function ReportPreview({
  markdown,
  evidence,
}: {
  markdown: string;
  evidence?: EvidenceItem[];
}) {
  const blocks = parseReportMarkdown(markdown.slice(0, 6000));

  return (
    <div className="scout-report-rendered">
      {blocks.map((block, index) => {
        if (block.type === "h1") {
          return (
            <h1 key={index} className="scout-report-h1">
              {block.text}
            </h1>
          );
        }
        if (block.type === "h2") {
          return (
            <h2 key={index} className="scout-report-h2">
              {block.text}
            </h2>
          );
        }
        if (block.type === "h3") {
          return (
            <h3 key={index} className="scout-report-h3">
              {block.text}
            </h3>
          );
        }
        if (block.type === "li") {
          return (
            <p key={index} className="scout-report-li">
              {block.text}
            </p>
          );
        }
        if (block.type === "img") {
          return (
            // eslint-disable-next-line @next/next/no-img-element
            <img key={index} src={block.src} alt={block.alt} className="scout-report-img" />
          );
        }
        return (
          <p key={index} className="scout-report-p">
            {block.text}
          </p>
        );
      })}
      {evidence && evidence.length > 0 && (
        <div className="scout-evidence-grid" style={{ marginTop: "1rem" }}>
          {evidence.slice(0, 4).map((ev) => (
            <figure key={ev.path} className="scout-evidence-card">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/api/evidence?path=${encodeURIComponent(ev.path)}`} alt={ev.label || "evidence"} />
              <figcaption>{ev.label || ev.path.split("/").pop()}</figcaption>
            </figure>
          ))}
        </div>
      )}
    </div>
  );
}
