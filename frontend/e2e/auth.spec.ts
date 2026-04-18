import { expect, test } from "@playwright/test";
import { uniqueEmail } from "./fixtures";

test.describe("auth pages", () => {
  test("register → redirect to dashboard", async ({ page }) => {
    const email = uniqueEmail("e2e-educator");
    await page.goto("/register");
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill("password-123");
    const roleSelect = page.getByLabel(/role/i).or(page.locator("select[name='role']"));
    if (await roleSelect.count()) {
      await roleSelect.first().selectOption("educator");
    }
    await page.getByRole("button", { name: /register|create/i }).click();
    await expect(page).toHaveURL(/dashboard|classes/, { timeout: 15_000 });
  });

  test("login with wrong password shows error", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email/i).fill("nope@example.com");
    await page.getByLabel(/password/i).fill("password-123");
    await page.getByRole("button", { name: /log ?in|sign ?in/i }).click();
    await expect(page.getByText(/invalid|incorrect|password|unauthorized/i)).toBeVisible({ timeout: 10_000 });
  });
});
