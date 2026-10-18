import test from "node:test";
import assert from "node:assert/strict";
import { forecastPoints } from "../src/server/planning";
import { dateOnly, period, csv } from "../src/server/query";
test("forecast ports moving-average trend without inventing negative demand", () => {
  const stable = forecastPoints(Array(90).fill(10000), 7, "2026-10-20");
  assert.equal(stable.forecast_value, "700.00");
  assert.equal(stable.average_daily_value, "100.00");
  assert.equal(stable.trend_label, "stable");
  assert.equal(stable.forecast_points.at(-1)?.date, "2026-10-26");
  const declining = forecastPoints(
    [...Array(62).fill(10000), ...Array(28).fill(0)],
    90,
    "2026-10-20",
  );
  assert(declining.forecast_points.every((p) => Number(p.value) >= 0));
  assert.equal(declining.trend_label, "decreasing");
});
test("date filters reject nonexistent calendar dates and reversed periods", () => {
  assert.throws(() => dateOnly("2026-02-30"));
  assert.throws(() =>
    period(new URL("https://test/?start_date=2026-10-20&end_date=2026-10-01")),
  );
});
test("CSV neutralizes formula cells and escapes embedded delimiters", async () => {
  const result = await csv(
    [{ name: '=HYPERLINK("bad")', value: "a,b\nc" }],
    "test",
  ).text();
  assert.match(result, /"'=HYPERLINK/);
  assert.match(result, /"a,b\nc"/);
});
