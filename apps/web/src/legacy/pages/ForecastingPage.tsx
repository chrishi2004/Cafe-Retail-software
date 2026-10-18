import { useCallback, useEffect, useMemo, useState } from "react";
import { BrainCircuit, RefreshCw, TrendingDown, TrendingUp } from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ApiError } from "../api/client";
import { listForecasts, runForecast } from "../api/forecasts";
import { listBranches, listCategories, listProducts } from "../api/masterData";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, LoadingState, MetricCard } from "../components/ui";
import type {
  Branch,
  Category,
  ForecastRecord,
  ForecastRunResult,
  ForecastType,
  Product,
} from "../types";
import { formatCurrency, formatQuantity, formatStatus, inputDateDaysAgo } from "../utils/format";

type ForecastDimension = "overall" | "branch" | "category" | "product";

const HORIZONS = [7, 30, 90] as const;
const FORECAST_TYPES: ForecastType[] = ["revenue", "units", "demand"];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Could not run the forecast. Check that the backend is running.";
}

function valueFormatter(type: ForecastType, value: string | number | null): string {
  if (value === null) {
    return "Not available";
  }
  return type === "revenue" ? formatCurrency(value) : formatQuantity(value);
}

function trendTone(result: ForecastRunResult | null): "green" | "blue" | "amber" | "rose" | "slate" {
  if (!result || result.insufficient_data) return "slate";
  if (result.trend_label === "increasing") return "green";
  if (result.trend_label === "decreasing") return "rose";
  return "blue";
}

function trendDetail(result: ForecastRunResult | null): string {
  if (!result || result.insufficient_data) return "Run a forecast to calculate trend";
  if (result.trend_percent === null) return "No comparable previous window";
  return `${Number(result.trend_percent).toLocaleString("en-IN", { maximumFractionDigits: 2 })}% vs previous window`;
}

function recordScope(record: ForecastRecord): string {
  if (record.product_name) return record.product_name;
  if (record.category_name) return record.category_name;
  if (record.branch_name) return record.branch_name;
  return "Overall business";
}

