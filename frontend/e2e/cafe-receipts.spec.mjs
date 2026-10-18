import { expect, test } from "@playwright/test";
const receipt = {
  invoice_id: 42, invoice_number: "CFG-00042", source_type: "cafe_takeaway", source_id: "existing-order",
  cafe_name: "Configured Café & Kitchen", branch_name: "Configured Main Counter",
  invoice_type: "non_gst", invoice_status: "partial_paid", payment_status: "partial_paid",
  issued_at: "2026-10-18T08:00:00Z", subtotal: "300.00", discount_total: "0.00", taxable_total: "300.00",
  cgst_total: "0.00", sgst_total: "0.00", igst_total: "0.00", cess_total: "0.00", round_off: "0.00",
  grand_total: "300.00", paid_amount: "200.00", balance_due: "100.00", gstin: null,
  items: [{ name: "A very long configured menu item name with extra toppings and customized preparation", sku: "ITEM-1", quantity: "2.00", unit_price: "150.00", discount: "0.00", line_total: "300.00" }],
  payments: [{ mode_name: "UPI", amount: "200.00", reference_number: "TEST-123", is_credit_marker: false }],
};
const user = { id: 4, business_group_id: 1, company_id: 2, company_name: receipt.cafe_name,
  company_slug: "configured-cafe", company_business_type: "cafe", name: "Cashier", email: "cashier@example.test",
  role: "staff", branch_id: 3, permissions: ["billing.read", "billing.write"], is_active: true, mfa_enabled: false };
async function setup(page, long = false) {
  const requests = [];
  await page.addInitScript(() => sessionStorage.setItem("hybrid_retail_auth_token", "receipt-test-token"));
  await page.route("**/api/**", async (route) => {
    const request = route.request(), url = new URL(request.url());
    requests.push({ method: request.method(), path: url.pathname });
    let body;
    if (url.pathname === "/api/auth/me") body = user;
    else if (url.pathname === "/api/branches") body = [{ id: 3, name: receipt.branch_name, is_active: true }];
    else if (url.pathname === "/api/cafe/billing/invoices") body = { items: [{ ...receipt, branch_id: 3 }], total: 1, limit: 50, offset: 0 };
    else if (url.pathname === "/api/cafe/billing/invoices/42/receipt") body = long
      ? { ...receipt, items: Array.from({ length: 80 }, (_, index) => ({ ...receipt.items[0], name: `${index + 1}. ${receipt.items[0].name}` })) } : receipt;
    else return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Unexpected request" }) });
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/cafe/receipts");
  await page.getByRole("button", { name: "View / reprint CFG-00042" }).click();
  await expect(page.getByRole("button", { name: "Reprint receipt", exact: true })).toBeVisible();
  return requests;
}
test("history reprints with GET only and isolates the 80mm receipt", async ({ page }) => {
  const requests = await setup(page), screen = page.locator(".cafe-receipt-preview");
  for (const text of [receipt.cafe_name, receipt.branch_name, receipt.invoice_number, "18 Oct 2026", receipt.items[0].name,
    "Grand total", "UPI", "Amount paid", "Balance due", "150.00", "300.00"]) await expect(screen).toContainText(text);
  await page.evaluate(() => { window.print = () => window.dispatchEvent(new Event("beforeprint")); });
  await page.getByRole("button", { name: "Reprint receipt", exact: true }).click();
  await page.getByRole("button", { name: "Reprint receipt", exact: true }).click();
  expect(requests.every((request) => request.method === "GET")).toBe(true);
  await page.emulateMedia({ media: "print" });
  await expect(page.locator("#root")).toBeHidden();
  const paper = page.locator("#cafe-receipt-print-root");
  await expect(paper).toBeVisible(); await expect(paper).toContainText("REPRINT");
  expect(await paper.locator("button, nav, aside").count()).toBe(0);
  const layout = await paper.evaluate((element) => ({
    width: element.getBoundingClientRect().width, page: getComputedStyle(element).page,
    children: [...document.body.children].filter((child) => getComputedStyle(child).display !== "none").map((child) => child.id),
    rule: document.querySelector("style[data-cafe-receipt-page]").textContent,
    overflow: [...element.querySelectorAll("td")].some((cell) => cell.scrollWidth > cell.clientWidth + 1),
  }));
  expect(layout.width).toBeCloseTo(72 * 96 / 25.4, 0); expect(layout.page).toBe("cafe-receipt");
  expect(layout.children).toEqual(["cafe-receipt-print-root"]); expect(layout.rule).toMatch(/size: 80mm \d+mm/);
  expect(layout.overflow).toBe(false);
  await page.emulateMedia({ media: "screen" });
  await page.getByRole("button", { name: "Close receipt", exact: true }).click();
  expect(await page.locator("#cafe-receipt-print-root").count()).toBe(0);
  expect(await page.locator("style[data-cafe-receipt-page]").count()).toBe(0);
});
test("long receipts grow roll length and retain every item without horizontal overflow", async ({ page }) => {
  await setup(page, true);
  const root = page.locator("#cafe-receipt-print-root");
  expect(await root.locator("tbody tr").count()).toBe(80);
  const rule = await page.locator("style[data-cafe-receipt-page]").textContent();
  expect(Number(rule.match(/80mm (\d+)mm/)[1])).toBeGreaterThan(200);
  await page.emulateMedia({ media: "print" });
  expect(await root.locator("tbody tr").count()).toBe(80);
  expect(await root.evaluate((element) => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
});
