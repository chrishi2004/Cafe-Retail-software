import type { ReactNode } from "react";
import { AlertCircle, Inbox, Loader2, Search } from "lucide-react";

import type { PageAction, PageMetric, TableColumn, TableRow } from "../types";

type MetricCardProps = {
  metric: PageMetric;
};

export function MetricCard({ metric }: MetricCardProps) {
  return (
    <article className={`metric-card ${metric.tone}`}>
      <p>{metric.label}</p>
      <strong>{metric.value}</strong>
      <span>{metric.detail}</span>
    </article>
  );
}

type FilterBarProps = {
  filters: string[];
};

export function FilterBar({ filters }: FilterBarProps) {
  return (
    <div className="filter-bar" aria-label="Page filters">
      <div className="search-shell">
        <Search aria-hidden="true" size={16} />
        <input aria-label="Search current page" placeholder="Search current view" type="search" />
      </div>
      <div className="filter-actions">
        {filters.map((filter) => (
          <button className="filter-chip" key={filter} type="button">
            {filter}
          </button>
        ))}
      </div>
    </div>
  );
}

type PageActionsProps = {
  actions: PageAction[];
};

export function PageActions({ actions }: PageActionsProps) {
  return (
    <div className="page-actions">
      {actions.map((action) => (
        <button className={`action-button ${action.tone}`} key={action.label} type="button">
          {action.label}
        </button>
      ))}
    </div>
  );
}

type DataTableShellProps = {
  columns: TableColumn[];
  rows: TableRow[];
};

export function DataTableShell({ columns, rows }: DataTableShellProps) {
  return (
    <div className="table-shell">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={`${rowIndex}-${columns[0]?.key ?? "row"}`}>
              {columns.map((column) => (
                <td key={column.key}>{row[column.key] ?? ""}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function LoadingState({ label = "Loading dashboard" }: { label?: string }) {
  return (
    <div className="state-panel">
      <Loader2 aria-hidden="true" className="spin-icon" size={24} />
      <p>{label}</p>
    </div>
  );
}

export function EmptyState({
  title,
  message,
}: {
  title: string;
  message: string;
}) {
  return (
    <div className="state-panel">
      <Inbox aria-hidden="true" size={24} />
      <h3>{title}</h3>
      <p>{message}</p>
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  children,
}: {
  title?: string;
  message: string;
  children?: ReactNode;
}) {
  return (
    <div className="state-panel error">
      <AlertCircle aria-hidden="true" size={24} />
      <h3>{title}</h3>
      <p>{message}</p>
      {children}
    </div>
  );
}
