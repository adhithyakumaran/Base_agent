"use client";

import { useMemo, useState, type ReactNode } from "react";
import { Archive, ChevronDown, Download, ExternalLink, FileJson, FileText } from "lucide-react";
import type { AgentRun } from "@/lib/types";
import { isTerminalRunStatus } from "@/lib/run-resume";

type ExportItem = {
  id: string;
  label: string;
  href: string;
  target?: "_blank";
  icon: ReactNode;
};

export function RunReportExport({ run }: { run: AgentRun }) {
  const [open, setOpen] = useState(false);
  const enabled = isTerminalRunStatus(run.status);
  const base = `/api/runs/${encodeURIComponent(run.id)}/report`;

  const items = useMemo<ExportItem[]>(
    () => [
      {
        id: "view",
        label: "View report",
        href: `${base}?format=html`,
        target: "_blank",
        icon: <ExternalLink size={14} aria-hidden />,
      },
      {
        id: "pdf",
        label: "Download PDF",
        href: `${base}?format=pdf&download=1`,
        icon: <FileText size={14} aria-hidden />,
      },
      {
        id: "docx",
        label: "Download DOCX",
        href: `${base}?format=docx&download=1`,
        icon: <FileText size={14} aria-hidden />,
      },
      {
        id: "json",
        label: "Download JSON",
        href: `${base}?format=json&download=1`,
        icon: <FileJson size={14} aria-hidden />,
      },
      {
        id: "bundle",
        label: "Download Evidence Bundle",
        href: `${base}?format=bundle&download=1`,
        icon: <Archive size={14} aria-hidden />,
      },
    ],
    [base]
  );

  return (
    <div className="run-export">
      <button
        type="button"
        className="run-export__trigger"
        disabled={!enabled}
        aria-expanded={open}
        aria-haspopup="menu"
        title={enabled ? "Export canonical QA report" : "Report available when execution completes."}
        onClick={() => enabled && setOpen((v: boolean) => !v)}
      >
        <Download size={16} aria-hidden />
        Export Report
        <ChevronDown size={14} aria-hidden />
      </button>
      {!enabled ? (
        <p className="run-export__hint">Report available when execution completes.</p>
      ) : null}
      {open && enabled ? (
        <ul className="run-export__menu" role="menu">
          {items.map((item: ExportItem) => (
            <li key={item.id} role="none">
              <a
                role="menuitem"
                className="run-export__item"
                href={item.href}
                target={item.target}
                rel={item.target === "_blank" ? "noopener noreferrer" : undefined}
                onClick={() => setOpen(false)}
              >
                {item.icon}
                {item.label}
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
