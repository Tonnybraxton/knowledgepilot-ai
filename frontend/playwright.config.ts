import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  retries: process.env.CI ? 1 : 0,
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"], defaultBrowserType: "chromium" } },
  ],
  webServer: [
    { command: "uv run --project ../backend --directory ../backend uvicorn tests.e2e_server:app --host 127.0.0.1 --port 8000 --no-access-log", url: "http://127.0.0.1:8000/health", reuseExistingServer: false, env: { APP_ENV: "test", FRONTEND_URL: "http://localhost:3000", UV_CACHE_DIR: "../.cache/uv" } },
    { command: "node scripts/start.mjs", url: "http://localhost:3000", reuseExistingServer: false, timeout: 120_000 },
  ],
});
