import { HttpError } from "./errors";
export function scaled(value: unknown): number {
  const s = String(value ?? "");
  if (!/^\d{1,9}(\.\d{1,2})?$/.test(s))
    throw new HttpError(
      422,
      "invalid_decimal",
      "Use a non-negative decimal with at most two places.",
    );
  const [whole, fraction = ""] = s.split(".");
  const n = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  if (!Number.isSafeInteger(n))
    throw new HttpError(422, "invalid_decimal", "Value is too large.");
  return n;
}
export function decimal(n: number) {
  if (!Number.isSafeInteger(n))
    throw new HttpError(422, "invalid_decimal", "Invalid monetary result.");
  return `${n < 0 ? "-" : ""}${Math.floor(Math.abs(n) / 100)}.${String(Math.abs(n) % 100).padStart(2, "0")}`;
}
export function multiply(price: number, quantity: number) {
  const result = price * quantity;
  if (!Number.isSafeInteger(result))
    throw new HttpError(422, "invalid_decimal", "Line value is too large.");
  return Math.floor((result + 50) / 100);
}
export function canonical(value: unknown): string {
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  if (value !== null && typeof value === "object")
    return (
      "{" +
      Object.entries(value)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([k, v]) => JSON.stringify(k) + ":" + canonical(v))
        .join(",") +
      "}"
    );
  return JSON.stringify(value);
}
export function businessDate(time = new Date()) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(time);
}
