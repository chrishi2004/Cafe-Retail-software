export const CAFE_TIMEZONE = "Asia/Kolkata";
export const PRESETS = ["Today", "Yesterday", "7 Days", "This Month", "Last Month", "Custom Range"] as const;
export type CafePreset = typeof PRESETS[number];

export function cafeToday(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: CAFE_TIMEZONE, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}
export function cafeRange(preset: CafePreset): { startDate: string; endDate: string } {
  const today = cafeToday();
  const end = new Date(`${today}T12:00:00Z`);
  const start = new Date(end);
  if (preset === "Yesterday") { start.setUTCDate(start.getUTCDate() - 1); end.setUTCDate(end.getUTCDate() - 1); }
  if (preset === "7 Days") start.setUTCDate(start.getUTCDate() - 6);
  if (preset === "This Month") start.setUTCDate(1);
  if (preset === "Last Month") { start.setUTCDate(1); start.setUTCMonth(start.getUTCMonth() - 1); end.setUTCDate(0); }
  return { startDate: start.toISOString().slice(0, 10), endDate: end.toISOString().slice(0, 10) };
}
