import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      className={cn(
        "flex h-10 w-full rounded-lg border px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-[color:var(--text-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--action-primary)] disabled:cursor-not-allowed disabled:opacity-50 border-[color:var(--border-default)] bg-[color:var(--surface-page)] text-[color:var(--text-primary)]",
        className
      )}
      ref={ref}
      {...props}
    />
  )
);
Input.displayName = "Input";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.ComponentProps<"textarea">>(
  ({ className, ...props }, ref) => (
    <textarea
      className={cn(
        "flex min-h-[96px] w-full rounded-lg border px-3 py-2 text-sm shadow-sm placeholder:text-[color:var(--text-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--action-primary)] disabled:cursor-not-allowed disabled:opacity-50 border-[color:var(--border-default)] bg-[color:var(--surface-page)] text-[color:var(--text-primary)]",
        className
      )}
      ref={ref}
      {...props}
    />
  )
);
Textarea.displayName = "Textarea";

export function Badge({
  className,
  tone = "neutral",
  children,
}: {
  className?: string;
  tone?: "neutral" | "ok" | "warn" | "bad" | "info";
  children: React.ReactNode;
}) {
  const tones: Record<string, string> = {
    neutral:
      "bg-[color:var(--surface-raised)] text-[color:var(--text-secondary)] border-[color:var(--border-default)]",
    ok: "bg-[color:var(--status-pass-bg)] text-[color:var(--status-pass)] border-[color:var(--status-pass)]/30",
    warn:
      "bg-[color:var(--status-pending-bg)] text-[color:var(--status-pending)] border-[color:var(--status-pending)]/30",
    bad: "bg-[color:var(--status-fail-bg)] text-[color:var(--status-fail)] border-[color:var(--status-fail)]/30",
    info: "bg-[color:var(--status-running-bg)] text-[color:var(--status-running)] border-[color:var(--status-running)]/30",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        tones[tone],
        className
      )}
    >
      {children}
    </span>
  );
}
