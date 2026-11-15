export const BUSINESS_TIMEZONE = "Asia/Kolkata";
// POS dates use modern IST (UTC+05:30).
export const KOLKATA_OFFSET = "+05:30";
export const DAY_MS = 86_400_000;

const calendarDay = new Intl.DateTimeFormat("en-CA", {
  timeZone: BUSINESS_TIMEZONE, year: "numeric", month: "2-digit", day: "2-digit",
});
const dateOnly = /^\d{4}-\d{2}-\d{2}$/;
const explicitOffset = /(?:Z|[+-]\d{2}:\d{2})$/i;

export function isCalendarDate(value: string) {
  return dateOnly.test(value) && Number.isFinite(Date.parse(value)) &&
    new Date(value).toISOString().slice(0, 10) === value;
}

// Persisted ISO timestamps are UTC or carry an offset. Old offsetless timestamps
// were written as UTC; calendar dates are labels and should never shift a day.
export function storedDate(value: string) {
  return new Date(dateOnly.test(value) || explicitOffset.test(value) ? value : value + "Z");
}

export function businessDate(value: Date | string = new Date()) {
  return typeof value === "string" && isCalendarDate(value)
    ? value
    : calendarDay.format(typeof value === "string" ? storedDate(value) : value);
}

// Date-only arithmetic uses UTC as a calendar, never as the business timezone.
export function shiftDate(day: string, days: number) {
  return new Date(Date.parse(day) + days * DAY_MS).toISOString().slice(0, 10);
}

export function inBusinessRange(value: unknown, start: string | null, end: string | null) {
  if (typeof value === "string" && dateOnly.test(value) && !isCalendarDate(value)) return false;
  if (!(typeof value === "string" || value instanceof Date)) return false;
  const instant = typeof value === "string" ? storedDate(value) : value;
  if (!Number.isFinite(instant.getTime())) return false;
  const day = businessDate(value);
  return (!start || day >= start) && (!end || day <= end);
}
