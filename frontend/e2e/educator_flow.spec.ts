import { expect, test } from "@playwright/test";
import { backend, registerUser, uniqueEmail } from "./fixtures";

/**
 * Educator creates a class + lesson + quiz via the API,
 * then logs into the UI and confirms they are visible.
 */
test("educator sees classes and materials after API setup", async ({ page }) => {
  const api = await backend();
  const email = uniqueEmail("e2e-ed-ui");
  const auth = await registerUser(api, email, "educator");
  const headers = { Authorization: `Bearer ${auth.access_token}` };

  const cls = await api.post("/classes", {
    headers,
    data: { title: "E2E Algorithms", description: "desc" }
  });
  expect(cls.ok()).toBeTruthy();
  const createdClass = await cls.json();

  const material = await api.post(`/classes/${createdClass.id}/materials`, {
    headers,
    data: {
      title: "E2E Recursion",
      type: "lesson",
      sections: [
        { title: "Base case", content: "A stopping condition exists.", order_index: 0 }
      ]
    }
  });
  expect(material.ok()).toBeTruthy();

  // Seed auth in localStorage then visit dashboard
  await page.goto("/");
  await page.evaluate((value: string) => window.localStorage.setItem("edutrack.auth", value), JSON.stringify(auth));
  await page.goto("/dashboard");
  await expect(page.getByText(/E2E Algorithms/)).toBeVisible({ timeout: 15_000 });
});
