import { expect, test } from "@playwright/test";

test("login renders MFA and submits authenticator code", async ({ page }) => {
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ error: { code: "unauthorized", message: "Authentication required." } }),
    });
  });

  let submitted = null;
  await page.route("**/api/auth/login", async (route) => {
    submitted = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: "browser-release-test-token",
        token_type: "bearer",
        expires_at: "2099-01-01T00:00:00Z",
        user: {
          id: 1,
          business_group_id: 1,
          company_id: 1,
          company_name: "Release Cafe",
          company_slug: "release-cafe",
          company_business_type: "cafe",
          name: "Release Admin",
          email: "admin@hybridretail.test",
          role: "admin",
          branch_id: null,
          permissions: ["*"],
          is_active: true,
          mfa_enabled: true,
        },
      }),
    });
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in to your workspace" })).toBeVisible();
  const authenticator = page.getByLabel("Authenticator code");
  await expect(authenticator).toBeVisible();
  await authenticator.fill("123456");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect.poll(() => submitted).not.toBeNull();
  expect(submitted.totp_code).toBe("123456");
  expect(submitted.email).toBe("admin@hybridretail.test");
});

test("public Cafe route does not need the Local Hub operational API", async ({ page }) => {
  let operationalCalls = 0;
  let cloudCalls = 0;
  await page.route("**/api/cafe/public/**", async (route) => {
    operationalCalls += 1;
    await route.abort();
  });
  await page.route("**/api/cloud/public/cafe/qr/resolve", async (route) => {
    cloudCalls += 1;
    await route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ error: { code: "not_found", message: "Unknown QR" } }),
    });
  });

  await page.goto("/order/release-invalid-token");
  await expect(page.getByRole("heading", { name: "This table link is unavailable" })).toBeVisible();
  expect(cloudCalls).toBeGreaterThan(0);
  expect(operationalCalls).toBe(0);
});

test("cloud customer can order and retry a bill request with the same key", async ({ page }) => {
  const order = {
    public_id: "release-cloud-order",
    status: "awaiting_cafe_confirmation",
    estimated_total: "50.00",
    created_at: "2026-09-20T12:00:00Z",
    items: [{ menu_item_public_id: "tea", name: "Tea", quantity: 1, unit_price: "50.00", line_total: "50.00" }],
    replayed: false,
  };
  const billKeys = [];
  let submitted = null;
  let operationalCalls = 0;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body;
    let status = 200;
    if (path === "/api/cloud/public/cafe/qr/resolve") {
      body = { publication_id: "release-menu", table_code: "T1", table_display_name: "Table 1", ordering_enabled: true };
    } else if (path === "/api/cloud/public/cafe/menu/release-menu") {
      body = {
        categories: [{ source_category_id: "drinks", name: "Drinks", display_order: 1 }],
        items: [{ source_menu_item_id: "tea", source_category_id: "drinks", name: "Tea", description: null, image_reference: null, selling_price: "50.00", preparation_area: "kitchen", available: true, display_order: 1 }],
      };
    } else if (path === "/api/cloud/public/cafe/orders") {
      submitted = route.request().postDataJSON();
      body = order;
    } else if (path.endsWith("/release-cloud-order/bill-request")) {
      billKeys.push(route.request().headers()["idempotency-key"]);
      status = billKeys.length === 1 ? 503 : 200;
      body = status === 503
        ? { error: { code: "unavailable", message: "Try again" } }
        : { order_public_id: order.public_id, status: "queued", bill_requested_at: "2026-09-20T12:01:00Z", replayed: true };
    } else if (path.endsWith("/orders/release-cloud-order")) {
      body = order;
    } else {
      operationalCalls += 1;
      await route.abort();
      return;
    }
    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  });

  await page.goto("/order/release-valid-qr");
  await expect(page.getByRole("heading", { name: "Table 1" })).toBeVisible();
  await expect(page.getByText("The Local Hub is temporarily unreachable.", { exact: false })).toHaveCount(0);
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("button", { name: /Place order/ }).click();
  await expect(page.getByText(/sent. Waiting for Cafe confirmation/)).toBeVisible();
  expect(submitted.items).toEqual([{ menu_item_public_id: "tea", quantity: 1, notes: null }]);
  await page.getByRole("button", { name: "Request bill", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("The bill request could not be confirmed.");
  await page.getByRole("button", { name: "Request bill", exact: true }).click();
  await expect(page.getByRole("button", { name: "Bill requested", exact: true })).toBeDisabled();
  expect(billKeys).toHaveLength(2);
  expect(billKeys[0]).toBeTruthy();
  expect(billKeys[1]).toBe(billKeys[0]);
  expect(operationalCalls).toBe(0);
});
