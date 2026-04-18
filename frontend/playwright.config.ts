import { defineConfig, devices } from "@playwright/test";

const BACKEND_URL = process.env.E2E_BACKEND_URL ?? "http://127.0.0.1:8000";
const FRONTEND_URL = process.env.E2E_FRONTEND_URL ?? "http://127.0.0.1:3000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: FRONTEND_URL,
    headless: true,
    trace: "retain-on-failure"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ],
  // Assumes scripts/run.sh is already running both backend + frontend.
  // Set E2E_SKIP_SERVER=1 and run them yourself, or rely on the default
  // webServer command below (uncomment the block and tweak for your env).
  //
  // webServer: [
  //   {
  //     command: "bash ../scripts/run.sh",
  //     url: FRONTEND_URL,
  //     reuseExistingServer: true,
  //     timeout: 120_000
  //   }
  // ]
});

export { BACKEND_URL, FRONTEND_URL };
