import { defineConfig, devices } from "@playwright/test";

const PORT = 13000;
const BASE_URL = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: true,
  retries: 0,
  reporter: [["line"]],
  timeout: 30_000,
  expect: {
    timeout: 5_000
  },
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off"
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"]
      }
    }
  ],
  webServer: [
    {
      command: "node e2e/fixtures/atlas-api-server.mjs",
      url: "http://127.0.0.1:18080/_atlas_e2e/health",
      reuseExistingServer: false,
      timeout: 30_000
    },
    {
      command:
        "ATLAS_API_INTERNAL_URL=http://127.0.0.1:18080 npm run dev -- --hostname 127.0.0.1 --port 13000",
      url: `${BASE_URL}/login`,
      reuseExistingServer: false,
      timeout: 120_000
    }
  ]
});
