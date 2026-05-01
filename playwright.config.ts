import { defineConfig } from "@playwright/test"

const chromeExecutable =
  process.env.CHROME_BIN ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

export default defineConfig({
  testDir: "./tests/browser",
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: "http://127.0.0.1:3001",
    browserName: "chromium",
    launchOptions: {
      executablePath: chromeExecutable,
    },
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run start:test",
    url: "http://127.0.0.1:3001",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
