import { apiRequest } from "./client";

export type P9Dashboard = {
  scope: string;
  venture: string;
  period_start: string;
  period_end: string;
  kpis: {
    order_count: number;
    ordered_value: string;
    billed_revenue: string;
    net_billed_revenue: string;
    collections: string;
    outstanding: string;
    cancelled_value: string;
    void_value: string;
    average_bill_value: string;
    open_unbilled_sessions: number;
  };
  top_items: Array<{ menu_item_id: number; item_name: string; units_sold: string; ordered_value: string }>;
  source_channel_mix: Record<string, string>;
  payment_mode_mix: Record<string, string>;
  table_turnover: { session_count: number; closed_session_count: number; average_duration_minutes: string | null };
};

export type P9Consolidated = P9Dashboard & {
  venture_summaries: Array<{
    company_id: number;
    venture: string;
    company_name: string;
    billed_revenue: string;
    net_billed_revenue: string;
    collections: string;
    outstanding: string;
  }>;
};

function query(options: { startDate?: string; endDate?: string; branchId?: number }): string {
  const params = new URLSearchParams();
  if (options.startDate) params.set("start_date", options.startDate);
  if (options.endDate) params.set("end_date", options.endDate);
  if (options.branchId) params.set("branch_id", String(options.branchId));
  const value = params.toString();
  return value ? `?${value}` : "";
}

export function getCafeDashboard(token: string, options = {}): Promise<P9Dashboard> {
  return apiRequest<P9Dashboard>(`/dashboard/cafe${query(options)}`, {}, token);
}

export function getConsolidatedDashboard(token: string, options = {}): Promise<P9Consolidated> {
  return apiRequest<P9Consolidated>(`/dashboard/consolidated${query(options)}`, {}, token);
}
