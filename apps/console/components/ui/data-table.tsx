"use client";

import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/ui/status-badge";

export type DataTableColumn<T> = {
  key: string;
  header: string;
  mono?: boolean;
  render?: (row: T) => React.ReactNode;
  className?: string;
};

export function DataTable<T extends Record<string, unknown>>({
  columns,
  rows,
  selectedId,
  onSelect,
  loading,
  error,
  emptyTitle,
  emptyDescription,
  emptyAction,
}: {
  columns: DataTableColumn<T>[];
  rows: T[];
  selectedId?: string | null;
  onSelect?: (row: T) => void;
  loading?: boolean;
  error?: string | null;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: React.ReactNode;
}) {
  if (loading) {
    return (
      <div className="data-table-empty" role="status">
        <Loader2 size={18} className="status-badge-spin" aria-hidden />
        <span>Loading…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="data-table-empty data-table-empty--error" role="alert">
        <strong>{error}</strong>
      </div>
    );
  }

  if (!rows.length) {
    return (
      <div className="data-table-empty">
        <strong>{emptyTitle || "No records"}</strong>
        {emptyDescription ? <p>{emptyDescription}</p> : null}
        {emptyAction}
      </div>
    );
  }

  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} scope="col">
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => {
            const rowId = String((row as { id?: string }).id ?? idx);
            const selected = selectedId === rowId;
            return (
              <tr
                key={rowId}
                className={cn(selected && "data-table-row--selected", onSelect && "data-table-row--clickable")}
                onClick={onSelect ? () => onSelect(row) : undefined}
                tabIndex={onSelect ? 0 : undefined}
                onKeyDown={
                  onSelect
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onSelect(row);
                        }
                      }
                    : undefined
                }
              >
                {columns.map((col) => (
                  <td key={col.key} className={cn(col.mono && "font-mono text-sm", col.className)}>
                    {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? "—")}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function StatusCell({ status }: { status?: string | null }) {
  return <StatusBadge status={status} compact />;
}
