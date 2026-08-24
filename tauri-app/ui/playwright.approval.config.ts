import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  retries: 0,
  workers: 1,
  timeout: 90_000,
  use: {
    baseURL: "http://127.0.0.1:1420",
    viewport: { width: 1100, height: 760 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev -- --host 127.0.0.1",
    url: "http://127.0.0.1:1420",
    reuseExistingServer: false,
    timeout: 60_000,
    stdout: "pipe",
    stderr: "pipe",
    env: { VITE_DAEMON_TOKEN: "playwright-ui-token" },
  },
});
