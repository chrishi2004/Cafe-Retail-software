import { apiRequest } from "./client";
import type { ForecastRecord, ForecastRunPayload, ForecastRunResult, ForecastType } from "../types";

type ForecastListOptions = {
  forecastType?: ForecastType | "";
  branchId?: number;
  categoryId?: number;
  productId?: number;
  limit?: number;
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

export function runForecast(token: string, payload: ForecastRunPayload): Promise<ForecastRunResult> {
  return apiRequest<ForecastRunResult>(
    "/forecasts/run",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function listForecasts(token: string, options: ForecastListOptions = {}): Promise<ForecastRecord[]> {
  return apiRequest<ForecastRecord[]>(
    `/forecasts${queryString({
      forecast_type: options.forecastType,
      branch_id: options.branchId,
      category_id: options.categoryId,
      product_id: options.productId,
      limit: options.limit,
    })}`,
    {},
    token,
  );
}

export function listProductForecasts(
  token: string,
  productId: number,
  options: Pick<ForecastListOptions, "branchId" | "limit"> = {},
): Promise<ForecastRecord[]> {
  return apiRequest<ForecastRecord[]>(
    `/forecasts/products/${productId}${queryString({
      branch_id: options.branchId,
      limit: options.limit,
    })}`,
    {},
    token,
  );
}
