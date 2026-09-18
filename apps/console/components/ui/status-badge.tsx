"use client";

import {
  AlertCircle,
  Ban,
  CheckCircle2,
  Circle,
  Clock,
  Loader2,
  PauseCircle,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type StatusKind =
  | "PASS"
  | "FAIL"
  | "BLOCKED"
  | "WAITING_FOR_APPROVAL"
  | "NEEDS_REVIEW"
  | "RUNNING"
  | "RECOVERING"
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "STALE"
  | "READY"
  | "DRAFT"
  | "SUPERSEDED";

const CONFIG: Record<
  StatusKind,
  { label: string; icon: React.ReactNode; className: string }
> = {
  PASS: {
    label: "Pass",
    icon: <CheckCircle2 size={14} aria-hidden />,
    className: "status-badge--pass",
  },
  FAIL: {
    label: "Fail",
    icon: <XCircle size={14} aria-hidden />,
    className: "status-badge--fail",
  },
  BLOCKED: {
    label: "Blocked",
    icon: <Ban size={14} aria-hidden />,
    className: "status-badge--blocked",
  },
  WAITING_FOR_APPROVAL: {
    label: "Waiting for approval",
    icon: <PauseCircle size={14} aria-hidden />,
    className: "status-badge--pending",
  },
  NEEDS_REVIEW: {
    label: "Needs review",
    icon: <ShieldAlert size={14} aria-hidden />,
    className: "status-badge--needs-review",
  },
  RUNNING: {
    label: "Running",
    icon: <Loader2 size={14} className="status-badge-spin" aria-hidden />,
    className: "status-badge--running",
  },
  RECOVERING: {
    label: "Recovering",
    icon: <Loader2 size={14} className="status-badge-spin" aria-hidden />,
    className: "status-badge--recovering",
  },
  PENDING: {
    label: "Pending",
    icon: <Clock size={14} aria-hidden />,
    className: "status-badge--pending",
  },
  APPROVED: {
    label: "Approved",
    icon: <CheckCircle2 size={14} aria-hidden />,
    className: "status-badge--approved",
  },
  REJECTED: {
    label: "Rejected",
    icon: <XCircle size={14} aria-hidden />,
    className: "status-badge--rejected",
  },
  STALE: {
    label: "Stale",
    icon: <AlertCircle size={14} aria-hidden />,
    className: "status-badge--stale",
  },
  READY: {
    label: "Ready",
    icon: <CheckCircle2 size={14} aria-hidden />,
    className: "status-badge--approved",
  },
  DRAFT: {
    label: "Draft",
    icon: <Circle size={14} aria-hidden />,
    className: "status-badge--blocked",
  },
  SUPERSEDED: {
    label: "Superseded",
    icon: <Ban size={14} aria-hidden />,
    className: "status-badge--stale",
  },
};

export function normalizeStatus(value?: string | null): StatusKind {
  const raw = String(value || "PENDING").toUpperCase().replace(/\s+/g, "_");
  if (raw in CONFIG) return raw as StatusKind;
  if (raw.includes("REVIEW")) return "NEEDS_REVIEW";
  if (raw.includes("APPROV")) return "WAITING_FOR_APPROVAL";
  if (raw.includes("RUN")) return "RUNNING";
  if (raw.includes("RECOVER")) return "RECOVERING";
  return "PENDING";
}

export function StatusBadge({
  status,
  className,
  compact,
}: {
  status?: string | null;
  className?: string;
  compact?: boolean;
}) {
  const kind = normalizeStatus(status);
  const cfg = CONFIG[kind];
  return (
    <span
      className={cn("status-badge", cfg.className, compact && "status-badge--compact", className)}
      role="status"
      aria-label={cfg.label}
    >
      {cfg.icon}
      <span>{cfg.label}</span>
    </span>
  );
}