export function ForecastingPage() {
  const { token, user } = useAuth();
  const [branches, setBranches] = useState<Branch[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [savedForecasts, setSavedForecasts] = useState<ForecastRecord[]>([]);
  const [forecastType, setForecastType] = useState<ForecastType>("revenue");
  const [horizonDays, setHorizonDays] = useState<7 | 30 | 90>(30);
  const [dimension, setDimension] = useState<ForecastDimension>("overall");
  const [branchId, setBranchId] = useState(0);
  const [categoryId, setCategoryId] = useState(0);
  const [productId, setProductId] = useState(0);
  const [asOfDate, setAsOfDate] = useState(() => inputDateDaysAgo(0));
  const [result, setResult] = useState<ForecastRunResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const visibleBranches = useMemo(() => {
    if (!user || user.role === "admin" || user.role === "analyst") {
      return branches;
    }
    return branches.filter((branch) => branch.id === user.branch_id);
  }, [branches, user]);

  const visibleProducts = useMemo(() => {
    if (categoryId) {
      return products.filter((product) => product.category_id === categoryId);
    }
    return products;
  }, [categoryId, products]);

  useEffect(() => {
    if (user?.role === "store_manager" && user.branch_id) {
      setBranchId(user.branch_id);
    }
  }, [user]);

  const loadOptions = useCallback(async () => {
    if (!token) return;
    const [branchRows, categoryRows, productRows] = await Promise.all([
      listBranches(token, { includeInactive: false }),
      listCategories(token),
      listProducts(token, { includeInactive: false }),
    ]);
    setBranches(branchRows);
    setCategories(categoryRows);
    setProducts(productRows);
  }, [token]);

  const loadSavedForecasts = useCallback(async () => {
    if (!token) return;
    setSavedForecasts(await listForecasts(token, { forecastType, limit: 20 }));
  }, [forecastType, token]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        await Promise.all([loadOptions(), loadSavedForecasts()]);
      } catch (loadError) {
        setError(errorMessage(loadError));
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [loadOptions, loadSavedForecasts]);

  const chartData = useMemo(() => {
    if (!result) return [];
    const history = result.historical_points.slice(-45).map((point) => ({
      date: point.date,
      actual: Number(point.value),
      forecast: null,
    }));
    const forecast = result.forecast_points.map((point) => ({
      date: point.date,
      actual: null,
      forecast: Number(point.value),
    }));
    return [...history, ...forecast];
  }, [result]);

  const runSelectedForecast = async () => {
    if (!token) return;
    setRunning(true);
    setError(null);
    try {
      const payload = {
        forecast_type: forecastType,
        horizon_days: horizonDays,
        as_of_date: asOfDate || null,
        branch_id: dimension === "branch" && branchId ? branchId : null,
        category_id: dimension === "category" && categoryId ? categoryId : null,
        product_id: dimension === "product" && productId ? productId : null,
      };
      const forecastResult = await runForecast(token, payload);
      setResult(forecastResult);
      await loadSavedForecasts();
    } catch (forecastError) {
      setError(errorMessage(forecastError));
    } finally {
      setRunning(false);
    }
  };

  const latestScope = result?.product_name ?? result?.category_name ?? result?.branch_name ?? "Overall business";

  return (
    <section className="page-stack" aria-labelledby="forecast-title">
      <div className="page-header">
        <div>
          <p className="eyebrow">Demand planning</p>
          <h2 id="forecast-title">Forecasting</h2>
          <p className="page-description">
            Run explainable moving-average forecasts from historical sales. Use them to estimate
            revenue, units, or product demand before purchasing decisions.
          </p>
        </div>
        <div className="page-header-side">
          <span className="role-scope">Forecast service connected</span>
          <button className="action-button secondary" onClick={() => void loadSavedForecasts()} type="button">
            <RefreshCw aria-hidden="true" size={16} />
            Refresh
          </button>
        </div>
      </div>

      <div className="filter-bar dashboard-filter-bar forecast-filter-bar">
        <div className="filter-actions">
          <select
            aria-label="Select forecast type"
            onChange={(event) => setForecastType(event.target.value as ForecastType)}
            value={forecastType}
          >
            {FORECAST_TYPES.map((type) => (
              <option key={type} value={type}>
                {formatStatus(type)}
              </option>
            ))}
          </select>
          <select
            aria-label="Select forecast horizon"
            onChange={(event) => setHorizonDays(Number(event.target.value) as 7 | 30 | 90)}
            value={horizonDays}
          >
            {HORIZONS.map((horizon) => (
              <option key={horizon} value={horizon}>
                {horizon} days
              </option>
            ))}
          </select>
          <select
            aria-label="Select forecast dimension"
            onChange={(event) => {
              setDimension(event.target.value as ForecastDimension);
              setCategoryId(0);
              setProductId(0);
            }}
            value={dimension}
          >
            <option value="overall">Overall</option>
            <option value="branch">Branch</option>
            <option value="category">Category</option>
            <option value="product">Product</option>
          </select>
          {dimension === "branch" ? (
            <select
              aria-label="Select branch for forecast"
              onChange={(event) => setBranchId(Number(event.target.value))}
              value={branchId}
            >
              <option value={0}>Select branch</option>
              {visibleBranches.map((branch) => (
                <option key={branch.id} value={branch.id}>
                  {branch.name}
                </option>
              ))}
            </select>
          ) : null}
          {dimension === "category" ? (
            <select
              aria-label="Select category for forecast"
              onChange={(event) => setCategoryId(Number(event.target.value))}
              value={categoryId}
            >
              <option value={0}>Select category</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          ) : null}
          {dimension === "product" ? (
            <>
              <select
                aria-label="Narrow products by category"
                onChange={(event) => {
                  setCategoryId(Number(event.target.value));
                  setProductId(0);
                }}
                value={categoryId}
              >
                <option value={0}>All product categories</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
              <select
                aria-label="Select product for forecast"
                onChange={(event) => setProductId(Number(event.target.value))}
                value={productId}
              >
                <option value={0}>Select product</option>
                {visibleProducts.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name}
                  </option>
                ))}
              </select>
            </>
          ) : null}
          <label className="date-filter">
            As of
            <input onChange={(event) => setAsOfDate(event.target.value)} type="date" value={asOfDate} />
          </label>
          <button className="action-button primary" disabled={running} onClick={() => void runSelectedForecast()} type="button">
            <BrainCircuit aria-hidden="true" size={16} />
            {running ? "Running" : "Run forecast"}
          </button>
        </div>
      </div>

      {error ? <ErrorState message={error} title="Forecast failed" /> : null}

      <section className="metric-grid">
        <MetricCard
          metric={{
            label: "Forecast Value",
            value: result ? valueFormatter(result.forecast_type, result.forecast_value) : "Not run",
            detail: result?.forecast_start_date
              ? `${result.forecast_start_date} to ${result.forecast_end_date}`
              : "Select a horizon and run forecast",
            tone: "green",
          }}
        />
        <MetricCard
          metric={{
            label: "Average Daily",
            value: result ? valueFormatter(result.forecast_type, result.average_daily_value) : "Not run",
            detail: "Recent moving average baseline",
            tone: "blue",
          }}
        />
        <MetricCard
          metric={{
            label: "Trend",
            value: result ? formatStatus(result.trend_label) : "Not run",
            detail: trendDetail(result),
            tone: trendTone(result),
          }}
        />
        <MetricCard
          metric={{
            label: "Confidence Range",
            value: result
              ? `${valueFormatter(result.forecast_type, result.confidence_low)} - ${valueFormatter(
                  result.forecast_type,
                  result.confidence_high,
                )}`
              : "Not run",
            detail: "Simple 15% planning band",
            tone: "amber",
          }}
        />
      </section>

      <section className="dashboard-grid">
        <article className="panel chart-panel wide forecast-chart-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{latestScope}</p>
              <h3>Historical vs forecast</h3>
            </div>
            {result ? (
              <span className={`priority-badge ${result.insufficient_data ? "medium" : result.trend_label === "decreasing" ? "critical" : "low"}`}>
                {result.insufficient_data ? "Insufficient data" : formatStatus(result.trend_label)}
              </span>
            ) : null}
          </div>

          {loading ? <LoadingState label="Loading forecast data" /> : null}
          {!loading && !result ? (
            <EmptyState title="Forecast not run yet" message="Choose a scope and run a forecast to draw the planning chart." />
          ) : null}
          {result?.insufficient_data ? (
            <ErrorState title="Insufficient data" message={result.message} />
          ) : null}
          {result && !result.insufficient_data ? (
            <>
              <p className="forecast-explanation">{result.message}</p>
              <ResponsiveContainer height={330} width="100%">
                <LineChart data={chartData}>
                  <CartesianGrid stroke="#e7ebf1" vertical={false} />
                  <XAxis dataKey="date" minTickGap={24} />
                  <YAxis tickFormatter={(value) => valueFormatter(result.forecast_type, value)} width={86} />
                  <Tooltip
                    formatter={(value) => valueFormatter(result.forecast_type, String(value))}
                    labelFormatter={(label) => `Date: ${label}`}
                  />
                  <Legend />
                  <Line connectNulls={false} dataKey="actual" dot={false} name="Historical" stroke="#276fbf" strokeWidth={2} />
                  <Line connectNulls={false} dataKey="forecast" dot={false} name="Forecast" stroke="#1f8a5b" strokeDasharray="5 4" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </>
          ) : null}
        </article>

        <article className="panel wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Saved outputs</p>
              <h3>Recent forecasts</h3>
            </div>
          </div>
          {savedForecasts.length === 0 ? (
            <EmptyState title="No saved forecasts" message="Run a forecast to save the horizon total in the local database." />
          ) : (
            <div className="table-shell forecast-table">
              <table>
                <thead>
                  <tr>
                    <th>Scope</th>
                    <th>Type</th>
                    <th>Forecast Window</th>
                    <th>Value</th>
                    <th>Confidence</th>
                    <th>Model</th>
                  </tr>
                </thead>
                <tbody>
                  {savedForecasts.map((forecast) => (
                    <tr key={forecast.id}>
                      <td>
                        <strong>{recordScope(forecast)}</strong>
                        <span className="subtle-cell">{new Date(forecast.created_at).toLocaleString()}</span>
                      </td>
                      <td>{formatStatus(forecast.forecast_type)}</td>
                      <td>
                        {forecast.forecast_start_date} to {forecast.forecast_end_date}
                      </td>
                      <td>{valueFormatter(forecast.forecast_type, forecast.forecast_value)}</td>
                      <td>
                        {valueFormatter(forecast.forecast_type, forecast.confidence_low)} -{" "}
                        {valueFormatter(forecast.forecast_type, forecast.confidence_high)}
                      </td>
                      <td>{forecast.model_name}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </section>

      {result && !result.insufficient_data ? (
        <section className="panel forecast-summary-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Planning note</p>
              <h3>Business explanation</h3>
            </div>
            {result.trend_label === "decreasing" ? <TrendingDown aria-hidden="true" size={20} /> : <TrendingUp aria-hidden="true" size={20} />}
          </div>
          <p className="forecast-explanation">
            This MVP forecast uses recent historical sales only. It is best for short planning conversations,
            reorder timing, and portfolio demonstration, not for automated purchasing without review.
          </p>
        </section>
      ) : null}
    </section>
  );
}
