"use client";

import { cn } from "@/lib/utils";

export function EmptyState({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("empty-state", className)}>
      <h3>{title}</h3>
      {description ? <p>{description}</p> : null}
      {action ? <div className="empty-state__action">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  title,
  description,
  onRetry,
  details,
}: {
  title: string;
  description?: string;
  onRetry?: () => void;
  details?: string;
}) {
  return (
    <div className="error-state" role="alert">
      <h3>{title}</h3>
      {description ? <p>{description}</p> : null}
      {onRetry ? (
        <button type="button" className="btn btn-secondary" onClick={onRetry}>
          Retry
        </button>
      ) : null}
      {details ? (
        <details className="error-state__details">
          <summary>Technical details</summary>
          <pre>{details}</pre>
        </details>
      ) : null}
    </div>
  );
}
