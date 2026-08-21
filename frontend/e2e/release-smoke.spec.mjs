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
  await page.route("**/api/cafe/public/**", async (route) => {
    operationalCalls += 1;
    await route.abort();
  });
  await page.route("**/api/cloud/public/cafe/qr/resolve", async (route) => {
    await route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ error: { code: "not_found", message: "Unknown QR" } }),
    });
  });

  await page.goto("/order/release-invalid-token");
  await page.waitForTimeout(500);
  expect(operationalCalls).toBe(0);
});
