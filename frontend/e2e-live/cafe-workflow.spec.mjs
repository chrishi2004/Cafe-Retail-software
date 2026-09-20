import { expect, test } from "@playwright/test";

async function login(page, email) {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill("RetailDemo@123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}

test("real cafe order, service and cash bill reconcile with persisted inventory", async ({ page }) => {
  // LAN HTTP does not provide randomUUID; checkout must still work.
  await page.addInitScript(() => Object.defineProperty(crypto, "randomUUID", { value: undefined }));
  await login(page, "cafe.admin@example.test");
  await expect(page).toHaveURL(/\/cafe\/dashboard$/);
  const token = await page.evaluate(() => sessionStorage.getItem("hybrid_retail_auth_token"));
  const headers = { Authorization: `Bearer ${token}` };
  const before = await page.request.get("http://127.0.0.1:8001/api/inventory", { headers });
  expect(before.ok()).toBeTruthy();
  const stockBefore = await before.json();
  await page.getByRole("button", { name: "New Order", exact: true }).click();
  await page.getByRole("row").filter({ hasText: "Cafe Latte" }).getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("button", { name: "Place order", exact: true }).click();
  await expect(page.getByText(/placed at ₹180/)).toBeVisible();
  await page.getByRole("button", { name: "Live Orders", exact: true }).click();
  for (const action of ["Accept", "Start preparing", "Mark ready", "Serve", "Request bill"]) {
    await page.getByRole("button", { name: action, exact: true }).click();
  }
  await page.getByRole("button", { name: "Billing", exact: true }).click();
  await page.getByLabel("Billing source").selectOption({ index: 1 });
  await expect(page.getByText("Grand total ₹180.00", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Issue bill and settle", exact: true }).click();
  await expect(page.getByText("Source closed", { exact: true })).toBeVisible();
  await expect(page.locator("#cafe-receipt")).toContainText("Balance ₹0.00");
  const after = await page.request.get("http://127.0.0.1:8001/api/inventory", { headers });
  const stockAfter = await after.json();
  expect(Number(stockAfter[0].quantity_on_hand)).toBe(Number(stockBefore[0].quantity_on_hand) - 1);
  await page.reload();
  await expect(page.getByLabel("Billing source").locator("option")).toHaveCount(1);
});

test("real kitchen login has preparation access and cannot fetch invoices", async ({ page }) => {
  await login(page, "cafe.kitchen@example.test");
  await expect(page).toHaveURL(/\/cafe\/kitchen$/);
  await expect(page.getByRole("heading", { name: "Kitchen Queue", exact: true })).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("hybrid_retail_auth_token"));
  const response = await page.request.get("http://127.0.0.1:8001/api/invoices", { headers: { Authorization: `Bearer ${token}` } });
  expect(response.status()).toBe(403);
});
