import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e-live",
  timeout: 60000,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["html", { outputFolder: "playwright-live-report", open: "never" }]],
  use: { baseURL: "http://127.0.0.1:4174", headless: true, trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: [
    { command: "cd ../backend && python -m tests.browser_server", env: { ENVIRONMENT: "test", BROWSER_FIXTURE: "1" }, url: "http://127.0.0.1:8001/api/health", timeout: 60000 },
    { command: "npm run preview -- --host 127.0.0.1 --port 4174", port: 4174, timeout: 30000 },
  ],
});
