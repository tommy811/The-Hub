import { expect, test } from "@playwright/test"

const routes = [
  "/",
  "/admin",
  "/content",
  "/creators",
  "/platforms/instagram/accounts",
  "/platforms/instagram/analytics",
  "/platforms/instagram/classification",
  "/platforms/instagram/outliers",
  "/platforms/tiktok/accounts",
  "/platforms/tiktok/analytics",
  "/platforms/tiktok/classification",
  "/platforms/tiktok/outliers",
  "/trends",
]

for (const route of routes) {
  test(`${route} renders without browser console errors`, async ({ page }) => {
    const consoleErrors: string[] = []
    const pageErrors: string[] = []

    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(message.text())
      }
    })
    page.on("pageerror", (error) => {
      pageErrors.push(error.message)
    })

    const response = await page.goto(route, { waitUntil: "domcontentloaded" })
    expect(response?.status(), `${route} should return HTTP 200`).toBe(200)
    await expect(page.locator("body")).toBeVisible()
    await page.waitForTimeout(500)

    expect(pageErrors, `${route} page errors`).toEqual([])
    expect(consoleErrors, `${route} console errors`).toEqual([])
  })
}
