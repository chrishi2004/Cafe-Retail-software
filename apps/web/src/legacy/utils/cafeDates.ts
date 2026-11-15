import { businessDate, shiftDate } from "../../businessDates";
export const PRESETS = ["Today", "Yesterday", "7 Days", "This Month", "Last Month", "Custom Range"] as const;
export type CafePreset = typeof PRESETS[number];

export const cafeToday = businessDate;

export function cafeRange(preset: CafePreset, now = new Date()): { startDate: string; endDate: string } {
  const today = cafeToday(now);
  const monthStart = today.slice(0, 8) + "01";
  const yesterday = shiftDate(today, -1);
  if (preset === "Yesterday") return { startDate: yesterday, endDate: yesterday };
  if (preset === "7 Days") return { startDate: shiftDate(today, -6), endDate: today };
  if (preset === "This Month") return { startDate: monthStart, endDate: today };
  if (preset === "Last Month") {
    const endDate = shiftDate(monthStart, -1);
    return { startDate: endDate.slice(0, 8) + "01", endDate };
  }
  return { startDate: today, endDate: today };
}
