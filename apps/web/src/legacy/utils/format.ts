import { BUSINESS_TIMEZONE, businessDate, shiftDate, storedDate } from "../../businessDates";

export function formatCurrency(value: string | number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value));
}

export function formatQuantity(value: string | number): string {
  return Number(value).toLocaleString("en-IN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

export function formatPercent(value: string | number | null): string {
  if (value === null) {
    return "No prior period";
  }
  const numberValue = Number(value);
  const sign = numberValue > 0 ? "+" : "";
  return `${sign}${numberValue.toLocaleString("en-IN", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
  })}%`;
}

export function formatDate(value: string): string {
  // Render a calendar label as-is, regardless of the browser's timezone.
  return storedDate(value).toLocaleDateString("en-IN", {
    timeZone: "UTC", day: "2-digit", month: "short",
  });
}

export function formatDateTime(value: string): string {
  return storedDate(value).toLocaleString("en-IN", {
    timeZone: BUSINESS_TIMEZONE,
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  }) + " IST";
}

export function formatStatus(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function inputDateDaysAgo(daysAgo: number, now = new Date()): string {
  return shiftDate(businessDate(now), -daysAgo);
}
