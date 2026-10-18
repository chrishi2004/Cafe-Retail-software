import { API_BASE_URL, activeVentureStorage, ApiError } from "./client";

export type ExportKind = "sales" | "inventory" | "purchase-orders" | "forecasts" | "cafe" | "consolidated";

export type ExportDownloadOptions = {
  branchId?: number;
  categoryId?: number;
  supplierId?: number;
  productId?: number;
  lowStock?: boolean;
  status?: string;
  forecastType?: string;
  startDate?: string;
  endDate?: string;
};

const EXPORT_FILES: Record<ExportKind, string> = {
  sales: "sales_export.csv",
  inventory: "inventory_export.csv",
  "purchase-orders": "purchase_orders_export.csv",
  forecasts: "forecasts_export.csv",
  cafe: "cafe_report.csv",
  consolidated: "consolidated_report.csv",
};

function queryString(params: Record<string, string | number | boolean | undefined>): string {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

async function parseDownloadError(response: Response): Promise<ApiError> {
  try {
    const payload = (await response.json()) as {
      error?: { code?: string; message?: string };
      detail?: string;
    };
    return new ApiError(
      payload.error?.message ?? payload.detail ?? "Export failed.",
      response.status,
      payload.error?.code ?? "export_error",
    );
  } catch {
    return new ApiError("Export failed. Check that the backend is running.", response.status, "export_error");
  }
}

function triggerDownload(blob: Blob, filename: string): void {
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}

export async function downloadExport(
  token: string,
  kind: ExportKind,
  options: ExportDownloadOptions = {},
): Promise<void> {
  const query = queryString({
    branch_id: options.branchId,
    category_id: options.categoryId,
    supplier_id: options.supplierId,
    product_id: options.productId,
    low_stock: options.lowStock,
    status: options.status,
    forecast_type: options.forecastType,
    start_date: options.startDate,
    end_date: options.endDate,
  });
  const headers = new Headers({ Authorization: `Bearer ${token}` });
  const activeVentureId = activeVentureStorage.get();
  if (activeVentureId !== null) headers.set("X-Venture-Id", String(activeVentureId));
  const response = await fetch(`${API_BASE_URL}/exports/${kind}${query}`, { headers });

  if (!response.ok) {
    throw await parseDownloadError(response);
  }

  const disposition = response.headers.get("content-disposition") ?? "";
  const matchedFilename = disposition.match(/filename="?(?<filename>[^";]+)"?/i)?.groups?.filename;
  triggerDownload(await response.blob(), matchedFilename ?? EXPORT_FILES[kind]);
}
