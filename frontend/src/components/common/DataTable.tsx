import React from "react";

export interface Column<T> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  align?: "left" | "center" | "right";
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (item: T) => string;
  onRowClick?: (item: T) => void;
  isLoading?: boolean;
  emptyMessage?: string;
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  onRowClick,
  isLoading = false,
  emptyMessage = "No records found",
}: DataTableProps<T>) {
  if (isLoading) {
    return (
      <div className="w-full bg-slate-900/60 border border-slate-800 rounded-xl p-8 flex flex-col items-center justify-center gap-3">
        <div className="w-8 h-8 border-3 border-slate-700 border-t-emerald-400 rounded-full animate-spin" />
        <span className="text-sm font-mono text-slate-400">Loading market telemetry...</span>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="w-full bg-slate-900/40 border border-slate-800/80 rounded-xl p-10 text-center">
        <p className="text-slate-400 text-sm font-mono">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="w-full overflow-x-auto border border-slate-800/80 rounded-xl bg-slate-900/50 backdrop-blur-sm">
      <table className="w-full text-left border-collapse text-xs">
        <thead>
          <tr className="border-b border-slate-800 bg-slate-900/90 text-slate-400 font-mono uppercase text-[11px] tracking-wider">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`py-3 px-4 font-semibold ${
                  col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"
                } ${col.className || ""}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60 font-mono text-slate-200 tabular-nums">
          {data.map((item) => (
            <tr
              key={keyExtractor(item)}
              onClick={() => onRowClick && onRowClick(item)}
              className={`transition-colors hover:bg-slate-800/50 ${
                onRowClick ? "cursor-pointer" : ""
              }`}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={`py-3 px-4 whitespace-nowrap ${
                    col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"
                  } ${col.className || ""}`}
                >
                  {col.render ? col.render(item) : (item as any)[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
